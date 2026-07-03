"""ADR repository: list projects and load a project's latest-snapshot lines.

Joins the 4 ADR source tables into one canonical per-item frame and selects
the latest snapshot per project (the doc: "the latest snapshot available for
that project"). Branches on ``SETTINGS.is_mock`` so the same join logic runs
against mock frames or real Snowflake reads - only the fetcher changes.
"""
from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from config.schema import (
    ADR_COST_RESULTS_RENAME,
    ADR_ITEM_RECORD_RENAME,
    ADR_LINE_NUMERIC_COLUMNS,
    ADR_QTY_RESULTS_RENAME,
    ADR_TABLES,
    COL_BASE_MATERIAL_MFC,
    COL_COST_BASIS,
    COL_DESCRIPTION,
    COL_ITEM_ID,
    COL_PROJECT_ID,
    COL_PROJECT_NAME,
    COL_QUANTITY,
    COL_SNAPSHOT_ID,
    COL_VENDOR_SHOP_FAB_MFC,
    COL_WBS,
    SNAPSHOT_PRIORITY,
    TBL_COST_RESULTS,
    TBL_DESIGN_DETAILS,
    TBL_ITEM_RECORD,
    TBL_QTY_RESULTS,
)
from config.settings import SETTINGS
from src.models import ProjectRef

logger = logging.getLogger(__name__)

_JOIN_KEYS = [COL_ITEM_ID, COL_SNAPSHOT_ID]

# Canonical columns the engine/UI need on the line frame, by source table.
# QUANTITY comes from the qty table, so the cost table contributes every other
# databook numeric plus the two material factor codes.
_DB_NUMERIC_COLS = [c for c in ADR_LINE_NUMERIC_COLUMNS if c != COL_QUANTITY]
_ITEM_COLS = [COL_ITEM_ID, COL_PROJECT_ID, COL_PROJECT_NAME, COL_SNAPSHOT_ID,
              COL_WBS, COL_DESCRIPTION, COL_COST_BASIS]
_COST_COLS = [COL_ITEM_ID, *_DB_NUMERIC_COLS,
              COL_BASE_MATERIAL_MFC, COL_VENDOR_SHOP_FAB_MFC]


# =============================================================================
# Mock canonical line frame (the whole universe; mock is small)
# =============================================================================
def _mock_lines() -> pd.DataFrame:
    """Mock path: the 4 mock tables are canonical projections of one master."""
    from src.mock_data import fetch_mock_table

    tables = {name: fetch_mock_table(name) for name in ADR_TABLES}
    return _join_tables(tables)


def _join_tables(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join the 4 (mock) ADR tables on ``(ITEM_ID, SNAPSHOT_ID)`` into one frame.

    Used for the mock source, whose tables are wide canonical projections of a
    single master. The real Snowflake schema is reconciled in
    :func:`_snowflake_lines` instead (different column layout + an EAV design
    table that must not be joined).
    """
    items = tables[TBL_ITEM_RECORD]
    design = tables[TBL_DESIGN_DETAILS]
    cost = tables[TBL_COST_RESULTS]
    qty = tables[TBL_QTY_RESULTS]

    df = items.merge(design, on=_JOIN_KEYS, how="left")
    df = df.merge(cost, on=_JOIN_KEYS, how="left")
    df = df.merge(qty, on=_JOIN_KEYS, how="left")
    return df


# Raw columns to project per ADR table = the keys of each rename map (exactly the
# columns the engine/UI need). Pushing the projection to Snowflake means a narrow
# read instead of SELECT * across dozens of columns.
_ITEM_RAW_COLS = list(ADR_ITEM_RECORD_RENAME)
_COST_RAW_COLS = list(ADR_COST_RESULTS_RENAME)
_QTY_RAW_COLS = list(ADR_QTY_RESULTS_RENAME)


def _sf_list_projects() -> List[ProjectRef]:
    """Snowflake path: list projects via a server-side aggregation.

    Only the item table is touched, and only as a ``GROUP BY`` - one row per
    (project, snapshot) instead of transferring every line item. The latest
    snapshot per project is then picked locally on that small frame.
    """
    from src.snowflake_client import get_shared_client

    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)
    agg = client.fetch_query(
        f"SELECT PLANVIEW_ID, MAX(FILE_NAME) AS FILE_NAME, SNAPSHOT, "
        f"COUNT(*) AS N_ITEMS FROM {item_t} GROUP BY PLANVIEW_ID, SNAPSHOT"
    )
    agg = agg.rename(
        columns={
            "PLANVIEW_ID": COL_PROJECT_ID,
            "FILE_NAME": COL_PROJECT_NAME,
            "SNAPSHOT": COL_SNAPSHOT_ID,
        }
    )
    return _projects_from_snapshot_counts(agg)


def _sf_load_project_lines(project_id: str) -> pd.DataFrame:
    """Snowflake path: load ONE project's latest-snapshot lines, projected.

    Pushes the project filter to Snowflake instead of pulling the whole table:
    finds the project's latest snapshot, then reads only the needed columns for
    its rows. Cost/qty carry no project key, so they are filtered by the
    matching ``ROW_ID``s via a subquery on the item table. Joins on ``ROW_ID``
    (-> ``ITEM_ID``); the EAV design-details table is intentionally skipped.
    """
    from src.snowflake_client import get_shared_client

    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)

    snaps = client.fetch_query(
        f"SELECT DISTINCT SNAPSHOT FROM {item_t} WHERE PLANVIEW_ID = %s",
        params=[project_id],
    )
    if snaps.empty:
        raise KeyError(f"No ADR estimations loaded for project {project_id!r}")
    snaps = snaps.rename(columns={"SNAPSHOT": COL_SNAPSHOT_ID})
    latest = snaps.loc[_snapshot_rank(snaps[COL_SNAPSHOT_ID]).idxmax(), COL_SNAPSHOT_ID]

    sel_params = [project_id, latest]
    row_filter = (
        f"ROW_ID IN (SELECT ROW_ID FROM {item_t} "
        "WHERE PLANVIEW_ID = %s AND SNAPSHOT = %s)"
    )
    items = client.fetch_table(
        TBL_ITEM_RECORD, columns=_ITEM_RAW_COLS,
        where="PLANVIEW_ID = %s AND SNAPSHOT = %s", params=sel_params,
    ).rename(columns=ADR_ITEM_RECORD_RENAME)
    cost = client.fetch_table(
        TBL_COST_RESULTS, columns=_COST_RAW_COLS, where=row_filter, params=sel_params,
    ).rename(columns=ADR_COST_RESULTS_RENAME)
    qty = client.fetch_table(
        TBL_QTY_RESULTS, columns=_QTY_RAW_COLS, where=row_filter, params=sel_params,
    ).rename(columns=ADR_QTY_RESULTS_RENAME)

    _require_columns(items, _ITEM_COLS, TBL_ITEM_RECORD)
    _require_columns(cost, _COST_COLS, TBL_COST_RESULTS)
    _require_columns(qty, [COL_ITEM_ID, COL_QUANTITY], TBL_QTY_RESULTS)

    df = (
        items[_ITEM_COLS]
        .merge(cost[_COST_COLS], on=COL_ITEM_ID, how="inner")
        .merge(qty[[COL_ITEM_ID, COL_QUANTITY]], on=COL_ITEM_ID, how="left")
        .reset_index(drop=True)
    )
    return _coerce_line_numerics(df)


def _coerce_line_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce databook numerics (some arrive as strings) and normalize MFC codes."""
    for col in ADR_LINE_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in (COL_BASE_MATERIAL_MFC, COL_VENDOR_SHOP_FAB_MFC):
        df[col] = df[col].astype(str).str.strip()
    return df


def _require_columns(df: pd.DataFrame, cols: list, table: str) -> None:
    """Raise a clear error if a renamed ADR table is missing canonical columns."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"ADR table {table} is missing canonical column(s) {missing} after "
            f"rename. Check the raw->canonical map in config/schema.py against "
            f"the real headers (run scripts/inspect_adr_schema.py). "
            f"Got columns: {sorted(df.columns)}"
        )


def _snapshot_rank(values: pd.Series) -> pd.Series:
    """Map snapshot labels to a sortable rank (higher = more recent).

    Known stage gates use ``SNAPSHOT_PRIORITY``; otherwise a numeric reading of
    the value (so the mock's integer snapshots order correctly); otherwise the
    lowest rank so an unrecognized label never spuriously wins.
    """
    up = values.astype(str).str.strip().str.upper()
    rank = up.map(SNAPSHOT_PRIORITY).astype("float64")
    numeric = pd.to_numeric(up, errors="coerce")
    rank = rank.fillna(numeric)
    return rank.fillna(-1.0)


def _latest_snapshot_per_project(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows from each project's highest-ranked ``SNAPSHOT_ID``."""
    rank = _snapshot_rank(df[COL_SNAPSHOT_ID])
    top = rank.groupby(df[COL_PROJECT_ID]).transform("max")
    return df[rank == top].reset_index(drop=True)


def _coerce_snapshot_id(value: object) -> object:
    """Return the snapshot id as int when numeric (mock), else its string form."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


# =============================================================================
# ProjectRef builders (latest snapshot per project)
# =============================================================================
def _projects_from_mock_frame(joined: pd.DataFrame) -> List[ProjectRef]:
    """Build refs from the mock per-item latest-snapshot frame (n_items = rows)."""
    out: List[ProjectRef] = []
    for project_id, group in joined.groupby(COL_PROJECT_ID):
        out.append(
            ProjectRef(
                project_id=str(project_id),
                project_name=str(group[COL_PROJECT_NAME].iloc[0]),
                snapshot_id=_coerce_snapshot_id(group[COL_SNAPSHOT_ID].iloc[0]),
                n_items=len(group),
            )
        )
    return sorted(out, key=lambda p: p.project_id)


def _projects_from_snapshot_counts(agg: pd.DataFrame) -> List[ProjectRef]:
    """Pick the latest snapshot per project from a (project, snapshot, count) frame.

    ``agg`` has one row per (project, snapshot) with an ``N_ITEMS`` count; the
    highest-ranked snapshot per project wins and supplies the item count.
    """
    if agg.empty:
        return []
    ranked = agg.assign(_rank=_snapshot_rank(agg[COL_SNAPSHOT_ID]))
    top = ranked.loc[ranked.groupby(COL_PROJECT_ID)["_rank"].idxmax()]
    out = [
        ProjectRef(
            project_id=str(row[COL_PROJECT_ID]),
            project_name=str(row[COL_PROJECT_NAME]),
            snapshot_id=_coerce_snapshot_id(row[COL_SNAPSHOT_ID]),
            n_items=int(row["N_ITEMS"]),
        )
        for _, row in top.iterrows()
    ]
    return sorted(out, key=lambda p: p.project_id)


# =============================================================================
# Public API
# =============================================================================
def list_projects() -> List[ProjectRef]:
    """Return every project that has ADR estimations, at its latest snapshot.

    Mock loads the whole (small) universe; Snowflake aggregates server-side so
    the listing never transfers line items.
    """
    if SETTINGS.is_mock:
        return _projects_from_mock_frame(_latest_snapshot_per_project(_mock_lines()))
    return _sf_list_projects()


def load_project_lines(project_id: str) -> pd.DataFrame:
    """Return the canonical line-item frame for a project's latest snapshot.

    Raises ``KeyError`` if the project has no ADR estimations loaded. Snowflake
    reads only this project's rows (projected + filtered); mock filters the
    in-memory universe.
    """
    if SETTINGS.is_mock:
        joined = _latest_snapshot_per_project(_mock_lines())
        lines = joined[joined[COL_PROJECT_ID] == project_id].reset_index(drop=True)
        if lines.empty:
            raise KeyError(f"No ADR estimations loaded for project {project_id!r}")
        return lines
    return _sf_load_project_lines(project_id)
