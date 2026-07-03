"""The estimation engine: re-estimate ADR databook lines with EMMA factors.

Given a project's canonical line frame plus the user's (Location, Period)
selection, this recomputes every cost/hour category and the totals, then
assembles an :class:`EstimationResult` with original-vs-updated comparisons.

Calculation rules (from the business doc, with the two confirmed readings):

Labor (LRC factor ``F`` + USD rate ``USD_R`` for the selected location/period,
applied to ALL THREE labor categories - Specialty Subcontractor, Field Shop
Fabrication and Field Labor):
    SPEC_H_NEW         = DB_SPEC_H        * F   SPEC_COST_NEW        = SPEC_H_NEW        * USD_R
    FSF_H_NEW          = DB_FSF_H         * F   FSF_COST_NEW         = FSF_H_NEW         * USD_R
    FIELD_LABOR_H_NEW  = DB_FIELD_LABOR_H * F   FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R

Material (MFC factor matched per line code, location, period):
    BASE_MATERIAL_COST_NEW    = DB_BM_C  * F_mfc[BASE_MATERIAL_MFC]
    VENDOR_SHOP_FAB_COST_NEW  = DB_VSF_C * F_mfc[VENDOR_SHOP_FAB_MFC]

Totals:
    TOTAL_HOURS_NEW = SPEC_H_NEW + FSF_H_NEW + FIELD_LABOR_H_NEW
    TOTAL_COST_NEW  = VENDOR_SHOP_FAB_COST_NEW + SPEC_COST_NEW
                      + BASE_MATERIAL_COST_NEW + FSF_COST_NEW + FIELD_LABOR_COST_NEW

A missing MFC factor for a line's code is treated as factor ``1.0`` (cost
unchanged) and recorded as a warning, never silently dropped. A missing LRC
factor for the selection raises ``LookupError`` - the UI only offers
selections present in both references, so this is a guard, not a normal path.
"""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_COST_NEW,
    COL_BASE_MATERIAL_FACTOR,
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_BASE_MATERIAL_MFC,
    COL_COST_BASIS,
    COL_DB_BM_C,
    COL_DB_FIELD_LABOR_H,
    COL_DB_FSF_H,
    COL_DB_SPEC_H,
    COL_DB_VSF_C,
    COL_FIELD_LABOR_COST_NEW,
    COL_FIELD_LABOR_H_NEW,
    COL_FSF_COST_NEW,
    COL_FSF_H_NEW,
    COL_LRC_FACTOR,
    COL_LRC_USD_RATE,
    COL_SPEC_COST_NEW,
    COL_SPEC_H_NEW,
    COL_TOTAL_COST_NEW,
    COL_TOTAL_COST_ORIG,
    COL_TOTAL_HOURS_NEW,
    COL_TOTAL_HOURS_ORIG,
    COL_VENDOR_SHOP_FAB_COST_NEW,
    COL_VENDOR_SHOP_FAB_FACTOR,
    COL_VENDOR_SHOP_FAB_FACTOR_MISSING,
    COL_VENDOR_SHOP_FAB_MFC,
    COST_CATEGORIES,
    HOUR_CATEGORIES,
)
from src.emma_reference import lrc_lookup, mfc_factor_map
from src.models import Comparison, EstimationResult, FactorSelection, ProjectRef


def estimate_lines(
    lines: pd.DataFrame,
    mfc: pd.DataFrame,
    lrc: pd.DataFrame,
    selection: FactorSelection,
) -> Tuple[pd.DataFrame, List[str]]:
    """Return ``(lines_with_updated_columns, warnings)``.

    Pure and vectorized: does not mutate the input frame.
    """
    df = lines.copy()
    warnings: List[str] = []

    lrc_match = lrc_lookup(lrc, selection.location_code, selection.period)
    if lrc_match is None:
        raise LookupError(
            f"No LRC labor factor for {selection.location_code} / {selection.period}"
        )
    f_lrc, usd_rate = lrc_match

    # --- Labor: Specialty Subcontractor + Field Shop Fabrication + Field Labor ---
    # All three labor categories use the same LRC multiplier F and USD rate.
    df[COL_LRC_FACTOR] = f_lrc
    df[COL_LRC_USD_RATE] = usd_rate
    df[COL_SPEC_H_NEW] = df[COL_DB_SPEC_H] * f_lrc
    df[COL_SPEC_COST_NEW] = df[COL_SPEC_H_NEW] * usd_rate
    df[COL_FSF_H_NEW] = df[COL_DB_FSF_H] * f_lrc
    df[COL_FSF_COST_NEW] = df[COL_FSF_H_NEW] * usd_rate
    df[COL_FIELD_LABOR_H_NEW] = df[COL_DB_FIELD_LABOR_H] * f_lrc
    df[COL_FIELD_LABOR_COST_NEW] = df[COL_FIELD_LABOR_H_NEW] * usd_rate

    # --- Material: Base Material + Vendor Shop Fabrication (MFC per code) ---
    factor_by_code = mfc_factor_map(mfc, selection.location_code, selection.period)

    df[COL_BASE_MATERIAL_FACTOR] = df[COL_BASE_MATERIAL_MFC].map(factor_by_code)
    df[COL_VENDOR_SHOP_FAB_FACTOR] = df[COL_VENDOR_SHOP_FAB_MFC].map(factor_by_code)

    # Flag the lines whose factor is missing (NaN) BEFORE defaulting to 1.0, so a
    # missing factor is distinguishable from a real factor that equals 1.0.
    df[COL_BASE_MATERIAL_FACTOR_MISSING] = df[COL_BASE_MATERIAL_FACTOR].isna()
    df[COL_VENDOR_SHOP_FAB_FACTOR_MISSING] = df[COL_VENDOR_SHOP_FAB_FACTOR].isna()

    missing = _collect_missing_codes(df, factor_by_code)
    if missing:
        warnings.append(
            "No MFC factor for "
            f"{len(missing)} material code(s) at {selection.location_name} / "
            f"{selection.period}; cost left unchanged (factor 1.0): "
            f"{', '.join(sorted(missing))}"
        )
    df[COL_BASE_MATERIAL_FACTOR] = df[COL_BASE_MATERIAL_FACTOR].fillna(1.0)
    df[COL_VENDOR_SHOP_FAB_FACTOR] = df[COL_VENDOR_SHOP_FAB_FACTOR].fillna(1.0)

    df[COL_BASE_MATERIAL_COST_NEW] = df[COL_DB_BM_C] * df[COL_BASE_MATERIAL_FACTOR]
    df[COL_VENDOR_SHOP_FAB_COST_NEW] = df[COL_DB_VSF_C] * df[COL_VENDOR_SHOP_FAB_FACTOR]

    # --- Totals (per line) ---
    df[COL_TOTAL_HOURS_ORIG] = sum(df[c.orig_col] for c in HOUR_CATEGORIES)
    df[COL_TOTAL_HOURS_NEW] = sum(df[c.new_col] for c in HOUR_CATEGORIES)
    df[COL_TOTAL_COST_ORIG] = sum(df[c.orig_col] for c in COST_CATEGORIES)
    df[COL_TOTAL_COST_NEW] = sum(df[c.new_col] for c in COST_CATEGORIES)

    return df, warnings


def _collect_missing_codes(df: pd.DataFrame, factor_by_code: dict) -> set:
    """Material codes present on lines but absent from the factor map."""
    used = set(df[COL_BASE_MATERIAL_MFC]) | set(df[COL_VENDOR_SHOP_FAB_MFC])
    return {str(code) for code in used if code not in factor_by_code}


def _original_basis(lines: pd.DataFrame) -> str:
    """Time period the original databook estimate was priced at (``COST_BASIS``).

    ADR carries one basis per estimate; the most frequent non-blank value wins
    so a stray blank row can't hide it. ``"n/a"`` when absent - the comparison
    then shows the original context as unknown rather than failing.
    """
    if COL_COST_BASIS not in lines.columns:
        return "n/a"
    vals = lines[COL_COST_BASIS].dropna().astype(str).str.strip()
    vals = vals[(vals != "") & (vals.str.lower() != "nan")]
    if vals.empty:
        return "n/a"
    return str(vals.mode().iat[0])


def run_estimation(
    project: ProjectRef,
    lines: pd.DataFrame,
    mfc: pd.DataFrame,
    lrc: pd.DataFrame,
    selection: FactorSelection,
) -> EstimationResult:
    """Run the full re-estimation and assemble an :class:`EstimationResult`."""
    out, warnings = estimate_lines(lines, mfc, lrc, selection)

    cost_cmps = [
        Comparison(c.key, c.label, float(out[c.orig_col].sum()), float(out[c.new_col].sum()))
        for c in COST_CATEGORIES
    ]
    hour_cmps = [
        Comparison(c.key, c.label, float(out[c.orig_col].sum()), float(out[c.new_col].sum()))
        for c in HOUR_CATEGORIES
    ]
    total_cost = Comparison(
        "total_cost", "Total Cost",
        float(out[COL_TOTAL_COST_ORIG].sum()), float(out[COL_TOTAL_COST_NEW].sum()),
    )
    total_hours = Comparison(
        "total_hours", "Total Hours",
        float(out[COL_TOTAL_HOURS_ORIG].sum()), float(out[COL_TOTAL_HOURS_NEW].sum()),
    )
    return EstimationResult(
        project=project,
        selection=selection,
        lines=out,
        cost_categories=cost_cmps,
        hour_categories=hour_cmps,
        total_cost=total_cost,
        total_hours=total_hours,
        warnings=warnings,
        original_basis=_original_basis(lines),
    )
