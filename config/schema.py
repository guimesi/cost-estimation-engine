"""Canonical schema: column names, ADR table names, and category definitions.

Single source of truth for every column the engine reads or writes. The
business doc uses inconsistent column labels across its calculation tables
(``DB_SPEC_S_C`` vs ``DB_SPEC_H``, ``FL_C`` for both field-labor hours and
cost, etc.); this module pins ONE canonical name per concept so the engine,
repository, mock data and UI never drift. The mapping from the real
Databricks / Excel column names to these canonical names lives in
:mod:`src.adr_repository` (ADR) and :mod:`src.emma_reference` (EMMA), so a
schema reconciliation is a one-file edit.

Naming convention (uppercase, warehouse style):
- ``*_ORIG`` -> original-estimate values from ADR (the engine's inputs and the
  "Original" side of every comparison). In the real cost table these are the
  columns WITHOUT the ``DB_`` prefix (``SPEC_S_C_COST`` etc.) - business
  correction, 2026-07-07.
- ``DB_*``  -> databook REFERENCE values from ADR. Display only (line table +
  line-level CSV); no formula reads them.
- ``*_NEW`` -> values recomputed by the engine (the "updated" estimate).
"""
from __future__ import annotations

from collections import namedtuple

# =============================================================================
# ADR source tables (Unity Catalog; names match the Snowflake originals)
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
# Original-estimate pricing context (doc v2 section 8 wants the original
# estimation's "time"; the original location is not recorded in ADR). Doc v2
# points the period at COST_BASIS, but the REAL data disagrees (verified via
# scripts/inspect_cost_basis.py, 2026-07-03): COST_UPDATE holds the clean
# quarterly period ("2Q2019"), constant per project/gate, while COST_BASIS is a
# free-text pricing-basis/scenario label ("TA"/"NTA", "Fab Yard - China", ...)
# that VARIES between items of one project. So the comparison context uses
# COST_UPDATE; COST_BASIS is carried as per-line detail only.
COL_COST_BASIS = "COST_BASIS"
COL_COST_UPDATE = "COST_UPDATE"
# Execution split the item belongs to (scope partitions like ISBL/OSBL; see
# business Q6). Users choose which splits to include in the comparison (step 2
# checkboxes, default all).
COL_EXECUTION_SPLIT = "EXECUTION_SPLIT"

# Original-estimate hours (engine inputs; raw columns WITHOUT the DB_ prefix)
COL_SPEC_H_ORIG = "SPEC_H_ORIG"                          # specialty subcontractor hours
COL_FSF_H_ORIG = "FSF_H_ORIG"                            # field shop fabrication hours
COL_FIELD_LABOR_H_ORIG = "FIELD_LABOR_H_ORIG"            # field labor hours

# Original-estimate costs (engine inputs; raw columns WITHOUT the DB_ prefix)
COL_SPEC_COST_ORIG = "SPEC_COST_ORIG"                    # specialty subcontractor cost
COL_FSF_COST_ORIG = "FSF_COST_ORIG"                      # field shop fabrication cost
COL_FIELD_LABOR_COST_ORIG = "FIELD_LABOR_COST_ORIG"      # field labor cost
COL_BASE_MATERIAL_COST_ORIG = "BASE_MATERIAL_COST_ORIG"  # base material cost
COL_VENDOR_SHOP_FAB_COST_ORIG = "VENDOR_SHOP_FAB_COST_ORIG"

# Databook REFERENCE values (raw DB_* columns). Business correction 2026-07-07:
# the DB_ prefixed columns are reference only - the engine never reads them;
# they are carried for display (line table + line-level CSV) alongside the
# *_ORIG columns that actually feed the calculation.
COL_DB_SPEC_H = "DB_SPEC_H"                  # databook specialty subcontractor hours
COL_DB_FSF_H = "DB_FSF_H"                    # databook field shop fabrication hours
COL_DB_FIELD_LABOR_H = "DB_FIELD_LABOR_H"    # databook field labor hours
COL_DB_SPEC_C = "DB_SPEC_C"                  # databook specialty subcontractor cost
COL_DB_FSF_C = "DB_FSF_C"                    # databook field shop fabrication cost
COL_DB_FIELD_LABOR_C = "DB_FIELD_LABOR_C"    # databook field labor cost
COL_DB_BM_C = "DB_BM_C"                      # databook base material cost
COL_DB_VSF_C = "DB_VSF_C"                    # databook vendor shop fabrication cost

# Material factor codes carried on each line (matched against MFC_CODE)
COL_BASE_MATERIAL_MFC = "BASE_MATERIAL_MFC"
COL_VENDOR_SHOP_FAB_MFC = "VENDOR_SHOP_FAB_MFC"

# All numeric input columns expected on the canonical line frame (engine inputs
# first, then the display-only databook reference block).
ADR_LINE_NUMERIC_COLUMNS = (
    COL_SPEC_H_ORIG, COL_FSF_H_ORIG, COL_FIELD_LABOR_H_ORIG,
    COL_SPEC_COST_ORIG, COL_FSF_COST_ORIG, COL_FIELD_LABOR_COST_ORIG,
    COL_BASE_MATERIAL_COST_ORIG, COL_VENDOR_SHOP_FAB_COST_ORIG,
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
# Per-line flags: True when the line's material code had no MFC factor for the
# selection (factor defaulted to 1.0). Distinguishes a missing factor from a
# legitimate factor that happens to equal 1.0.
COL_BASE_MATERIAL_FACTOR_MISSING = "BASE_MATERIAL_FACTOR_MISSING"
COL_VENDOR_SHOP_FAB_FACTOR_MISSING = "VENDOR_SHOP_FAB_FACTOR_MISSING"
# Per-line flags: True when the line carries NO MFC code at all (NULL/blank in
# ADR). Business rule (2026-07-10): the material calculation is not executed
# for these lines and the updated cost is 0. A different case from
# FACTOR_MISSING above (code present, EMMA factor absent -> kept at 1.0).
COL_BASE_MATERIAL_CODE_MISSING = "BASE_MATERIAL_CODE_MISSING"
COL_VENDOR_SHOP_FAB_CODE_MISSING = "VENDOR_SHOP_FAB_CODE_MISSING"

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

# Raw EMMA ingestion (Excel workbooks or the Unity Catalog tables loaded from
# them) does NOT use a fixed rename map: headers vary between the doc's
# ``MFC_*``/``LRC_*`` style and the exports' ``code``/``factorMultiplier``
# style, and the material/labor contents can arrive under either name
# (business Q8). ``src/emma_excel.py`` normalizes headers and classifies each
# frame by its columns; both the Excel and Databricks paths route through it
# onto the canonical names above.

# =============================================================================
# ADR raw -> canonical column maps (real ITPlus headers)
# =============================================================================
# The 4 ADR tables ship the real ITPlus column names (uppercased by the
# client). These maps reconcile them onto the canonical names above; applied
# per table in :func:`src.adr_repository._dbx_load_project_lines`. Reconciled against
# the live schema (see scripts/inspect_adr_schema.py).
#
# Notes:
# - The item-level join key is ``ROW_ID`` (canonical ``ITEM_ID``); the same
#   value appears on every fact table. ``ADR_ID`` is the estimate-level id
#   (planview + gate + split + ADR number) - too coarse for an item join.
# - ``ADR_DIM_ESTIMATEDESIGNDETAILS`` is an EAV table (one row per design
#   parameter) and contributes no column the engine needs, so it is NOT joined.
# - Several databook values arrive as strings ("0", "9.47"); the repository
#   coerces ADR_LINE_NUMERIC_COLUMNS to numeric after the rename.
# - Business correction (2026-07-07): the real original hours/costs are the
#   columns WITHOUT the DB_ prefix (SPEC_S_C, SPEC_S_C_COST, ...); the DB_*
#   twins are databook reference values, kept for display only. Both sets are
#   read; only the un-prefixed set feeds the engine.
ADR_ITEM_RECORD_RENAME = {
    "ROW_ID": COL_ITEM_ID,
    "PLANVIEW_ID": COL_PROJECT_ID,
    "FILE_NAME": COL_PROJECT_NAME,
    "SNAPSHOT": COL_SNAPSHOT_ID,
    "COMPLETE_WBC": COL_WBS,
    "ITEM_DESCRIPTION": COL_DESCRIPTION,
    "COST_BASIS": COL_COST_BASIS,
    "COST_UPDATE": COL_COST_UPDATE,
    "EXECUTION_SPLIT": COL_EXECUTION_SPLIT,
}
ADR_COST_RESULTS_RENAME = {
    "ROW_ID": COL_ITEM_ID,
    # Original estimate (engine inputs) - the un-prefixed columns:
    "SPEC_S_C": COL_SPEC_H_ORIG,                # specialty subcontractor HOURS
    "SPEC_S_C_COST": COL_SPEC_COST_ORIG,        # specialty subcontractor cost
    "FIELD_SHOP_FAB": COL_FSF_H_ORIG,           # field shop fab HOURS
    "FIELD_SHOP_FAB_COST": COL_FSF_COST_ORIG,   # field shop fab cost
    "FIELD_LABOR": COL_FIELD_LABOR_H_ORIG,      # field labor HOURS
    "FIELD_LABOR_COST": COL_FIELD_LABOR_COST_ORIG,
    "BASE_MATERIAL_COST": COL_BASE_MATERIAL_COST_ORIG,
    "VENDOR_SHOP_FAB_COST": COL_VENDOR_SHOP_FAB_COST_ORIG,
    # Databook reference (display only):
    "DB_SPEC_S_C": COL_DB_SPEC_H,            # databook specialty subcontractor HOURS
    "DB_SPEC_S_C_COST": COL_DB_SPEC_C,       # databook specialty subcontractor cost
    "DB_FIELD_SHOP_FAB": COL_DB_FSF_H,       # databook field shop fab HOURS
    "DB_FIELD_SHOP_FAB_COST": COL_DB_FSF_C,  # databook field shop fab cost
    "DB_FIELD_LABOR": COL_DB_FIELD_LABOR_H,  # databook field labor HOURS
    "DB_FIELD_LABOR_COST": COL_DB_FIELD_LABOR_C,
    "DB_BASE_MATERIAL_COST": COL_DB_BM_C,
    "DB_VENDOR_SHOP_FAB_COST": COL_DB_VSF_C,
    "BASE_MATERIAL_MFC": COL_BASE_MATERIAL_MFC,
    "VENDOR_SHOP_FAB_MFC": COL_VENDOR_SHOP_FAB_MFC,
}
ADR_QTY_RESULTS_RENAME = {
    "ROW_ID": COL_ITEM_ID,
    "QUANTITY": COL_QUANTITY,
}

# "Latest snapshot per project" ordering. SNAPSHOT is a stage-gate label, not a
# number, with the business priority SCREEN < GATE1 < ... < GATE3 (later gate =
# more recent estimate). Higher rank wins. Values absent here fall back to a
# numeric reading (so the mock's integer snapshots still order correctly), then
# to "lowest" for anything unrecognized.
SNAPSHOT_PRIORITY = {
    "SCREEN": 0,
    "GATE1": 1,
    "GATE2": 2,
    "GATE3": 3,
    "GATE4": 4,
    "GATE5": 5,
}

# =============================================================================
# Category definitions (drive the engine, the comparison, and the CSV)
# =============================================================================
# A cost category pairs the original-estimate column (*_ORIG, engine input)
# with the engine's recomputed (updated) column. Order matches the doc's
# breakdown. The DB_* databook reference columns deliberately do NOT appear
# here - they are display-only.
CostCategory = namedtuple("CostCategory", "key label orig_col new_col")
HourCategory = namedtuple("HourCategory", "key label orig_col new_col")

COST_CATEGORIES = (
    CostCategory("spec", "Specialty Subcontractor", COL_SPEC_COST_ORIG, COL_SPEC_COST_NEW),
    CostCategory("vsf", "Vendor Shop Fabrication", COL_VENDOR_SHOP_FAB_COST_ORIG,
                 COL_VENDOR_SHOP_FAB_COST_NEW),
    CostCategory("bm", "Base Material", COL_BASE_MATERIAL_COST_ORIG, COL_BASE_MATERIAL_COST_NEW),
    CostCategory("fsf", "Field Shop Fabrication", COL_FSF_COST_ORIG, COL_FSF_COST_NEW),
    CostCategory("fl", "Field Labor", COL_FIELD_LABOR_COST_ORIG, COL_FIELD_LABOR_COST_NEW),
)

HOUR_CATEGORIES = (
    HourCategory("spec", "Specialty Subcontractor", COL_SPEC_H_ORIG, COL_SPEC_H_NEW),
    HourCategory("fsf", "Field Shop Fabrication", COL_FSF_H_ORIG, COL_FSF_H_NEW),
    HourCategory("fl", "Field Labor", COL_FIELD_LABOR_H_ORIG, COL_FIELD_LABOR_H_NEW),
)
