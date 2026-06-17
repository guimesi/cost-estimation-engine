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
    ADR_TABLES,
    COL_ITEM_ID,
    COL_PROJECT_ID,
    COL_PROJECT_NAME,
    COL_SNAPSHOT_ID,
    TBL_COST_RESULTS,
    TBL_DESIGN_DETAILS,
    TBL_ITEM_RECORD,
    TBL_QTY_RESULTS,
)
from config.settings import SETTINGS
from src.models import ProjectRef

logger = logging.getLogger(__name__)

_JOIN_KEYS = [COL_ITEM_ID, COL_SNAPSHOT_ID]


# =============================================================================
# Fetching (mock vs Snowflake)
# =============================================================================
def _fetch_adr_tables() -> Dict[str, pd.DataFrame]:
    """Return the 4 ADR source tables as a dict keyed by table name."""
    if SETTINGS.is_mock:
        from src.mock_data import fetch_mock_table

        return {name: fetch_mock_table(name) for name in ADR_TABLES}

    from src.snowflake_client import get_shared_client

    client = get_shared_client()
    return {name: client.fetch_table(name) for name in ADR_TABLES}


def _join_tables(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join the 4 ADR tables on ``(ITEM_ID, SNAPSHOT_ID)`` into one frame.

    ``ADR_DIM_ESTIMATEITEMRECORD`` carries the project identity; the other
    three contribute design details, databook cost components, and quantity.
    """
    items = tables[TBL_ITEM_RECORD]
    design = tables[TBL_DESIGN_DETAILS]
    cost = tables[TBL_COST_RESULTS]
    qty = tables[TBL_QTY_RESULTS]

    df = items.merge(design, on=_JOIN_KEYS, how="left")
    df = df.merge(cost, on=_JOIN_KEYS, how="left")
    df = df.merge(qty, on=_JOIN_KEYS, how="left")
    return df


def _latest_snapshot_per_project(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows from each project's maximum ``SNAPSHOT_ID``."""
    latest = df.groupby(COL_PROJECT_ID)[COL_SNAPSHOT_ID].transform("max")
    return df[df[COL_SNAPSHOT_ID] == latest].reset_index(drop=True)


# =============================================================================
# Public API
# =============================================================================
def list_projects() -> List[ProjectRef]:
    """Return every project that has ADR estimations, at its latest snapshot."""
    joined = _latest_snapshot_per_project(_join_tables(_fetch_adr_tables()))
    out: List[ProjectRef] = []
    for project_id, group in joined.groupby(COL_PROJECT_ID):
        name = str(group[COL_PROJECT_NAME].iloc[0])
        snap = int(group[COL_SNAPSHOT_ID].iloc[0])
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
    joined = _latest_snapshot_per_project(_join_tables(_fetch_adr_tables()))
    lines = joined[joined[COL_PROJECT_ID] == project_id].reset_index(drop=True)
    if lines.empty:
        raise KeyError(f"No ADR estimations loaded for project {project_id!r}")
    return lines
