"""Quantify multiple ADR estimates / splits per project at the latest gate.

Business Q6 ("multiple ADRs or splits per project") needs data to decide whether
to keep aggregating ALL items at the latest snapshot or to pick a single
ADR/split. Run this against Snowflake (DATA_SOURCE=snowflake + the SNOWFLAKE_*
vars in .env) and paste the output back.

It (1) finds the ADR/split identifier column on the item table, (2) counts, per
project at its latest gate, how many distinct ADR/split ids exist, and (3) for a
sample of multi-split projects, checks whether their WBS codes OVERLAP (a hint
of possible double counting if we aggregate) or are DISJOINT (complementary
partitions, where aggregating is correct).

    python scripts/inspect_adr_splits.py

Read-only: it issues SELECTs only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import TBL_ITEM_RECORD  # noqa: E402
from src.adr_repository import _snapshot_rank  # noqa: E402  (reuse gate ranking)
from src.snowflake_client import get_shared_client  # noqa: E402


def _candidate_id_columns(columns) -> list:
    """Item-table columns that look like an ADR/split identifier."""
    out = []
    for c in columns:
        u = c.upper()
        if "SPLIT" in u or ("ADR" in u and "ID" in u):
            out.append(c)
    return out


def main() -> None:
    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)

    head = client.fetch_table(TBL_ITEM_RECORD, limit=5)
    cols = list(head.columns)
    cands = _candidate_id_columns(cols)
    print("item table columns:")
    print("  " + ", ".join(cols))
    print(f"\ncandidate ADR/split id columns: {cands or '(none found)'}")
    if not cands:
        print(
            "No ADR/split id column auto-detected. Tell me the right column name "
            "and I will adjust the script."
        )
        return

    idcol = cands[0]
    print(f"Using '{idcol}' as the ADR/split id.\n")

    # Item counts per (project, gate, adr/split), computed server-side.
    agg = client.fetch_query(
        f"SELECT PLANVIEW_ID, SNAPSHOT, {idcol} AS ADR_SPLIT, COUNT(*) AS N "
        f"FROM {item_t} GROUP BY PLANVIEW_ID, SNAPSHOT, {idcol}"
    )
    # Keep each project's latest gate only.
    agg = agg.assign(_rank=_snapshot_rank(agg["SNAPSHOT"]))
    latest_rank = agg.groupby("PLANVIEW_ID")["_rank"].transform("max")
    latest = agg[agg["_rank"] == latest_rank]

    per_proj = latest.groupby("PLANVIEW_ID")["ADR_SPLIT"].nunique()
    multi = per_proj[per_proj > 1]
    total = max(per_proj.size, 1)
    print(f"projects total: {per_proj.size}")
    print(
        f"projects with >1 ADR/split at latest gate: {multi.size} "
        f"({100 * multi.size / total:.0f}%)"
    )
    print("\n# distinct ADR/split per project (latest gate):")
    print(per_proj.value_counts().sort_index().to_string())

    sample = list(multi.index[:5])
    if not sample:
        print("\nNo multi-split projects: aggregating all items is unambiguous.")
        return

    print("\nWBS overlap on a sample of multi-split projects:")
    for pid in sample:
        gate = latest[latest["PLANVIEW_ID"] == pid]["SNAPSHOT"].iloc[0]
        rows = client.fetch_table(
            TBL_ITEM_RECORD,
            columns=["PLANVIEW_ID", "SNAPSHOT", idcol, "COMPLETE_WBC"],
            where="PLANVIEW_ID = %s AND SNAPSHOT = %s",
            params=[pid, gate],
        )
        rows.columns = [c.upper() for c in rows.columns]
        wbs_by_split = rows.groupby(idcol.upper())["COMPLETE_WBC"].apply(
            lambda s: set(s.astype(str))
        )
        sets = list(wbs_by_split)
        shared = set.intersection(*sets) if len(sets) > 1 else set()
        union = set.union(*sets) if sets else set()
        verdict = "OVERLAP (possible double count)" if shared else "disjoint (complementary)"
        print(
            f"  {pid} (gate {gate}): {len(sets)} splits, {len(union)} distinct WBS, "
            f"{len(shared)} shared across all splits -> {verdict}"
        )


if __name__ == "__main__":
    main()
