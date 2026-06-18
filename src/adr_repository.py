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
              COL_WBS, COL_DESCRIPTION]
_COST_COLS = [COL_ITEM_ID, *_DB_NUMERIC_COLS,
              COL_BASE_MATERIAL_MFC, COL_VENDOR_SHOP_FAB_MFC]


# =============================================================================
# Canonical line frame (mock vs Snowflake)
# =============================================================================
def _canonical_lines() -> pd.DataFrame:
    """Return the joined per-item canonical frame (all snapshots)."""
    if SETTINGS.is_mock:
        return _mock_lines()
    return _snowflake_lines()


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


def _snowflake_lines() -> pd.DataFrame:
    """Snowflake path: reconcile the real ITPlus schema into the canonical frame.

    Joins item record + cost results + quantity on ``ROW_ID`` (-> ``ITEM_ID``);
    the EAV design-details table is intentionally skipped. Renames each table's
    raw columns, then coerces the databook numerics (some arrive as strings).
    """
    from src.snowflake_client import get_shared_client

    client = get_shared_client()
    items = client.fetch_table(TBL_ITEM_RECORD).rename(columns=ADR_ITEM_RECORD_RENAME)
    cost = client.fetch_table(TBL_COST_RESULTS).rename(columns=ADR_COST_RESULTS_RENAME)
    qty = client.fetch_table(TBL_QTY_RESULTS).rename(columns=ADR_QTY_RESULTS_RENAME)

    _require_columns(items, _ITEM_COLS, TBL_ITEM_RECORD)
    _require_columns(cost, _COST_COLS, TBL_COST_RESULTS)
    _require_columns(qty, [COL_ITEM_ID, "QUANTITY"], TBL_QTY_RESULTS)

    df = (
        items[_ITEM_COLS]
        .merge(cost[_COST_COLS], on=COL_ITEM_ID, how="inner")
        .merge(qty[[COL_ITEM_ID, "QUANTITY"]], on=COL_ITEM_ID, how="left")
    )

    # Databook values can come back as strings ("0", "9.47") -> coerce to float.
    for col in ADR_LINE_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    # Material factor codes are looked up as strings; normalize.
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
# Public API
# =============================================================================
def list_projects() -> List[ProjectRef]:
    """Return every project that has ADR estimations, at its latest snapshot."""
    joined = _latest_snapshot_per_project(_canonical_lines())
    out: List[ProjectRef] = []
    for project_id, group in joined.groupby(COL_PROJECT_ID):
        name = str(group[COL_PROJECT_NAME].iloc[0])
        snap = _coerce_snapshot_id(group[COL_SNAPSHOT_ID].iloc[0])
        out.append(
            ProjectRef(
                project_id=str(project_id),
                project_name=name,
                snapshot_id=snap,
                n_items=len(group),
            )
        )
    return sorted(out, key=lambda p: p.project_id)


def load_project_lines(project_id: str) -> pd.DataFrame:
    """Return the canonical line-item frame for a project's latest snapshot.

    Raises ``KeyError`` if the project has no ADR estimations loaded.
    """
    joined = _latest_snapshot_per_project(_canonical_lines())
    lines = joined[joined[COL_PROJECT_ID] == project_id].reset_index(drop=True)
    if lines.empty:
        raise KeyError(f"No ADR estimations loaded for project {project_id!r}")
    return lines
