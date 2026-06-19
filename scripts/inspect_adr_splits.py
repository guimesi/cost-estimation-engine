"""Quantify multiple ADR estimates / splits per project at the latest gate.

Business Q6 ("multiple ADRs or splits per project") needs data to decide whether
to keep aggregating ALL items at the latest snapshot or to pick a single
ADR/split. Run this against Snowflake (DATA_SOURCE=snowflake + the SNOWFLAKE_*
vars in .env) and paste the output back.

For EACH candidate id column (EXECUTION_SPLIT, ADR_ID, ...) it reports how many
projects have more than one distinct value at their latest gate. Then, for a
sample of the most-split projects, it runs two probes:
  - WBS-set overlap across splits (a coarse hint), and
  - item-level duplication: the same item identity (WBS + item name) appearing
    in more than one split, which is a much stronger signal that aggregating
    would double-count (vs splits being additive partitions of one scope).

    python scripts/inspect_adr_splits.py

Read-only: it issues SELECTs only. Column names are auto-detected so it does not
depend on COMPLETE_WBC vs COMPLETE_WBS spelling.
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


def _find(columns, *needles):
    """First column whose name contains all needles (case-insensitive)."""
    for c in columns:
        u = c.upper()
        if all(n in u for n in needles):
            return c
    return None


def _latest_gate_per_project(client, item_t) -> dict:
    """Map PLANVIEW_ID -> its highest-ranked SNAPSHOT (the latest gate)."""
    gates = client.fetch_query(
        f"SELECT PLANVIEW_ID, SNAPSHOT FROM {item_t} GROUP BY PLANVIEW_ID, SNAPSHOT"
    )
    gates = gates.assign(_rank=_snapshot_rank(gates["SNAPSHOT"]))
    top = gates.loc[gates.groupby("PLANVIEW_ID")["_rank"].idxmax()]
    return dict(zip(top["PLANVIEW_ID"], top["SNAPSHOT"]))


def _distinct_per_project(client, item_t, col, latest):
    """For `col`, the count of distinct values per project at its latest gate."""
    agg = client.fetch_query(
        f"SELECT PLANVIEW_ID, SNAPSHOT, {col} AS V FROM {item_t} "
        f"GROUP BY PLANVIEW_ID, SNAPSHOT, {col}"
    )
    agg = agg[agg["PLANVIEW_ID"].map(latest) == agg["SNAPSHOT"]]
    return agg.groupby("PLANVIEW_ID")["V"].nunique()


def main() -> None:
    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)

    head = client.fetch_table(TBL_ITEM_RECORD, limit=5)
    cols = list(head.columns)
    cands = _candidate_id_columns(cols)
    wbs_col = _find(cols, "WB")
    name_col = _find(cols, "ITEM", "NAME")
    print("item table columns:\n  " + ", ".join(cols))
    print(f"\ncandidate ADR/split id columns: {cands or '(none found)'}")
    print(f"WBS column: {wbs_col} | item-name column: {name_col}")
    if not cands:
        print("No ADR/split id column detected; tell me the right column name.")
        return

    latest = _latest_gate_per_project(client, item_t)
    print(f"projects total: {len(latest)}\n")

    # Distribution per candidate id column.
    multi_by_col = {}
    for col in cands:
        per = _distinct_per_project(client, item_t, col, latest)
        multi = per[per > 1]
        multi_by_col[col] = list(multi.index)
        pct = 100 * multi.size / max(per.size, 1)
        print(f"[{col}] projects with >1 at latest gate: {multi.size} ({pct:.0f}%)")
        print("  distinct-per-project distribution:")
        print("  " + per.value_counts().sort_index().to_string().replace("\n", "\n  "))
        print()

    # Item-level duplication probe on the id column with the most multi projects.
    probe_col = max(cands, key=lambda c: len(multi_by_col[c]))
    sample = multi_by_col[probe_col][:5]
    if not sample:
        print("No multi-split projects: aggregating all items is unambiguous.")
        return

    print(f"duplication probe (split column = {probe_col}):")
    for pid in sample:
        gate = latest[pid]
        proj_cols = ["PLANVIEW_ID", "SNAPSHOT", probe_col]
        if wbs_col:
            proj_cols.append(wbs_col)
        if name_col:
            proj_cols.append(name_col)
        rows = client.fetch_table(
            TBL_ITEM_RECORD, columns=proj_cols,
            where="PLANVIEW_ID = %s AND SNAPSHOT = %s", params=[pid, gate],
        )
        rows.columns = [c.upper() for c in rows.columns]
        pc = probe_col.upper()
        n_splits = rows[pc].nunique()

        line = f"  {pid} (gate {gate}): {n_splits} splits, {len(rows)} items"
        if wbs_col:
            sets = list(rows.groupby(pc)[wbs_col.upper()].apply(lambda s: set(s.astype(str))))
            shared = set.intersection(*sets) if len(sets) > 1 else set()
            union = set.union(*sets) if sets else set()
            line += f"; WBS {len(shared)}/{len(union)} shared across all splits"
        if wbs_col and name_col:
            ident = rows[wbs_col.upper()].astype(str) + " | " + rows[name_col.upper()].astype(str)
            per_ident = rows.assign(IDENT=ident).groupby("IDENT")[pc].nunique()
            dup = int((per_ident > 1).sum())
            line += f"; {dup} item-identities (WBS+name) in >1 split"
        print(line)

    print(
        "\nReading: high 'item-identities in >1 split' => the same items repeat "
        "across splits (aggregating would double-count). Near-zero => splits are "
        "additive partitions (aggregating is correct)."
    )


if __name__ == "__main__":
    main()
