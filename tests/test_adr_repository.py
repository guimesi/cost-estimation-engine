"""ADR repository: project listing + latest-snapshot line loading."""
from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from config.schema import (
    ADR_LINE_NUMERIC_COLUMNS,
    COL_BASE_MATERIAL_MFC,
    COL_DB_FIELD_LABOR_H,
    COL_PROJECT_ID,
    COL_SNAPSHOT_ID,
    COL_VENDOR_SHOP_FAB_MFC,
    TBL_COST_RESULTS,
    TBL_ITEM_RECORD,
    TBL_QTY_RESULTS,
)
from config.settings import SETTINGS
from src import adr_repository as repo


def test_list_projects_returns_latest_snapshot():
    projects = repo.list_projects()
    assert projects
    for p in projects:
        # Mock data has snapshots {1, 2}; latest must be 2.
        assert p.snapshot_id == 2
        assert p.n_items > 0


def test_load_project_lines_has_canonical_columns():
    pid = repo.list_projects()[0].project_id
    lines = repo.load_project_lines(pid)
    assert (lines[COL_PROJECT_ID] == pid).all()
    assert (lines[COL_SNAPSHOT_ID] == 2).all()
    for col in (*ADR_LINE_NUMERIC_COLUMNS, COL_BASE_MATERIAL_MFC):
        assert col in lines.columns


def test_load_unknown_project_raises():
    with pytest.raises(KeyError):
        repo.load_project_lines("PRJ-DOES-NOT-EXIST")


# ---------------------------------------------------------------------------
# Snowflake reconciliation: real ITPlus column names -> canonical line frame.
# ---------------------------------------------------------------------------
def _raw_item_record() -> pd.DataFrame:
    # Two planview projects; PV1 has both SCREEN and GATE3 snapshots.
    return pd.DataFrame(
        {
            "ROW_ID": ["PV1_GATE3_1", "PV1_SCREEN_1", "PV2_GATE2_1"],
            "PLANVIEW_ID": ["PV1", "PV1", "PV2"],
            "FILE_NAME": ["PV1 Coker", "PV1 Coker", "PV2 LNG"],
            "SNAPSHOT": ["GATE3", "SCREEN", "GATE2"],
            "COMPLETE_WBC": ["313.1", "313.1", "200.0"],
            "ITEM_DESCRIPTION": ["Pipe A", "Pipe A (old)", "Vessel B"],
            "COST_BASIS": ["4Q2023", "2Q2023", "2Q2023"],
        }
    )


def _raw_cost_results() -> pd.DataFrame:
    # Databook hours arrive as strings, like the real export.
    return pd.DataFrame(
        {
            "ROW_ID": ["PV1_GATE3_1", "PV1_SCREEN_1", "PV2_GATE2_1"],
            "DB_SPEC_S_C": ["10", "5", "0"],
            "DB_SPEC_S_C_COST": [100.0, 50.0, 0.0],
            "DB_FIELD_SHOP_FAB": ["0", "0", "2"],
            "DB_FIELD_SHOP_FAB_COST": [0.0, 0.0, 20.0],
            "DB_FIELD_LABOR": ["9.47", "3", "1"],
            "DB_FIELD_LABOR_COST": [9.47, 3.0, 1.0],
            "DB_BASE_MATERIAL_COST": [0.44, 0.2, 5.0],
            "DB_VENDOR_SHOP_FAB_COST": [328.0, 100.0, 0.0],
            "BASE_MATERIAL_MFC": ["313.01", "313.01", "200.01"],
            "VENDOR_SHOP_FAB_MFC": ["313.08", "313.08", "200.08"],
        }
    )


def _raw_qty_results() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ROW_ID": ["PV1_GATE3_1", "PV1_SCREEN_1", "PV2_GATE2_1"],
            "QUANTITY": [2.0, 1.0, 3.0],
        }
    )


class _FakeClient:
    """Emulates the slice of Snowflake the repository now relies on.

    The new path pushes work to SQL: an aggregation to list projects, a distinct
    query for a project's snapshots, and projected + filtered table reads. The
    fake interprets those queries against the raw frames so the tests exercise
    the same server-side semantics (filtering, latest-snapshot pick) the real
    client would apply.
    """

    _BY_TABLE = {
        TBL_ITEM_RECORD: _raw_item_record,
        TBL_COST_RESULTS: _raw_cost_results,
        TBL_QTY_RESULTS: _raw_qty_results,
    }

    def qualified(self, table_name):
        return table_name

    def fetch_query(self, sql, params=None):
        item = self._BY_TABLE[TBL_ITEM_RECORD]()
        if "GROUP BY" in sql:  # _sf_list_projects aggregation
            return (
                item.groupby(["PLANVIEW_ID", "SNAPSHOT"], as_index=False)
                .agg(FILE_NAME=("FILE_NAME", "max"), N_ITEMS=("ROW_ID", "size"))
                [["PLANVIEW_ID", "FILE_NAME", "SNAPSHOT", "N_ITEMS"]]
            )
        if "DISTINCT SNAPSHOT" in sql:  # latest-snapshot lookup for one project
            sub = item[item["PLANVIEW_ID"] == params[0]]
            return pd.DataFrame({"SNAPSHOT": sub["SNAPSHOT"].unique()})
        raise AssertionError(f"unexpected query: {sql}")

    def fetch_table(self, table_name, columns=None, where=None, params=None, limit=None):
        df = self._BY_TABLE[table_name]()
        if where and where.startswith("PLANVIEW_ID"):
            pid, snap = params
            df = df[(df["PLANVIEW_ID"] == pid) & (df["SNAPSHOT"] == snap)]
        elif where and where.startswith("ROW_ID IN"):
            pid, snap = params
            item = self._BY_TABLE[TBL_ITEM_RECORD]()
            ids = item[(item["PLANVIEW_ID"] == pid) & (item["SNAPSHOT"] == snap)]["ROW_ID"]
            df = df[df["ROW_ID"].isin(ids)]
        return df.reset_index(drop=True)


@pytest.fixture
def _snowflake(monkeypatch):
    import src.snowflake_client as sc

    sf_settings = dataclasses.replace(SETTINGS, data_source="snowflake")
    monkeypatch.setattr("src.adr_repository.SETTINGS", sf_settings)
    monkeypatch.setattr(sc, "get_shared_client", lambda: _FakeClient())


def test_snowflake_reconciles_canonical_columns(_snowflake):
    # Loading one project projects + reconciles the raw ITPlus columns.
    lines = repo.load_project_lines("PV1")
    for col in (*ADR_LINE_NUMERIC_COLUMNS, COL_BASE_MATERIAL_MFC, COL_VENDOR_SHOP_FAB_MFC):
        assert col in lines.columns
    # String databook hours were coerced to numeric.
    assert lines[COL_DB_FIELD_LABOR_H].dtype.kind == "f"


def test_snowflake_latest_snapshot_uses_gate_priority(_snowflake):
    projects = {p.project_id: p for p in repo.list_projects()}
    # PV1 had SCREEN + GATE3 -> GATE3 wins; PV2 only GATE2.
    assert projects["PV1"].snapshot_id == "GATE3"
    assert projects["PV2"].snapshot_id == "GATE2"
    assert projects["PV1"].n_items == 1  # count at the winning (GATE3) snapshot

    pv1 = repo.load_project_lines("PV1")
    assert (pv1[COL_SNAPSHOT_ID] == "GATE3").all()
    assert len(pv1) == 1  # the SCREEN row was dropped
