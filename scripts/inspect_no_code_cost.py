"""How much original material cost sits on lines WITHOUT an MFC code (Q12).

The Q12 rule zeroes the updated material cost of lines whose MFC code is NULL
in ADR. If a run's totals do not move even though the "N line(s) have no ...
code" warning fires, the likely reason is that those lines carry zero original
material cost to begin with (0 * anything = 0 either way). This prints, per
code column and overall, how many lines have no code and how much
BASE_MATERIAL_COST / VENDOR_SHOP_FAB_COST they actually hold - plus the top
projects and a sample of no-code lines WITH cost > 0 (the only ones the rule
visibly changes).

    DATA_SOURCE=snowflake python scripts/inspect_no_code_cost.py [PLANVIEW_ID]

Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import TBL_COST_RESULTS, TBL_ITEM_RECORD  # noqa: E402
from src.snowflake_client import get_shared_client  # noqa: E402

# (code column, un-prefixed original cost column the engine multiplies)
_PAIRS = [
    ("BASE_MATERIAL_MFC", "BASE_MATERIAL_COST"),
    ("VENDOR_SHOP_FAB_MFC", "VENDOR_SHOP_FAB_COST"),
]

_NO_CODE = "({code} IS NULL OR TRIM({code}) = '' OR LOWER(TRIM({code})) IN ('nan', 'none', 'null'))"


def main() -> None:
    client = get_shared_client()
    cost_t = client.qualified(TBL_COST_RESULTS)
    item_t = client.qualified(TBL_ITEM_RECORD)

    planview = sys.argv[1] if len(sys.argv) > 1 else None
    scope = ""
    params = []
    if planview:
        scope = (
            f" AND c.ROW_ID IN (SELECT ROW_ID FROM {item_t} WHERE PLANVIEW_ID = %s)"
        )
        params = [planview]
        print(f"Scope: PLANVIEW_ID = {planview}")

    for code_col, cost_col in _PAIRS:
        no_code = _NO_CODE.format(code=f"c.{code_col}")
        print("=" * 70)
        print(f"{code_col} (cost column: {cost_col})")
        df = client.fetch_query(
            f"SELECT COUNT(*) AS TOTAL_LINES, "
            f"SUM(IFF({no_code}, 1, 0)) AS NO_CODE_LINES, "
            f"SUM(IFF({no_code}, COALESCE(TRY_TO_DOUBLE(c.{cost_col}), 0), 0)) "
            f"  AS NO_CODE_COST, "
            f"SUM(IFF({no_code} AND COALESCE(TRY_TO_DOUBLE(c.{cost_col}), 0) <> 0, "
            f"  1, 0)) AS NO_CODE_LINES_WITH_COST "
            f"FROM {cost_t} c WHERE 1=1{scope}",
            params=params or None,
        )
        r = df.iloc[0]
        print(f"  lines total:                 {int(r['TOTAL_LINES']):>10}")
        print(f"  lines with no code:          {int(r['NO_CODE_LINES']):>10}")
        print(f"  ... of which cost <> 0:      {int(r['NO_CODE_LINES_WITH_COST']):>10}")
        print(f"  original cost on those lines: {float(r['NO_CODE_COST'] or 0):>15,.2f}")

        sample = client.fetch_query(
            f"SELECT c.ROW_ID, c.{cost_col} FROM {cost_t} c "
            f"WHERE {no_code} AND COALESCE(TRY_TO_DOUBLE(c.{cost_col}), 0) <> 0"
            f"{scope} LIMIT 5",
            params=params or None,
        )
        if sample.empty:
            print("  -> every no-code line carries ZERO cost: zeroing them "
                  "cannot move any total (expected: results unchanged).")
        else:
            print("  sample no-code lines WITH cost (these DO change):")
            for _, row in sample.iterrows():
                print(f"    {row['ROW_ID']}  {cost_col}={row[cost_col]!r}")
    print("=" * 70)


if __name__ == "__main__":
    main()
