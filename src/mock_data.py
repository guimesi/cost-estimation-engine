"""Deterministic synthetic data for the ``mock`` data source.

Builds a small but realistic ADR estimate dataset (the 4 source tables) plus
the EMMA reference data (MFC material factors and LRC labor factors), so the
whole app runs end-to-end with no Snowflake connection.

Determinism contract (carried over from the sibling data-quality-app): every
frame is built ONCE at import with a dedicated, fixed-seed RNG and fixed
iteration order, so the byte content is identical on every call regardless of
order - scores never drift run-to-run. ``fetch_mock_table`` and the EMMA
builders just return slices/copies of these import-time frames.

These are MODELING CHOICES, not the real schema: the doc names the 4 ADR
tables but not their exact columns, so the split below (item record / design
details / cost results / qty results) is a reasonable reconstruction. The
real column names are reconciled in :mod:`src.adr_repository` /
:mod:`src.emma_reference` without touching the engine.
"""
from __future__ import annotations

import zlib
from typing import Dict, List

import numpy as np
import pandas as pd

from config.schema import (
    COL_BASE_MATERIAL_COST_ORIG,
    COL_BASE_MATERIAL_MFC,
    COL_COST_BASIS,
    COL_COST_UPDATE,
    COL_DB_BM_C,
    COL_DB_FIELD_LABOR_C,
    COL_DB_FIELD_LABOR_H,
    COL_DB_FSF_C,
    COL_DB_FSF_H,
    COL_DB_SPEC_C,
    COL_DB_SPEC_H,
    COL_DB_VSF_C,
    COL_DESCRIPTION,
    COL_EXECUTION_SPLIT,
    COL_FIELD_LABOR_COST_ORIG,
    COL_FIELD_LABOR_H_ORIG,
    COL_FSF_COST_ORIG,
    COL_FSF_H_ORIG,
    COL_ITEM_ID,
    COL_PROJECT_ID,
    COL_PROJECT_NAME,
    COL_QUANTITY,
    COL_SNAPSHOT_ID,
    COL_SPEC_COST_ORIG,
    COL_SPEC_H_ORIG,
    COL_VENDOR_SHOP_FAB_COST_ORIG,
    COL_VENDOR_SHOP_FAB_MFC,
    COL_WBS,
    LRC_FACTOR_MULTIPLIER,
    LRC_LOCATION,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    LRC_TOTAL_USD_RATE,
    MFC_CODE,
    MFC_DESCRIPTION,
    MFC_FACTOR_VALUE,
    MFC_LOCATION,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
    TBL_COST_RESULTS,
    TBL_DESIGN_DETAILS,
    TBL_ITEM_RECORD,
    TBL_QTY_RESULTS,
)

# =============================================================================
# Reference dimensions (shared keys between ADR lines and EMMA factors)
# =============================================================================
# (location_code, location_name)
LOCATIONS: List[tuple] = [
    ("USTX", "Houston, TX, USA"),
    ("SGP", "Singapore"),
    ("NLD", "Rotterdam, NL"),
]
PERIODS: List[str] = ["2024-H1", "2024-H2", "2025-H1"]

# Material Factor Codes referenced by ADR lines (base material + vendor shop fab).
MFC_CODES: Dict[str, str] = {
    "STEEL-CS": "Carbon steel structural",
    "STEEL-SS": "Stainless steel structural",
    "PIPE-CS": "Carbon steel piping",
    "VALVE-GATE": "Gate valves",
    "INSTR-XMTR": "Instrumentation transmitters",
    "ELEC-CABLE": "Electrical cable",
}

# Per-location base USD labor rate; period applies a small escalation.
_LOCATION_BASE_RATE = {"USTX": 65.0, "SGP": 48.0, "NLD": 72.0}
_PERIOD_ESCALATION = {"2024-H1": 1.00, "2024-H2": 1.03, "2025-H1": 1.07}

# Projects with ADR estimations loaded. Each gets an older snapshot (1) and a
# latest snapshot (2); the repository selects the latest per project.
_PROJECTS: List[tuple] = [
    ("PRJ-1001", "Coker Unit Revamp"),
    ("PRJ-1002", "LNG Train 4 Expansion"),
    ("PRJ-1003", "Offshore Platform Topsides"),
    ("PRJ-1004", "Refinery Tank Farm"),
]
_SNAPSHOTS = [1, 2]
_WBS_POOL = ["WBS-100", "WBS-200", "WBS-300", "WBS-400", "WBS-500"]
# Original-estimate pricing context, mirroring the real ADR semantics
# (scripts/inspect_cost_basis.py): COST_UPDATE is the quarterly pricing period,
# constant per snapshot; COST_BASIS is a free-text basis/scenario label that can
# vary between items. Both derived WITHOUT the RNG so adding them does not shift
# any other mock draw.
_COST_UPDATE_BY_SNAPSHOT = {1: "2Q2023", 2: "4Q2023"}
_COST_BASIS_POOL = ["NTA", "TA"]
# Execution splits (business Q6: scope partitions like ISBL/OSBL). One project
# gets two splits so the step-2 split selector is exercised in mock mode; the
# rest have a single split. Derived WITHOUT the RNG (index parity), so it does
# not shift any other mock draw.
_MULTI_SPLIT_PROJECT = "PRJ-1003"
_SPLITS = ["ISBL", "OSBL"]
_SINGLE_SPLIT = "NA"


# (original engine-input column, databook DB_* reference twin). The mock fills
# each reference as original * 0.9 - deterministic, no RNG draw (see
# _build_adr_master).
_DB_REFERENCE_TWINS = [
    (COL_SPEC_H_ORIG, COL_DB_SPEC_H),
    (COL_FSF_H_ORIG, COL_DB_FSF_H),
    (COL_FIELD_LABOR_H_ORIG, COL_DB_FIELD_LABOR_H),
    (COL_SPEC_COST_ORIG, COL_DB_SPEC_C),
    (COL_FSF_COST_ORIG, COL_DB_FSF_C),
    (COL_FIELD_LABOR_COST_ORIG, COL_DB_FIELD_LABOR_C),
    (COL_BASE_MATERIAL_COST_ORIG, COL_DB_BM_C),
    (COL_VENDOR_SHOP_FAB_COST_ORIG, COL_DB_VSF_C),
]


def _seed(name: str) -> np.random.Generator:
    """Fixed, process-stable RNG seeded from ``name`` (``zlib.crc32``)."""
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


# =============================================================================
# EMMA reference frames (built once at import)
# =============================================================================
def _build_mfc() -> pd.DataFrame:
    rng = _seed("emma_mfc")
    rows = []
    for code, desc in MFC_CODES.items():
        for loc_code, loc_name in LOCATIONS:
            for period in PERIODS:
                rows.append(
                    {
                        MFC_CODE: code,
                        MFC_DESCRIPTION: desc,
                        MFC_LOCATION: loc_name,
                        MFC_LOCATION_CODE: loc_code,
                        MFC_PERIOD: period,
                        MFC_FACTOR_VALUE: round(float(rng.uniform(0.85, 1.35)), 3),
                    }
                )
    return pd.DataFrame(rows)


def _build_lrc() -> pd.DataFrame:
    rng = _seed("emma_lrc")
    rows = []
    for loc_code, loc_name in LOCATIONS:
        for period in PERIODS:
            base = _LOCATION_BASE_RATE[loc_code] * _PERIOD_ESCALATION[period]
            rows.append(
                {
                    LRC_LOCATION: loc_name,
                    LRC_LOCATION_CODE: loc_code,
                    LRC_PERIOD: period,
                    LRC_FACTOR_MULTIPLIER: round(float(rng.uniform(0.90, 1.25)), 3),
                    LRC_TOTAL_USD_RATE: round(base, 2),
                }
            )
    return pd.DataFrame(rows)


# =============================================================================
# ADR master (built once, then split into the 4 source tables)
# =============================================================================
def _build_adr_master() -> pd.DataFrame:
    """One row per (project, snapshot, item) with all canonical fields.

    The 4 ADR tables are projections of this master onto shared keys, which
    guarantees the join in the repository reconstructs exactly these rows.
    """
    rng = _seed("adr_master")
    codes = list(MFC_CODES.keys())
    rows = []
    for project_id, project_name in _PROJECTS:
        for snap in _SNAPSHOTS:
            # Older snapshot has fewer items; latest snapshot is the full estimate.
            n_items = int(rng.integers(8, 14)) if snap == 1 else int(rng.integers(16, 29))
            for i in range(n_items):
                item_id = f"{project_id}-S{snap}-{i:03d}"
                spec_h = round(float(rng.uniform(0, 120)), 1)
                fsf_h = round(float(rng.uniform(0, 200)), 1)
                fl_h = round(float(rng.uniform(10, 260)), 1)
                row = {
                    COL_PROJECT_ID: project_id,
                    COL_PROJECT_NAME: project_name,
                    COL_SNAPSHOT_ID: snap,
                    COL_ITEM_ID: item_id,
                    COL_WBS: _WBS_POOL[int(rng.integers(0, len(_WBS_POOL)))],
                    COL_DESCRIPTION: f"Item {i:03d} - {project_name}",
                    COL_COST_BASIS: _COST_BASIS_POOL[i % len(_COST_BASIS_POOL)],
                    COL_COST_UPDATE: _COST_UPDATE_BY_SNAPSHOT[snap],
                    COL_EXECUTION_SPLIT: (
                        _SPLITS[i % len(_SPLITS)]
                        if project_id == _MULTI_SPLIT_PROJECT
                        else _SINGLE_SPLIT
                    ),
                    COL_QUANTITY: round(float(rng.uniform(1, 500)), 2),
                    COL_BASE_MATERIAL_MFC: codes[int(rng.integers(0, len(codes)))],
                    COL_VENDOR_SHOP_FAB_MFC: codes[int(rng.integers(0, len(codes)))],
                    # Original-estimate hours (engine inputs)
                    COL_SPEC_H_ORIG: spec_h,
                    COL_FSF_H_ORIG: fsf_h,
                    COL_FIELD_LABOR_H_ORIG: fl_h,
                    # Original-estimate costs (engine inputs)
                    COL_SPEC_COST_ORIG: round(spec_h * float(rng.uniform(40, 90)), 2),
                    COL_FSF_COST_ORIG: round(fsf_h * float(rng.uniform(40, 90)), 2),
                    COL_FIELD_LABOR_COST_ORIG: round(fl_h * float(rng.uniform(40, 90)), 2),
                    COL_BASE_MATERIAL_COST_ORIG: round(float(rng.uniform(500, 80000)), 2),
                    COL_VENDOR_SHOP_FAB_COST_ORIG: round(float(rng.uniform(0, 60000)), 2),
                }
                # Databook DB_* reference twins (display only, business
                # 2026-07-07). Derived from the originals WITHOUT the RNG (fixed
                # 0.9 offset) so no other mock draw shifts, and the reference is
                # visibly different from the engine input - a wiring mixup
                # between the two sets shows up in tests.
                for orig_col, ref_col in _DB_REFERENCE_TWINS:
                    row[ref_col] = round(row[orig_col] * 0.9, 2)
                # A few lines carry NO MFC code, like the real ADR (NULL ->
                # canonical ""): the engine zeroes their updated material cost
                # (business rule 2026-07-10). Index-derived, no RNG draw - the
                # code WAS drawn above, we just blank it - so nothing shifts.
                if i % 13 == 7:
                    row[COL_BASE_MATERIAL_MFC] = ""
                if i % 17 == 11:
                    row[COL_VENDOR_SHOP_FAB_MFC] = ""
                rows.append(row)
    return pd.DataFrame(rows)


_MFC = _build_mfc()
_LRC = _build_lrc()
_ADR_MASTER = _build_adr_master()

# The 4 ADR source tables as projections of the master (shared keys).
_KEYS = [COL_PROJECT_ID, COL_SNAPSHOT_ID, COL_ITEM_ID]
_ADR_TABLE_COLUMNS = {
    TBL_ITEM_RECORD: _KEYS + [COL_PROJECT_NAME, COL_WBS, COL_COST_BASIS,
                              COL_COST_UPDATE, COL_EXECUTION_SPLIT],
    TBL_DESIGN_DETAILS: [COL_ITEM_ID, COL_SNAPSHOT_ID, COL_DESCRIPTION,
                         COL_BASE_MATERIAL_MFC, COL_VENDOR_SHOP_FAB_MFC],
    TBL_COST_RESULTS: [COL_ITEM_ID, COL_SNAPSHOT_ID,
                       COL_SPEC_H_ORIG, COL_FSF_H_ORIG, COL_FIELD_LABOR_H_ORIG,
                       COL_SPEC_COST_ORIG, COL_FSF_COST_ORIG,
                       COL_FIELD_LABOR_COST_ORIG,
                       COL_BASE_MATERIAL_COST_ORIG, COL_VENDOR_SHOP_FAB_COST_ORIG,
                       COL_DB_SPEC_H, COL_DB_FSF_H, COL_DB_FIELD_LABOR_H,
                       COL_DB_SPEC_C, COL_DB_FSF_C, COL_DB_FIELD_LABOR_C,
                       COL_DB_BM_C, COL_DB_VSF_C],
    TBL_QTY_RESULTS: [COL_ITEM_ID, COL_SNAPSHOT_ID, COL_QUANTITY],
}


def fetch_mock_table(table_name: str) -> pd.DataFrame:
    """Return a deterministic mock ADR source table as a fresh copy."""
    if table_name not in _ADR_TABLE_COLUMNS:
        raise KeyError(f"Unknown mock ADR table: {table_name}")
    cols = _ADR_TABLE_COLUMNS[table_name]
    return _ADR_MASTER[cols].copy()


def mock_mfc() -> pd.DataFrame:
    """Return the deterministic mock MFC reference frame (fresh copy)."""
    return _MFC.copy()


def mock_lrc() -> pd.DataFrame:
    """Return the deterministic mock LRC reference frame (fresh copy)."""
    return _LRC.copy()
