"""Check EMMA coverage of (Location, Period) pairs across MFC and LRC.

For business Q7: does the "labor present but no material factors" case actually
occur in the real EMMA data? This loads the MFC (material) and LRC (labor)
reference frames and reports, by (Location, Period):
  - pairs in BOTH (selectable today),
  - pairs in LRC but NOT MFC (labor-only: hidden from the selectors, the Q7 case),
  - pairs in MFC but NOT LRC (material-only: also excluded, can't do labor).

Run with the SAME EMMA config the app uses, e.g.:
    EMMA_SOURCE=excel  EMMA_DIR=data  python scripts/inspect_labor_only.py
    DATA_SOURCE=snowflake EMMA_SOURCE=snowflake python scripts/inspect_labor_only.py

Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import (  # noqa: E402
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
)
from src.emma_reference import labor_only_selections, load_lrc, load_mfc  # noqa: E402


def main() -> None:
    mfc = load_mfc()
    lrc = load_lrc()
    mfc_pairs = set(zip(mfc[MFC_LOCATION_CODE], mfc[MFC_PERIOD]))
    lrc_pairs = set(zip(lrc[LRC_LOCATION_CODE], lrc[LRC_PERIOD]))

    both = mfc_pairs & lrc_pairs
    labor_only = lrc_pairs - mfc_pairs
    material_only = mfc_pairs - lrc_pairs

    print(f"MFC (Location, Period) pairs: {len(mfc_pairs)}")
    print(f"LRC (Location, Period) pairs: {len(lrc_pairs)}")
    print(f"in BOTH (selectable today):   {len(both)}")
    print(f"labor-only (LRC, no MFC):     {len(labor_only)}   <- the Q7 case")
    print(f"material-only (MFC, no LRC):   {len(material_only)}")

    pairs = labor_only_selections(mfc, lrc)
    if pairs:
        print("\nlabor-only pairs (labor present, NO material factors):")
        for s in pairs:
            print(f"  {s.location_name} ({s.location_code}) / {s.period}")
    else:
        print("\nNo labor-only pairs: every LRC (Location, Period) also has MFC rows.")


if __name__ == "__main__":
    main()
