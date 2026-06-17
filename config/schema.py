"""Canonical schema: column names, ADR table names, and category definitions.

Single source of truth for every column the engine reads or writes. The
business doc uses inconsistent column labels across its calculation tables
(``DB_SPEC_S_C`` vs ``DB_SPEC_H``, ``FL_C`` for both field-labor hours and
cost, etc.); this module pins ONE canonical name per concept so the engine,
repository, mock data and UI never drift. The mapping from the real
Snowflake / Excel column names to these canonical names lives in
:mod:`src.adr_repository` (ADR) and :mod:`src.emma_reference` (EMMA), so a
schema reconciliation is a one-file edit.

Naming convention (uppercase, Snowflake style):
- ``DB_*``  -> databook baseline values from ADR (the "original" estimate).
- ``*_NEW`` -> values recomputed by the engine (the "updated" estimate).
"""
from __future__ import annotations

from collections import namedtuple

# =============================================================================
# ADR source tables (Snowflake)
# =============================================================================
TBL_ITEM_RECORD = "ADR_DIM_ESTIMATEITEMRECORD"
TBL_DESIGN_DETAILS = "ADR_DIM_ESTIMATEDESIGNDETAILS"
TBL_COST_RESULTS = "ADR_FACT_ESTIMATECOSTRESULTS"
TBL_QTY_RESULTS = "ADR_FACT_ESTIMATEQTYRESULTS"
ADR_TABLES = (TBL_ITEM_RECORD, TBL_DESIGN_DETAILS, TBL_COST_RESULTS, TBL_QTY_RESULTS)

# =============================================================================
# Canonical ADR line-item columns (the joined per-item frame)
# =============================================================================
COL_PROJECT_ID = "PROJECT_ID"
COL_PROJECT_NAME = "PROJECT_NAME"
COL_SNAPSHOT_ID = "SNAPSHOT_ID"
COL_ITEM_ID = "ITEM_ID"
COL_WBS = "WBS_CODE"
COL_DESCRIPTION = "DESCRIPTION"
COL_QUANTITY = "QUANTITY"

# Databook (original) hours
COL_DB_SPEC_H = "DB_SPEC_H"                  # specialty subcontractor hours
COL_DB_FSF_H = "DB_FSF_H"                    # field shop fabrication hours
COL_DB_FIELD_LABOR_H = "DB_FIELD_LABOR_H"    # field labor hours (pass-through)

# Databook (original) costs
COL_DB_SPEC_C = "DB_SPEC_C"                  # specialty subcontractor cost
COL_DB_FSF_C = "DB_FSF_C"                    # field shop fabrication cost
COL_DB_FIELD_LABOR_C = "DB_FIELD_LABOR_C"    # field labor cost (pass-through)
COL_DB_BM_C = "DB_BM_C"                      # base material cost
COL_DB_VSF_C = "DB_VSF_C"                    # vendor shop fabrication cost

# Material factor codes carried on each line (matched against MFC_CODE)
COL_BASE_MATERIAL_MFC = "BASE_MATERIAL_MFC"
COL_VENDOR_SHOP_FAB_MFC = "VENDOR_SHOP_FAB_MFC"

# All databook input columns expected on the canonical line frame.
ADR_LINE_NUMERIC_COLUMNS = (
    COL_DB_SPEC_H, COL_DB_FSF_H, COL_DB_FIELD_LABOR_H,
    COL_DB_SPEC_C, COL_DB_FSF_C, COL_DB_FIELD_LABOR_C,
    COL_DB_BM_C, COL_DB_VSF_C,
    COL_QUANTITY,
)

# =============================================================================
# Engine output columns (added by src.estimation_engine)
# =============================================================================
# Updated hours
COL_SPEC_H_NEW = "SPEC_H_NEW"
COL_FSF_H_NEW = "FSF_H_NEW"
COL_FIELD_LABOR_H_NEW = "FIELD_LABOR_H_NEW"
# Updated costs
COL_SPEC_COST_NEW = "SPEC_COST_NEW"
COL_FSF_COST_NEW = "FSF_COST_NEW"
COL_FIELD_LABOR_COST_NEW = "FIELD_LABOR_COST_NEW"
COL_BASE_MATERIAL_COST_NEW = "BASE_MATERIAL_COST_NEW"
COL_VENDOR_SHOP_FAB_COST_NEW = "VENDOR_SHOP_FAB_COST_NEW"
# Totals
COL_TOTAL_HOURS_ORIG = "TOTAL_HOURS_ORIG"
COL_TOTAL_HOURS_NEW = "TOTAL_HOURS_NEW"
COL_TOTAL_COST_ORIG = "TOTAL_COST_ORIG"
COL_TOTAL_COST_NEW = "TOTAL_COST_NEW"
# Applied-factor diagnostics (per line)
COL_LRC_FACTOR = "LRC_FACTOR"
COL_LRC_USD_RATE = "LRC_USD_RATE"
COL_BASE_MATERIAL_FACTOR = "BASE_MATERIAL_FACTOR"
COL_VENDOR_SHOP_FAB_FACTOR = "VENDOR_SHOP_FAB_FACTOR"

# =============================================================================
# EMMA reference columns (canonical, post-ingestion)
# =============================================================================
# Material Factor Code (MFC)
MFC_CODE = "MFC_CODE"
MFC_LOCATION = "MFC_LOCATION"
MFC_LOCATION_CODE = "MFC_LOCATION_CODE"
MFC_DESCRIPTION = "MFC_DESCRIPTION"
MFC_FACTOR_VALUE = "MFC_FACTOR_VALUE"
MFC_PERIOD = "MFC_PERIOD"

# Labor Rate Code (LRC)
LRC_LOCATION = "LRC_LOCATION"
LRC_LOCATION_CODE = "LRC_LOCATION_CODE"
LRC_FACTOR_MULTIPLIER = "LRC_FACTOR_MULTIPLIER"
LRC_PERIOD = "LRC_PERIOD"
LRC_TOTAL_USD_RATE = "LRC_TOTAL_USD_RATE"

# Raw -> canonical column rename maps for Snowflake / Excel ingestion. The
# doc's MFC.xlsx / LRC.xlsx headers map onto the canonical names above.
MFC_RAW_RENAME = {
    "MFC_LOCATION": MFC_LOCATION,
    "MFC_LOCATIONCODE": MFC_LOCATION_CODE,
    "MFC_CODE": MFC_CODE,
    "MFC_DESCRIPTION": MFC_DESCRIPTION,
    "MFC_FACTORVALUE": MFC_FACTOR_VALUE,
    "MFC_COSTUPDATEREPORTINGPERIOD_NAME": MFC_PERIOD,
}
LRC_RAW_RENAME = {
    "LRC_LOCATION": LRC_LOCATION,
    "LRC_LOCATIONCODE": LRC_LOCATION_CODE,
    "LRC_FACTORMULTIPLIER": LRC_FACTOR_MULTIPLIER,
    "LRC_COSTUPDATEREPORTINGPERIOD_NAME": LRC_PERIOD,
    "LRC_TOTALUSDRATE": LRC_TOTAL_USD_RATE,
}

# =============================================================================
# Category definitions (drive the engine, the comparison, and the CSV)
# =============================================================================
# A cost category pairs the databook (original) column with the engine's
# recomputed (updated) column. Order matches the doc's breakdown.
CostCategory = namedtuple("CostCategory", "key label orig_col new_col")
HourCategory = namedtuple("HourCategory", "key label orig_col new_col")

COST_CATEGORIES = (
    CostCategory("spec", "Specialty Subcontractor", COL_DB_SPEC_C, COL_SPEC_COST_NEW),
    CostCategory("vsf", "Vendor Shop Fabrication", COL_DB_VSF_C, COL_VENDOR_SHOP_FAB_COST_NEW),
    CostCategory("bm", "Base Material", COL_DB_BM_C, COL_BASE_MATERIAL_COST_NEW),
    CostCategory("fsf", "Field Shop Fabrication", COL_DB_FSF_C, COL_FSF_COST_NEW),
    CostCategory("fl", "Field Labor", COL_DB_FIELD_LABOR_C, COL_FIELD_LABOR_COST_NEW),
)

HOUR_CATEGORIES = (
    HourCategory("spec", "Specialty Subcontractor", COL_DB_SPEC_H, COL_SPEC_H_NEW),
    HourCategory("fsf", "Field Shop Fabrication", COL_DB_FSF_H, COL_FSF_H_NEW),
    HourCategory("fl", "Field Labor", COL_DB_FIELD_LABOR_H, COL_FIELD_LABOR_H_NEW),
)
