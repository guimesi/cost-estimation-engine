"""Inspect what ADR's COST_BASIS and COST_UPDATE columns actually contain.

Doc v2 says the ORIGINAL estimation's time period comes from COST_BASIS, but a
real project showed "Fab Yard - China" there - a location, not a period. The
item table also has a COST_UPDATE column, which may hold the period (mirroring
EMMA's costUpdateReportingPeriod). This prints the distinct values of both
columns (overall top counts + per-project samples) so we can pin the real
semantics and label the original-estimation context correctly.

    DATA_SOURCE=snowflake python scripts/inspect_cost_basis.py

Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import TBL_ITEM_RECORD  # noqa: E402
from src.snowflake_client import get_shared_client  # noqa: E402

_COLS = ["COST_BASIS", "COST_UPDATE"]


def main() -> None:
    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)

    for col in _COLS:
        print("=" * 70)
        print(f"{col}: top distinct values (overall)")
        df = client.fetch_query(
            f"SELECT {col} AS V, COUNT(*) AS N FROM {item_t} "
            f"GROUP BY {col} ORDER BY N DESC LIMIT 20"
        )
        for _, r in df.iterrows():
            print(f"  {r['N']:>8}  {r['V']!r}")

    print("=" * 70)
    print("per (project, latest-ish gate): distinct COST_BASIS x COST_UPDATE pairs")
    df = client.fetch_query(
        f"SELECT PLANVIEW_ID, SNAPSHOT, COST_BASIS, COST_UPDATE, COUNT(*) AS N "
        f"FROM {item_t} GROUP BY PLANVIEW_ID, SNAPSHOT, COST_BASIS, COST_UPDATE "
        f"ORDER BY PLANVIEW_ID, SNAPSHOT LIMIT 40"
    )
    for _, r in df.iterrows():
        print(
            f"  {r['PLANVIEW_ID']} {r['SNAPSHOT']}: basis={r['COST_BASIS']!r} "
            f"update={r['COST_UPDATE']!r} ({r['N']} items)"
        )


if __name__ == "__main__":
    main()
