"""Pre-flight MFC coverage diagnostics."""
from __future__ import annotations

import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_COST_ORIG,
    COL_BASE_MATERIAL_MFC,
    COL_VENDOR_SHOP_FAB_COST_ORIG,
    COL_VENDOR_SHOP_FAB_MFC,
    MFC_CODE,
    MFC_FACTOR_VALUE,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
)
from src.diagnostics import mfc_coverage
from src.models import FactorSelection

_SEL = FactorSelection(location_code="L1", location_name="Loc 1", period="P1")


def _lines() -> pd.DataFrame:
    # Row 0 uses codes A (base) + C (vendor); row 1 uses B (base) + A (vendor).
    return pd.DataFrame(
        {
            COL_BASE_MATERIAL_MFC: ["A", "B"],
            COL_VENDOR_SHOP_FAB_MFC: ["C", "A"],
            COL_BASE_MATERIAL_COST_ORIG: [100.0, 200.0],
            COL_VENDOR_SHOP_FAB_COST_ORIG: [10.0, 20.0],
        }
    )


def _mfc(codes) -> pd.DataFrame:
    return pd.DataFrame(
        {
            MFC_CODE: list(codes),
            MFC_LOCATION_CODE: ["L1"] * len(codes),
            MFC_PERIOD: ["P1"] * len(codes),
            MFC_FACTOR_VALUE: [1.1] * len(codes),
        }
    )


def test_full_coverage():
    cov = mfc_coverage(_lines(), _mfc(["A", "B", "C"]), _SEL)
    assert cov.total_codes == 3            # distinct: A, B, C
    assert cov.matched_codes == 3
    assert cov.is_fully_covered
    assert cov.missing_codes == []
    assert cov.unmatched_material_cost == 0.0
    assert cov.matched_pct == 100.0
    assert cov.unmatched_cost_pct == 0.0


def test_partial_coverage_sums_only_missing_code_cost():
    # Drop C: it appears as the vendor code on row 0 (VENDOR_SHOP_FAB_COST_ORIG = 10).
    cov = mfc_coverage(_lines(), _mfc(["A", "B"]), _SEL)
    assert cov.total_codes == 3
    assert cov.matched_codes == 2
    assert cov.missing_codes == ["C"]
    assert cov.unmatched_material_cost == 10.0
    assert not cov.is_fully_covered


def test_blank_codes_are_a_separate_bucket_not_missing_codes():
    # Row 0 loses its base code (NULL in ADR): it is NOT a reference gap - the
    # engine zeroes it - so coverage reports it via the no_code_* fields.
    lines = _lines()
    lines.loc[0, COL_BASE_MATERIAL_MFC] = None
    cov = mfc_coverage(lines, _mfc(["A", "B", "C"]), _SEL)
    assert cov.missing_codes == []          # A/B/C all still covered
    assert cov.total_codes == 3             # blank not counted as a code
    assert cov.no_code_lines == 1
    assert cov.no_code_material_cost == 100.0  # row 0 base-material cost
    assert cov.unmatched_material_cost == 0.0


def test_wrong_period_misses_everything():
    other = FactorSelection(location_code="L1", location_name="Loc 1", period="P2")
    cov = mfc_coverage(_lines(), _mfc(["A", "B", "C"]), other)
    assert cov.matched_codes == 0
    assert cov.missing_codes == ["A", "B", "C"]
    # All base + vendor original material cost is left unchanged.
    assert cov.unmatched_material_cost == 330.0
    assert cov.unmatched_cost_pct == 100.0
