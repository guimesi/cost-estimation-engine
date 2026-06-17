"""Tests for the Excel EMMA loader (structure-based routing)."""
from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from config.schema import (
    LRC_FACTOR_MULTIPLIER,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    LRC_TOTAL_USD_RATE,
    MFC_CODE,
    MFC_FACTOR_VALUE,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
)
from config.settings import SETTINGS

# Material-shaped workbook (per-commodity factor). Matches the doc's MFC.xlsx.
_MATERIAL = pd.DataFrame(
    {
        "Location": ["Angola", "Australia", "Canada"],
        "locationCode": ["AO.LAD.E", "AU.ALT.P", "CA.MTL.E"],
        "code": ["302", "302.05", "ELECT"],
        "description": ["Air fins, Alloy", "Indexed Pricing", "Transformers"],
        "factorValue": [11.0, 0.35, None],  # last row dropped (NaN factor)
        "costUpdateReportingPeriod_name": ["2Q2024", "2Q2025", "2Q2025"],
    }
)

# Labor-shaped workbook (multiplier + USD rate, no code). Matches the doc's LRC.
_LABOR = pd.DataFrame(
    {
        "Location": ["Angola", "Australia", "Canada"],
        "locationCode": ["AO.LAD.E", "AU.ALT.P", "CA.MTL.E"],
        "factorMultiplier": [2.857143, 4.0, None],  # last row dropped (NaN factor)
        "costUpdateReportingPeriod_name": ["2Q2024", "2Q2025", "4Q2024"],
        "totalUSDRate": [0.0, 10.487076, 5.0],
    }
)


@pytest.fixture
def _excel_dir(tmp_path, monkeypatch):
    """Point SETTINGS at a temp EMMA dir and clear the loader's cache."""
    import src.emma_excel as emma_excel

    excel_settings = dataclasses.replace(
        SETTINGS, emma_source="excel", emma_dir=str(tmp_path)
    )
    monkeypatch.setattr("config.settings.SETTINGS", excel_settings)
    monkeypatch.setattr("src.emma_excel.SETTINGS", excel_settings)
    monkeypatch.setattr("src.emma_reference.SETTINGS", excel_settings)
    emma_excel._load_pair.cache_clear()
    yield tmp_path
    emma_excel._load_pair.cache_clear()


def _write(dir_path, mfc_name, mfc_df, lrc_name, lrc_df):
    mfc_df.to_excel(dir_path / mfc_name, index=False)
    lrc_df.to_excel(dir_path / lrc_name, index=False)


def test_routes_by_structure_not_filename(_excel_dir):
    """Even when the filenames are swapped, content determines the frame."""
    # Deliberately cross the names: the labor-shaped data is in MFC.xlsx.
    _write(_excel_dir, "MFC.xlsx", _LABOR, "LRC.xlsx", _MATERIAL)

    from src.emma_reference import load_lrc, load_mfc

    mfc = load_mfc()
    lrc = load_lrc()

    # Material frame got the per-code data regardless of the filename.
    assert MFC_CODE in mfc.columns
    assert set(mfc[MFC_CODE]) == {"302", "302.05"}  # NaN-factor row dropped
    # Labor frame got the multiplier + USD rate data.
    assert LRC_FACTOR_MULTIPLIER in lrc.columns
    assert LRC_TOTAL_USD_RATE in lrc.columns


def test_canonical_columns_and_nan_drop(_excel_dir):
    _write(_excel_dir, "MFC.xlsx", _MATERIAL, "LRC.xlsx", _LABOR)

    from src.emma_reference import load_lrc, load_mfc

    mfc = load_mfc()
    lrc = load_lrc()

    assert list(mfc.columns) == [
        "MFC_LOCATION",
        MFC_LOCATION_CODE,
        MFC_CODE,
        "MFC_DESCRIPTION",
        MFC_FACTOR_VALUE,
        MFC_PERIOD,
    ]
    assert len(mfc) == 2  # one NaN-factor material row dropped
    assert list(lrc.columns) == [
        "LRC_LOCATION",
        LRC_LOCATION_CODE,
        LRC_FACTOR_MULTIPLIER,
        LRC_TOTAL_USD_RATE,
        LRC_PERIOD,
    ]
    assert len(lrc) == 2  # one NaN-multiplier labor row dropped


def test_integration_with_available_selections(_excel_dir):
    _write(_excel_dir, "MFC.xlsx", _MATERIAL, "LRC.xlsx", _LABOR)

    from src.emma_reference import available_selections

    sels = available_selections()
    # Intersection of MFC and LRC (location, period); both share AO.LAD.E/2Q2024.
    pairs = {(s.location_code, s.period) for s in sels}
    assert ("AO.LAD.E", "2Q2024") in pairs


def test_missing_directory_raises(tmp_path, monkeypatch):
    import src.emma_excel as emma_excel

    excel_settings = dataclasses.replace(
        SETTINGS, emma_source="excel", emma_dir=str(tmp_path / "nope")
    )
    monkeypatch.setattr("src.emma_excel.SETTINGS", excel_settings)
    emma_excel._load_pair.cache_clear()
    with pytest.raises(FileNotFoundError):
        emma_excel.load_excel_mfc()
    emma_excel._load_pair.cache_clear()


def test_unclassifiable_workbook_raises(_excel_dir):
    pd.DataFrame({"foo": [1], "bar": [2]}).to_excel(
        _excel_dir / "MFC.xlsx", index=False
    )
    _LABOR.to_excel(_excel_dir / "LRC.xlsx", index=False)

    import src.emma_excel as emma_excel

    with pytest.raises(ValueError, match="Cannot classify"):
        emma_excel.load_excel_mfc()
