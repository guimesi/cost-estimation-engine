"""Pre-flight EMMA coverage diagnostics.

Before the engine runs, report how well the MFC (material) reference covers a
project's line codes for a chosen ``(Location, Period)``: how many distinct
material codes have a factor, and how much databook material cost would be left
unchanged (factor ``1.0``) because its code is missing. This surfaces - and puts
a dollar figure on - the same gap the engine otherwise only reports as a
"No MFC factor for N code(s)" warning, so the user sees it before committing.

Labor (LRC) needs no per-code coverage check: the UI only offers selections
present in BOTH references, so a labor factor always exists for any selection
(see :func:`src.emma_reference.available_selections`).

Pure and read-only - mirrors the engine's own matching so the preview can't
disagree with what the run will do.
"""
from __future__ import annotations

import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_COST_ORIG,
    COL_BASE_MATERIAL_MFC,
    COL_VENDOR_SHOP_FAB_COST_ORIG,
    COL_VENDOR_SHOP_FAB_MFC,
)
from src.emma_reference import mfc_factor_map
from src.estimation_engine import blank_code_mask
from src.models import FactorSelection, MfcCoverage


def mfc_coverage(
    lines: pd.DataFrame, mfc: pd.DataFrame, selection: FactorSelection
) -> MfcCoverage:
    """Coverage of a project's material codes by the MFC reference for a selection.

    Uses the same per-code factor map the engine builds, so a code counts as
    matched here iff the engine would apply its factor (not 1.0). The unmatched
    cost sums the original base-material cost on lines whose base-material code
    is missing plus the vendor-shop-fab cost on lines whose vendor code is
    missing - the two material categories the MFC factor scales. Weighted by
    the *_ORIG engine inputs (the same values the factors multiply), never the
    DB_* reference columns.

    Lines with NO MFC code at all (NULL/blank) are a separate bucket, mirroring
    the engine (business rule 2026-07-10): they are excluded from the code
    coverage sets/costs and reported via ``no_code_lines`` /
    ``no_code_material_cost`` - their updated cost will be 0, not "unchanged".
    """
    factor_by_code = mfc_factor_map(mfc, selection.location_code, selection.period)
    covered = set(factor_by_code)

    base_codes = lines[COL_BASE_MATERIAL_MFC].astype(str)
    vsf_codes = lines[COL_VENDOR_SHOP_FAB_MFC].astype(str)
    base_blank = blank_code_mask(lines[COL_BASE_MATERIAL_MFC])
    vsf_blank = blank_code_mask(lines[COL_VENDOR_SHOP_FAB_MFC])

    used = set(base_codes[~base_blank]) | set(vsf_codes[~vsf_blank])
    matched = used & covered
    missing = sorted(used - covered)

    unmatched_material_cost = float(
        lines.loc[~base_codes.isin(covered) & ~base_blank,
                  COL_BASE_MATERIAL_COST_ORIG].sum()
        + lines.loc[~vsf_codes.isin(covered) & ~vsf_blank,
                    COL_VENDOR_SHOP_FAB_COST_ORIG].sum()
    )
    total_material_cost = float(
        lines[COL_BASE_MATERIAL_COST_ORIG].sum()
        + lines[COL_VENDOR_SHOP_FAB_COST_ORIG].sum()
    )
    no_code_material_cost = float(
        lines.loc[base_blank, COL_BASE_MATERIAL_COST_ORIG].sum()
        + lines.loc[vsf_blank, COL_VENDOR_SHOP_FAB_COST_ORIG].sum()
    )

    return MfcCoverage(
        total_codes=len(used),
        matched_codes=len(matched),
        missing_codes=missing,
        total_material_cost=total_material_cost,
        unmatched_material_cost=unmatched_material_cost,
        no_code_lines=int((base_blank | vsf_blank).sum()),
        no_code_material_cost=no_code_material_cost,
    )
