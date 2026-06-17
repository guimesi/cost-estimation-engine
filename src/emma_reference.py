"""EMMA reference data: MFC (material) and LRC (labor) factor lookups.

Loads the two EMMA reference frames (mock or Snowflake), exposes the set of
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
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.schema import (
    LRC_FACTOR_MULTIPLIER,
    LRC_LOCATION,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    LRC_RAW_RENAME,
    LRC_TOTAL_USD_RATE,
    MFC_CODE,
    MFC_FACTOR_VALUE,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
    MFC_RAW_RENAME,
)
from config.settings import SETTINGS
from src.models import FactorSelection

logger = logging.getLogger(__name__)


# =============================================================================
# Loading (mock vs Snowflake)
# =============================================================================
def load_mfc() -> pd.DataFrame:
    """Load the MFC (material) reference frame with canonical columns."""
    if SETTINGS.emma_is_mock:
        from src.mock_data import mock_mfc

        return mock_mfc()
    if SETTINGS.emma_is_excel:
        from src.emma_excel import load_excel_mfc

        return load_excel_mfc()
    return _load_snowflake_reference("MFC", MFC_RAW_RENAME)


def load_lrc() -> pd.DataFrame:
    """Load the LRC (labor) reference frame with canonical columns."""
    if SETTINGS.emma_is_mock:
        from src.mock_data import mock_lrc

        return mock_lrc()
    if SETTINGS.emma_is_excel:
        from src.emma_excel import load_excel_lrc

        return load_excel_lrc()
    return _load_snowflake_reference("LRC", LRC_RAW_RENAME)


def _load_snowflake_reference(table: str, rename: Dict[str, str]) -> pd.DataFrame:
    """Fetch an EMMA reference table from Snowflake and canonicalize columns.

    The doc ships EMMA as ``MFC.xlsx`` / ``LRC.xlsx``; in a Snowflake
    deployment they are expected as tables with the same headers (uppercased
    by the client). Reconcile the raw->canonical map in ``config.schema`` if
    the real headers differ.
    """
    from src.snowflake_client import get_shared_client

    df = get_shared_client().fetch_query(f"SELECT * FROM {table}")
    df = df.rename(columns={k.upper(): v for k, v in rename.items()})
    return df


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
