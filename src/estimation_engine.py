"""The estimation engine: re-estimate ADR original lines with EMMA factors.

Given a project's canonical line frame plus the user's (Location, Period)
selection, this recomputes every cost/hour category and the totals, then
assembles an :class:`EstimationResult` with original-vs-updated comparisons.

The inputs are the ``*_ORIG`` columns - the real original hours/costs, which
in the ADR cost table are the columns WITHOUT the ``DB_`` prefix (business
correction, 2026-07-07). The ``DB_*`` databook columns are reference values
carried for display only; no formula reads them.

Calculation rules (from the business doc, with the confirmed readings):

Labor (LRC factor ``F`` + USD rate ``USD_R`` for the selected location/period,
applied to ALL THREE labor categories - Specialty Subcontractor, Field Shop
Fabrication and Field Labor):
    SPEC_H_NEW         = SPEC_H_ORIG        * F   SPEC_COST_NEW        = SPEC_H_NEW        * USD_R
    FSF_H_NEW          = FSF_H_ORIG         * F   FSF_COST_NEW         = FSF_H_NEW         * USD_R
    FIELD_LABOR_H_NEW  = FIELD_LABOR_H_ORIG * F   FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R

Material (MFC factor matched per line code, location, period):
    BASE_MATERIAL_COST_NEW    = BASE_MATERIAL_COST_ORIG   * F_mfc[BASE_MATERIAL_MFC]
    VENDOR_SHOP_FAB_COST_NEW  = VENDOR_SHOP_FAB_COST_ORIG * F_mfc[VENDOR_SHOP_FAB_MFC]

Totals:
    TOTAL_HOURS_NEW = SPEC_H_NEW + FSF_H_NEW + FIELD_LABOR_H_NEW
    TOTAL_COST_NEW  = VENDOR_SHOP_FAB_COST_NEW + SPEC_COST_NEW
                      + BASE_MATERIAL_COST_NEW + FSF_COST_NEW + FIELD_LABOR_COST_NEW

Two distinct "no MFC" cases (do not conflate them):

- **Line has NO MFC code** (NULL/blank in ADR): the material calculation is
  not executed and the updated cost is **0** (business rule, 2026-07-10).
  Flagged per line via ``*_CODE_MISSING`` + a warning.
- **Line has a code but EMMA has no factor** for the selection: factor
  ``1.0`` (cost unchanged), flagged per line via ``*_FACTOR_MISSING`` + a
  warning, never silently dropped (business Q3, 2026-06-19).

A missing LRC factor for the selection raises ``LookupError`` - the UI only
offers selections present in both references, so this is a guard, not a
normal path.
"""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_CODE_MISSING,
    COL_BASE_MATERIAL_COST_NEW,
    COL_BASE_MATERIAL_COST_ORIG,
    COL_BASE_MATERIAL_FACTOR,
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_BASE_MATERIAL_MFC,
    COL_COST_UPDATE,
    COL_FIELD_LABOR_COST_NEW,
    COL_FIELD_LABOR_H_NEW,
    COL_FIELD_LABOR_H_ORIG,
    COL_FSF_COST_NEW,
    COL_FSF_H_NEW,
    COL_FSF_H_ORIG,
    COL_LRC_FACTOR,
    COL_LRC_USD_RATE,
    COL_SPEC_COST_NEW,
    COL_SPEC_H_NEW,
    COL_SPEC_H_ORIG,
    COL_TOTAL_COST_NEW,
    COL_TOTAL_COST_ORIG,
    COL_TOTAL_HOURS_NEW,
    COL_TOTAL_HOURS_ORIG,
    COL_VENDOR_SHOP_FAB_CODE_MISSING,
    COL_VENDOR_SHOP_FAB_COST_NEW,
    COL_VENDOR_SHOP_FAB_COST_ORIG,
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
    df[COL_SPEC_H_NEW] = df[COL_SPEC_H_ORIG] * f_lrc
    df[COL_SPEC_COST_NEW] = df[COL_SPEC_H_NEW] * usd_rate
    df[COL_FSF_H_NEW] = df[COL_FSF_H_ORIG] * f_lrc
    df[COL_FSF_COST_NEW] = df[COL_FSF_H_NEW] * usd_rate
    df[COL_FIELD_LABOR_H_NEW] = df[COL_FIELD_LABOR_H_ORIG] * f_lrc
    df[COL_FIELD_LABOR_COST_NEW] = df[COL_FIELD_LABOR_H_NEW] * usd_rate

    # --- Material: Base Material + Vendor Shop Fabrication (MFC per code) ---
    factor_by_code = mfc_factor_map(mfc, selection.location_code, selection.period)

    # Lines with NO MFC code at all (NULL/blank in ADR): the calculation is not
    # executed and the updated cost is 0 (business rule, 2026-07-10). Flagged
    # separately from the factor-missing case below.
    base_blank = blank_code_mask(df[COL_BASE_MATERIAL_MFC])
    vsf_blank = blank_code_mask(df[COL_VENDOR_SHOP_FAB_MFC])
    df[COL_BASE_MATERIAL_CODE_MISSING] = base_blank
    df[COL_VENDOR_SHOP_FAB_CODE_MISSING] = vsf_blank
    # The warning carries the zeroed ORIGINAL cost so it is self-evident when
    # the rule cannot move the totals (no-code lines often hold zero cost).
    for mask, col_name, cost_col in (
        (base_blank, COL_BASE_MATERIAL_MFC, COL_BASE_MATERIAL_COST_ORIG),
        (vsf_blank, COL_VENDOR_SHOP_FAB_MFC, COL_VENDOR_SHOP_FAB_COST_ORIG),
    ):
        if mask.any():
            zeroed = float(df.loc[mask, cost_col].sum())
            warnings.append(
                f"{int(mask.sum())} line(s) have no {col_name} code; their "
                "updated cost for that category is 0 (calculation not "
                f"executed). Original cost on those lines: {zeroed:,.2f}."
            )

    df[COL_BASE_MATERIAL_FACTOR] = df[COL_BASE_MATERIAL_MFC].map(factor_by_code)
    df[COL_VENDOR_SHOP_FAB_FACTOR] = df[COL_VENDOR_SHOP_FAB_MFC].map(factor_by_code)

    # Flag the lines whose CODE exists but has no factor (NaN) BEFORE defaulting
    # to 1.0, so a missing factor is distinguishable from a real factor that
    # equals 1.0. Blank-code lines are the CODE_MISSING case, not this one.
    df[COL_BASE_MATERIAL_FACTOR_MISSING] = df[COL_BASE_MATERIAL_FACTOR].isna() & ~base_blank
    df[COL_VENDOR_SHOP_FAB_FACTOR_MISSING] = (
        df[COL_VENDOR_SHOP_FAB_FACTOR].isna() & ~vsf_blank
    )

    missing = _collect_missing_codes(df, factor_by_code, base_blank, vsf_blank)
    if missing:
        warnings.append(
            "No MFC factor for "
            f"{len(missing)} material code(s) at {selection.location_name} / "
            f"{selection.period}; cost left unchanged (factor 1.0): "
            f"{', '.join(sorted(missing))}"
        )
    df[COL_BASE_MATERIAL_FACTOR] = df[COL_BASE_MATERIAL_FACTOR].fillna(1.0)
    df[COL_VENDOR_SHOP_FAB_FACTOR] = df[COL_VENDOR_SHOP_FAB_FACTOR].fillna(1.0)
    # Blank-code lines: factor 0 -> updated cost 0 (rule above). Applied AFTER
    # the 1.0 fill so it always wins for those lines.
    df.loc[base_blank, COL_BASE_MATERIAL_FACTOR] = 0.0
    df.loc[vsf_blank, COL_VENDOR_SHOP_FAB_FACTOR] = 0.0

    df[COL_BASE_MATERIAL_COST_NEW] = (
        df[COL_BASE_MATERIAL_COST_ORIG] * df[COL_BASE_MATERIAL_FACTOR]
    )
    df[COL_VENDOR_SHOP_FAB_COST_NEW] = (
        df[COL_VENDOR_SHOP_FAB_COST_ORIG] * df[COL_VENDOR_SHOP_FAB_FACTOR]
    )

    # --- Totals (per line) ---
    df[COL_TOTAL_HOURS_ORIG] = sum(df[c.orig_col] for c in HOUR_CATEGORIES)
    df[COL_TOTAL_HOURS_NEW] = sum(df[c.new_col] for c in HOUR_CATEGORIES)
    df[COL_TOTAL_COST_ORIG] = sum(df[c.orig_col] for c in COST_CATEGORIES)
    df[COL_TOTAL_COST_NEW] = sum(df[c.new_col] for c in COST_CATEGORIES)

    return df, warnings


def blank_code_mask(codes: pd.Series) -> pd.Series:
    """True where the line carries no usable MFC code (NULL/blank in ADR)."""
    text = codes.astype(str).str.strip().str.lower()
    return codes.isna() | text.isin(("", "nan", "none", "null"))


def _collect_missing_codes(
    df: pd.DataFrame, factor_by_code: dict,
    base_blank: pd.Series, vsf_blank: pd.Series,
) -> set:
    """Material codes present on lines but absent from the factor map.

    Blank/NULL codes are excluded - they are the CODE_MISSING (cost 0) case,
    not a reference gap.
    """
    used = (
        set(df.loc[~base_blank, COL_BASE_MATERIAL_MFC])
        | set(df.loc[~vsf_blank, COL_VENDOR_SHOP_FAB_MFC])
    )
    return {str(code) for code in used if code not in factor_by_code}


def _original_period(lines: pd.DataFrame) -> str:
    """Time period the original databook estimate was priced at (``COST_UPDATE``).

    Doc v2 points this at ``COST_BASIS``, but the real data disagrees:
    ``COST_UPDATE`` holds the clean quarterly period ("2Q2019"), constant per
    project/gate, while ``COST_BASIS`` is a per-line scenario label. The most
    frequent non-blank value wins so a stray blank row can't hide it. ``"n/a"``
    when absent - the comparison then shows the original context as unknown
    rather than failing.
    """
    if COL_COST_UPDATE not in lines.columns:
        return "n/a"
    vals = lines[COL_COST_UPDATE].dropna().astype(str).str.strip()
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
        original_period=_original_period(lines),
    )
