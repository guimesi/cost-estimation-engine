"""Core calculation correctness for the estimation engine."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from config.schema import (
    COL_BASE_MATERIAL_COST_NEW,
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_BASE_MATERIAL_MFC,
    COL_DB_BM_C,
    COL_DB_FIELD_LABOR_C,
    COL_DB_FIELD_LABOR_H,
    COL_DB_FSF_C,
    COL_DB_FSF_H,
    COL_DB_SPEC_C,
    COL_DB_SPEC_H,
    COL_DB_VSF_C,
    COL_FIELD_LABOR_COST_NEW,
    COL_FIELD_LABOR_H_NEW,
    COL_FSF_COST_NEW,
    COL_FSF_H_NEW,
    COL_SPEC_COST_NEW,
    COL_SPEC_H_NEW,
    COL_TOTAL_COST_NEW,
    COL_TOTAL_COST_ORIG,
    COL_TOTAL_HOURS_NEW,
    COL_TOTAL_HOURS_ORIG,
    COL_VENDOR_SHOP_FAB_COST_NEW,
    COL_VENDOR_SHOP_FAB_FACTOR_MISSING,
    COL_VENDOR_SHOP_FAB_MFC,
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
from src.estimation_engine import estimate_lines, run_estimation
from src.models import FactorSelection, ProjectRef

LOC, PERIOD = "USTX", "2024-H1"
SELECTION = FactorSelection(LOC, "Houston", PERIOD)


def _one_line():
    return pd.DataFrame(
        [{
            COL_DB_SPEC_H: 10.0, COL_DB_FSF_H: 20.0, COL_DB_FIELD_LABOR_H: 5.0,
            COL_DB_SPEC_C: 100.0, COL_DB_FSF_C: 200.0, COL_DB_FIELD_LABOR_C: 50.0,
            COL_DB_BM_C: 1000.0, COL_DB_VSF_C: 2000.0,
            COL_BASE_MATERIAL_MFC: "C1", COL_VENDOR_SHOP_FAB_MFC: "C2",
        }]
    )


def _lrc(factor=1.1, usd=50.0):
    return pd.DataFrame([{
        LRC_LOCATION: "Houston", LRC_LOCATION_CODE: LOC, LRC_PERIOD: PERIOD,
        LRC_FACTOR_MULTIPLIER: factor, LRC_TOTAL_USD_RATE: usd,
    }])


def _mfc(c1=1.2, c2=0.9):
    return pd.DataFrame([
        {MFC_CODE: "C1", MFC_LOCATION_CODE: LOC, MFC_PERIOD: PERIOD, MFC_FACTOR_VALUE: c1},
        {MFC_CODE: "C2", MFC_LOCATION_CODE: LOC, MFC_PERIOD: PERIOD, MFC_FACTOR_VALUE: c2},
    ])


def test_labor_and_material_formulas():
    out, warnings = estimate_lines(_one_line(), _mfc(), _lrc(), SELECTION)
    r = out.iloc[0]
    assert not warnings
    # Labor: hours * F, then * USD
    assert r[COL_SPEC_H_NEW] == pytest.approx(11.0)
    assert r[COL_SPEC_COST_NEW] == pytest.approx(550.0)
    assert r[COL_FSF_H_NEW] == pytest.approx(22.0)
    assert r[COL_FSF_COST_NEW] == pytest.approx(1100.0)
    # Field labor: same LRC factor + USD rate as the other labor categories
    assert r[COL_FIELD_LABOR_H_NEW] == pytest.approx(5.5)     # 5 * 1.1
    assert r[COL_FIELD_LABOR_COST_NEW] == pytest.approx(275.0)  # 5.5 * 50
    # Material: cost * MFC factor
    assert r[COL_BASE_MATERIAL_COST_NEW] == pytest.approx(1200.0)
    assert r[COL_VENDOR_SHOP_FAB_COST_NEW] == pytest.approx(1800.0)
    # Both material codes matched -> no missing-MFC flag
    assert not r[COL_BASE_MATERIAL_FACTOR_MISSING]
    assert not r[COL_VENDOR_SHOP_FAB_FACTOR_MISSING]


def test_totals():
    out, _ = estimate_lines(_one_line(), _mfc(), _lrc(), SELECTION)
    r = out.iloc[0]
    assert r[COL_TOTAL_HOURS_ORIG] == pytest.approx(35.0)   # 10+20+5
    assert r[COL_TOTAL_HOURS_NEW] == pytest.approx(38.5)    # 11+22+5.5
    assert r[COL_TOTAL_COST_ORIG] == pytest.approx(3350.0)  # 2000+100+1000+200+50
    assert r[COL_TOTAL_COST_NEW] == pytest.approx(4925.0)   # 1800+550+1200+1100+275


def test_missing_mfc_code_warns_and_keeps_cost():
    # C2 absent from MFC -> vendor shop fab factor falls back to 1.0
    out, warnings = estimate_lines(_one_line(), _mfc().iloc[:1], _lrc(), SELECTION)
    assert warnings and "C2" in warnings[0]
    r = out.iloc[0]
    assert r[COL_VENDOR_SHOP_FAB_COST_NEW] == pytest.approx(2000.0)
    # The vendor code (C2) is flagged missing; the base code (C1) is not.
    assert r[COL_VENDOR_SHOP_FAB_FACTOR_MISSING]
    assert not r[COL_BASE_MATERIAL_FACTOR_MISSING]


def test_missing_lrc_raises():
    with pytest.raises(LookupError):
        estimate_lines(_one_line(), _mfc(), _lrc().iloc[:0], SELECTION)


def test_does_not_mutate_input():
    lines = _one_line()
    estimate_lines(lines, _mfc(), _lrc(), SELECTION)
    assert COL_SPEC_H_NEW not in lines.columns


def test_run_estimation_builds_comparisons():
    project = ProjectRef("PRJ-1", "Demo", 2, 1)
    result = run_estimation(project, _one_line(), _mfc(), _lrc(), SELECTION)
    assert result.total_cost.original == pytest.approx(3350.0)
    assert result.total_cost.updated == pytest.approx(4925.0)
    assert result.total_cost.pct_change == pytest.approx((4925 - 3350) / 3350 * 100)
    assert {c.key for c in result.cost_categories} == {"spec", "vsf", "bm", "fsf", "fl"}
    assert {c.key for c in result.hour_categories} == {"spec", "fsf", "fl"}


def test_pct_change_nan_when_zero_baseline():
    from src.models import Comparison

    assert math.isnan(Comparison("k", "L", 0.0, 5.0).pct_change)
