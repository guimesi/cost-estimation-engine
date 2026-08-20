"""EMMA reference loading, selections, and lookups."""
from __future__ import annotations

import pandas as pd

from config.schema import (
    LRC_FACTOR_MULTIPLIER,
    LRC_LOCATION,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    LRC_TOTAL_USD_RATE,
    MFC_CODE,
    MFC_FACTOR_VALUE,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
)
from src import emma_reference as emma


def test_available_selections_is_intersection():
    sels = emma.available_selections()
    assert sels, "expected at least one (location, period) selection"
    # Every offered selection must resolve a valid LRC lookup.
    lrc = emma.load_lrc()
    for s in sels:
        assert emma.lrc_lookup(lrc, s.location_code, s.period) is not None


def test_lrc_lookup_hit_and_miss():
    lrc = emma.load_lrc()
    s = emma.available_selections()[0]
    factor, usd = emma.lrc_lookup(lrc, s.location_code, s.period)
    assert factor > 0 and usd > 0
    assert emma.lrc_lookup(lrc, "NOPE", "1999-H1") is None


def test_mfc_factor_map():
    mfc = emma.load_mfc()
    s = emma.available_selections()[0]
    fmap = emma.mfc_factor_map(mfc, s.location_code, s.period)
    assert fmap
    assert all(v > 0 for v in fmap.values())


def test_databricks_load_path_routes_by_content(monkeypatch):
    """The non-mock branch reads both tables, fully qualified, and routes each
    by its COLUMNS (business Q8) - here the contents are deliberately crossed
    (the table named MFC holds the labor columns) and still land correctly."""
    import dataclasses

    import src.databricks_client as dbc

    dbx_settings = dataclasses.replace(
        emma.SETTINGS, data_source="databricks", emma_source="databricks"
    )
    monkeypatch.setattr("src.emma_reference.SETTINGS", dbx_settings)

    material_raw = pd.DataFrame(
        {"code": ["C1"], "locationCode": ["X"], "factorValue": [1.2],
         "costUpdateReportingPeriod_name": ["P1"], "location": ["Loc"],
         "description": ["d"]}
    )
    labor_raw = pd.DataFrame(
        {"location": ["Loc"], "locationCode": ["X"], "factorMultiplier": [1.1],
         "totalUSDRate": [50.0], "costUpdateReportingPeriod_name": ["P1"]}
    )

    class _Client:
        def qualified(self, table):
            return f"CAT.SCH.{table}"

        def fetch_query(self, sql):
            assert "CAT.SCH." in sql  # reads are fully qualified
            return labor_raw if "CAT.SCH.MFC" in sql else material_raw

    monkeypatch.setattr(dbc, "get_shared_client", lambda: _Client())
    emma._load_databricks_pair.cache_clear()
    try:
        mfc = emma.load_mfc()
        lrc = emma.load_lrc()
    finally:
        emma._load_databricks_pair.cache_clear()
    assert MFC_CODE in mfc.columns and MFC_FACTOR_VALUE in mfc.columns
    assert mfc.iloc[0][MFC_FACTOR_VALUE] == 1.2
    assert lrc.iloc[0][LRC_FACTOR_MULTIPLIER] == 1.1
    assert lrc.iloc[0][LRC_TOTAL_USD_RATE] == 50.0


def test_available_selections_accepts_injected_frames():
    mfc = pd.DataFrame(
        {MFC_CODE: ["C1"], MFC_LOCATION_CODE: ["X"], MFC_PERIOD: ["P1"],
         MFC_FACTOR_VALUE: [1.0]}
    )
    lrc = pd.DataFrame(
        {LRC_LOCATION: ["Loc X"], LRC_LOCATION_CODE: ["X"], LRC_PERIOD: ["P1"],
         LRC_FACTOR_MULTIPLIER: [1.1], LRC_TOTAL_USD_RATE: [50.0]}
    )
    sels = emma.available_selections(mfc, lrc)
    assert len(sels) == 1
    assert sels[0].location_code == "X" and sels[0].period == "P1"


def test_labor_selections_offer_every_lrc_pair():
    # MFC covers (X, P1) only; LRC has (X, P1) and (Y, P1).
    mfc = pd.DataFrame(
        {MFC_CODE: ["C1"], MFC_LOCATION_CODE: ["X"], MFC_PERIOD: ["P1"],
         MFC_FACTOR_VALUE: [1.0]}
    )
    lrc = pd.DataFrame(
        {LRC_LOCATION: ["Loc X", "Loc Y"], LRC_LOCATION_CODE: ["X", "Y"],
         LRC_PERIOD: ["P1", "P1"], LRC_FACTOR_MULTIPLIER: [1.1, 1.2],
         LRC_TOTAL_USD_RATE: [50.0, 60.0]}
    )
    # labor_selections offers BOTH LRC pairs (a superset of available_selections).
    labor = emma.labor_selections(lrc)
    assert {(s.location_code, s.period) for s in labor} == {("X", "P1"), ("Y", "P1")}
    available = {(s.location_code, s.period) for s in emma.available_selections(mfc, lrc)}
    assert available == {("X", "P1")}
    assert available.issubset({(s.location_code, s.period) for s in labor})


def test_labor_only_selections_are_lrc_pairs_absent_from_mfc():
    # MFC covers (X, P1) only; LRC has (X, P1) and (Y, P1).
    mfc = pd.DataFrame(
        {MFC_CODE: ["C1"], MFC_LOCATION_CODE: ["X"], MFC_PERIOD: ["P1"],
         MFC_FACTOR_VALUE: [1.0]}
    )
    lrc = pd.DataFrame(
        {LRC_LOCATION: ["Loc X", "Loc Y"], LRC_LOCATION_CODE: ["X", "Y"],
         LRC_PERIOD: ["P1", "P1"], LRC_FACTOR_MULTIPLIER: [1.1, 1.2],
         LRC_TOTAL_USD_RATE: [50.0, 60.0]}
    )
    # (X, P1) is selectable; (Y, P1) is labor-only (no MFC).
    assert [s.location_code for s in emma.available_selections(mfc, lrc)] == ["X"]
    labor_only = emma.labor_only_selections(mfc, lrc)
    assert len(labor_only) == 1
    assert labor_only[0].location_code == "Y" and labor_only[0].period == "P1"
