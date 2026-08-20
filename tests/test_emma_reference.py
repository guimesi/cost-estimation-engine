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


def test_databricks_load_path(monkeypatch):
    """The non-mock branch renames raw columns and fetches via the client."""
    import dataclasses

    import src.databricks_client as dbc

    dbx_settings = dataclasses.replace(
        emma.SETTINGS, data_source="databricks", emma_source="databricks"
    )
    monkeypatch.setattr("src.emma_reference.SETTINGS", dbx_settings)

    raw = pd.DataFrame({"MFC_CODE": ["C1"], "MFC_LOCATIONCODE": ["X"],
                        "MFC_FACTORVALUE": [1.2], "MFC_COSTUPDATEREPORTINGPERIOD_NAME": ["P1"],
                        "MFC_LOCATION": ["Loc"], "MFC_DESCRIPTION": ["d"]})

    class _Client:
        def qualified(self, table):
            return f"CAT.SCH.{table}"

        def fetch_query(self, sql):
            assert "CAT.SCH.MFC" in sql  # reads are fully qualified
            return raw

    monkeypatch.setattr(dbc, "get_shared_client", lambda: _Client())
    df = emma.load_mfc()
    assert MFC_CODE in df.columns and MFC_FACTOR_VALUE in df.columns
    assert df.iloc[0][MFC_FACTOR_VALUE] == 1.2


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
