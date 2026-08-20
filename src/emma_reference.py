"""EMMA reference data: MFC (material) and LRC (labor) factor lookups.

Loads the two EMMA reference frames (mock, Excel or Databricks), exposes the set of
(Location, Period) selections the user can pick, and provides fast lookups the
engine uses:

- LRC is keyed on ``(location_code, period)`` -> ``(factor_multiplier,
  usd_rate)`` and applied to BOTH labor categories (Specialty Subcontractor
  and Field Shop Fabrication) - the doc gives a single labor factor per
  location/period with no labor-type code.
- MFC is keyed on ``(code, location_code, period)`` -> ``factor_value`` and
  matched per material line (base material code + vendor shop fab code).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.schema import (
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
from config.settings import SETTINGS
from src.models import FactorSelection

logger = logging.getLogger(__name__)


# =============================================================================
# Loading (mock vs Excel vs Databricks)
# =============================================================================
def load_mfc() -> pd.DataFrame:
    """Load the MFC (material) reference frame with canonical columns."""
    if SETTINGS.emma_is_mock:
        from src.mock_data import mock_mfc

        return mock_mfc()
    if SETTINGS.emma_is_excel:
        from src.emma_excel import load_excel_mfc

        return load_excel_mfc()
    return _load_databricks_pair()[0]


def load_lrc() -> pd.DataFrame:
    """Load the LRC (labor) reference frame with canonical columns."""
    if SETTINGS.emma_is_mock:
        from src.mock_data import mock_lrc

        return mock_lrc()
    if SETTINGS.emma_is_excel:
        from src.emma_excel import load_excel_lrc

        return load_excel_lrc()
    return _load_databricks_pair()[1]


@lru_cache(maxsize=1)
def _load_databricks_pair() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch the MFC + LRC tables and return canonical ``(material, labor)``.

    The tables live in the app's Unity Catalog namespace under the names
    ``MFC`` / ``LRC``, but - like the Excel exports they are loaded from -
    their headers vary (Excel-style ``code``/``factorMultiplier`` vs
    SQL-style ``MFC_CODE``) and the material/labor CONTENTS have been observed
    crossed between the two names (business Q8: ignore names, route by
    content). So both tables are read and each is classified by its columns,
    then mapped onto the canonical frames with the same normalization the
    Excel loader uses. Cached for the process lifetime, mirroring the Excel
    loader; the ``ui/_data`` cache sits on top per session.
    """
    from src.databricks_client import get_shared_client
    from src.emma_excel import classify_frame, to_labor_frame, to_material_frame

    client = get_shared_client()
    material: Optional[pd.DataFrame] = None
    labor: Optional[pd.DataFrame] = None
    for table in ("MFC", "LRC"):
        df = client.fetch_query(f"SELECT * FROM {client.qualified(table)}")  # nosec B608 - table name is an internal constant
        kind = classify_frame(df)
        if kind == "material":
            if material is not None:
                raise ValueError(
                    "Both EMMA tables are material-shaped (have a 'code' "
                    "column); expected one material and one labor table."
                )
            material = to_material_frame(df)
        else:
            if labor is not None:
                raise ValueError(
                    "Both EMMA tables are labor-shaped (multiplier + USD "
                    "rate); expected one material and one labor table."
                )
            labor = to_labor_frame(df)
    assert material is not None and labor is not None  # one of each, by above
    return material, labor


# =============================================================================
# Selections (Location + Period the user can pick)
# =============================================================================
def available_selections(
    mfc: Optional[pd.DataFrame] = None, lrc: Optional[pd.DataFrame] = None
) -> List[FactorSelection]:
    """Return the (Location, Period) pairs present in BOTH MFC and LRC.

    The engine needs a labor factor (LRC) AND material factors (MFC) for the
    chosen pair, so only their intersection is offered - this guarantees a
    valid LRC lookup for every selection the UI exposes.
    """
    mfc = load_mfc() if mfc is None else mfc
    lrc = load_lrc() if lrc is None else lrc

    mfc_pairs = set(zip(mfc[MFC_LOCATION_CODE], mfc[MFC_PERIOD]))
    lrc_keyed = {
        (row[LRC_LOCATION_CODE], row[LRC_PERIOD]): row[LRC_LOCATION]
        for _, row in lrc.iterrows()
    }
    out: List[FactorSelection] = []
    for (loc_code, period), loc_name in sorted(lrc_keyed.items()):
        if (loc_code, period) in mfc_pairs:
            out.append(
                FactorSelection(
                    location_code=loc_code, location_name=loc_name, period=period
                )
            )
    return out


def labor_selections(lrc: Optional[pd.DataFrame] = None) -> List[FactorSelection]:
    """Return every (Location, Period) that has a valid LRC labor factor.

    Labor is re-estimated from location + period alone, so any LRC pair can run;
    material is best-effort and flagged when its MFC factor is missing (business
    Q7, 2026-06-19: for v1, let users pick any labor pair and flag the missing
    material reference rather than hiding the pair). This is a superset of
    :func:`available_selections` (which also requires MFC coverage) - it adds the
    labor-only pairs (see :func:`labor_only_selections`). The engine's LRC lookup
    stays valid for every pair offered here; only material may be unfactored.
    """
    lrc = load_lrc() if lrc is None else lrc
    names: Dict[Tuple[str, str], str] = {}
    for _, row in lrc.iterrows():
        names.setdefault((row[LRC_LOCATION_CODE], row[LRC_PERIOD]), row[LRC_LOCATION])
    return [
        FactorSelection(location_code=lc, location_name=name, period=p)
        for (lc, p), name in sorted(names.items())
    ]


def labor_only_selections(
    mfc: Optional[pd.DataFrame] = None, lrc: Optional[pd.DataFrame] = None
) -> List[FactorSelection]:
    """Return (Location, Period) pairs present in LRC but with NO MFC rows.

    These have a valid labor factor but zero material coverage, so the engine
    can't accurately re-estimate material for them. They are intentionally kept
    OUT of :func:`available_selections` (not selectable), but surfaced as
    examples for an SME follow-up on the expected behavior (business Q7).
    """
    mfc = load_mfc() if mfc is None else mfc
    lrc = load_lrc() if lrc is None else lrc

    mfc_pairs = set(zip(mfc[MFC_LOCATION_CODE], mfc[MFC_PERIOD]))
    lrc_keyed = {
        (row[LRC_LOCATION_CODE], row[LRC_PERIOD]): row[LRC_LOCATION]
        for _, row in lrc.iterrows()
    }
    out: List[FactorSelection] = []
    for (loc_code, period), loc_name in sorted(lrc_keyed.items()):
        if (loc_code, period) not in mfc_pairs:
            out.append(
                FactorSelection(
                    location_code=loc_code, location_name=loc_name, period=period
                )
            )
    return out


# =============================================================================
# Lookups
# =============================================================================
def lrc_lookup(
    lrc: pd.DataFrame, location_code: str, period: str
) -> Optional[Tuple[float, float]]:
    """Return ``(factor_multiplier, usd_rate)`` for the location/period, or None."""
    match = lrc[
        (lrc[LRC_LOCATION_CODE] == location_code) & (lrc[LRC_PERIOD] == period)
    ]
    if match.empty:
        return None
    row = match.iloc[0]
    return float(row[LRC_FACTOR_MULTIPLIER]), float(row[LRC_TOTAL_USD_RATE])


def mfc_factor_map(
    mfc: pd.DataFrame, location_code: str, period: str
) -> Dict[str, float]:
    """Return ``{material_code: factor_value}`` for the given location/period.

    Materials whose code is absent for this location/period simply won't be in
    the map; the engine treats a miss as factor ``1.0`` (cost unchanged) and
    records a warning rather than dropping the line.
    """
    subset = mfc[
        (mfc[MFC_LOCATION_CODE] == location_code) & (mfc[MFC_PERIOD] == period)
    ]
    return {
        str(code): float(value)
        for code, value in zip(subset[MFC_CODE], subset[MFC_FACTOR_VALUE])
    }
