"""CSV builders for the estimation result.

Two outputs:
- :func:`build_lines_csv` - the full per-line frame (databook originals +
  applied factors + updated values), the detailed project estimation file the
  doc's flow step (d) delivers.
- :func:`build_summary_csv` - the category-level original/updated/delta/%
  comparison shown on the dashboard.
"""
from __future__ import annotations

from io import StringIO

import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_COST_NEW,
    COL_BASE_MATERIAL_FACTOR,
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_BASE_MATERIAL_MFC,
    COL_COST_BASIS,
    COL_DB_BM_C,
    COL_DB_FIELD_LABOR_C,
    COL_DB_FIELD_LABOR_H,
    COL_DB_FSF_C,
    COL_DB_FSF_H,
    COL_DB_SPEC_C,
    COL_DB_SPEC_H,
    COL_DB_VSF_C,
    COL_DESCRIPTION,
    COL_FIELD_LABOR_COST_NEW,
    COL_FIELD_LABOR_H_NEW,
    COL_FSF_COST_NEW,
    COL_FSF_H_NEW,
    COL_ITEM_ID,
    COL_LRC_FACTOR,
    COL_LRC_USD_RATE,
    COL_PROJECT_ID,
    COL_QUANTITY,
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
    COL_WBS,
)
from src.models import EstimationResult

# Per-line CSV column order (identity -> databook -> applied factors -> updated).
_LINE_CSV_COLUMNS = [
    COL_PROJECT_ID, COL_ITEM_ID, COL_WBS, COL_DESCRIPTION, COL_QUANTITY,
    COL_COST_BASIS,
    # databook (original)
    COL_DB_SPEC_H, COL_DB_FSF_H, COL_DB_FIELD_LABOR_H,
    COL_DB_SPEC_C, COL_DB_FSF_C, COL_DB_FIELD_LABOR_C, COL_DB_BM_C, COL_DB_VSF_C,
    # applied factors (+ missing-MFC flags)
    COL_BASE_MATERIAL_MFC, COL_BASE_MATERIAL_FACTOR, COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_VENDOR_SHOP_FAB_MFC, COL_VENDOR_SHOP_FAB_FACTOR, COL_VENDOR_SHOP_FAB_FACTOR_MISSING,
    COL_LRC_FACTOR, COL_LRC_USD_RATE,
    # updated
    COL_SPEC_H_NEW, COL_FSF_H_NEW, COL_FIELD_LABOR_H_NEW,
    COL_SPEC_COST_NEW, COL_FSF_COST_NEW, COL_FIELD_LABOR_COST_NEW,
    COL_BASE_MATERIAL_COST_NEW, COL_VENDOR_SHOP_FAB_COST_NEW,
    COL_TOTAL_HOURS_ORIG, COL_TOTAL_HOURS_NEW,
    COL_TOTAL_COST_ORIG, COL_TOTAL_COST_NEW,
]


def build_lines_csv(result: EstimationResult) -> str:
    """Return the full per-line estimation file as CSV text."""
    present = [c for c in _LINE_CSV_COLUMNS if c in result.lines.columns]
    return result.lines[present].to_csv(index=False)


def build_summary_csv(result: EstimationResult) -> str:
    """Return the category-level comparison (cost + hours) as CSV text.

    Carries both estimation contexts (doc v2 section 8): the original's
    COST_BASIS period (its location is not recorded in ADR) and the new
    estimation's location + period.
    """
    rows = []
    for cmp in result.cost_categories + [result.total_cost]:
        rows.append(_summary_row("Cost", cmp, result))
    for cmp in result.hour_categories + [result.total_hours]:
        rows.append(_summary_row("Hours", cmp, result))
    frame = pd.DataFrame(rows)
    buf = StringIO()
    frame.to_csv(buf, index=False)
    return buf.getvalue()


def _summary_row(measure: str, cmp, result: EstimationResult) -> dict:
    return {
        "MEASURE": measure,
        "CATEGORY": cmp.label,
        "ORIGINAL_BASIS": result.original_basis,
        "NEW_LOCATION_PERIOD": result.selection.label,
        "ORIGINAL": round(cmp.original, 2),
        "UPDATED": round(cmp.updated, 2),
        "DELTA": round(cmp.delta, 2),
        "PCT_CHANGE": (None if pd.isna(cmp.pct_change) else round(cmp.pct_change, 2)),
    }
