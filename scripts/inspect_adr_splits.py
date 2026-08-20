"""Quantify multiple ADR estimates / splits per project at the latest gate.

Business Q6 ("multiple ADRs or splits per project") needs data to decide whether
to keep aggregating ALL items at the latest snapshot or to pick a single
ADR/split. Run this against Databricks (DATA_SOURCE=databricks + the DATABRICKS_*
vars in .env) and paste the output back.

For EACH candidate id column (EXECUTION_SPLIT, ADR_ID, ...) it reports how many
projects have more than one distinct value at their latest gate. Then, for a
sample of the most-split projects, it runs three probes of increasing strength:
  - WBS-set overlap across splits (coarse hint),
  - item-level duplication: same item identity (WBS + name) in >1 split, and
  - cost probe: of those duplicated identities, how many also have the SAME
    databook cost across splits (a strong signal of true double-counting) vs a
    differing cost (distinct items that merely share a generic WBS+name).

    python scripts/inspect_adr_splits.py

Read-only: it issues SELECTs only. Column names are auto-detected so it does not
depend on COMPLETE_WBC vs COMPLETE_WBS spelling.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import COL_ITEM_ID, COST_CATEGORIES, TBL_ITEM_RECORD  # noqa: E402
from src.adr_repository import (  # noqa: E402  (reuse internals for a diagnostic)
    _sf_load_project_lines,
    _snapshot_rank,
)
from src.databricks_client import get_shared_client  # noqa: E402

_COST_COLS = [c.orig_col for c in COST_CATEGORIES]  # canonical databook cost columns


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


def _cost_probe(pid, rows, split_c, wbs_c, name_c, dup_idents):
    """For duplicated identities, split them into same-cost vs differing-cost.

    Joins the project's canonical line frame (which carries the coerced databook
    costs) onto `rows` by ROW_ID, then for each duplicated WBS+name identity asks
    whether some total-cost value recurs across >1 split (a true duplicate).
    Returns (true_dup_count, distinct_count).
    """
    lines = _sf_load_project_lines(pid)  # canonical: ITEM_ID + DB_* costs, latest gate
    sub = rows.rename(columns={"ROW_ID": COL_ITEM_ID}).merge(
        lines[[COL_ITEM_ID, *_COST_COLS]], on=COL_ITEM_ID, how="inner"
    )
    sub["IDENT"] = sub[wbs_c].astype(str) + " | " + sub[name_c].astype(str)
    sub = sub[sub["IDENT"].isin(dup_idents)]
    sub["TOTAL_COST"] = sub[_COST_COLS].sum(axis=1).round(2)
    # An identity is a true duplicate if some (identity, cost) recurs in >1 split.
    spans = sub.groupby(["IDENT", "TOTAL_COST"])[split_c].nunique()
    true_idents = spans[spans > 1].index.get_level_values(0).unique()
    return len(true_idents), len(dup_idents) - len(true_idents)


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

    probe_col = max(cands, key=lambda c: len(multi_by_col[c]))
    sample = multi_by_col[probe_col][:5]
    if not sample:
        print("No multi-split projects: aggregating all items is unambiguous.")
        return

    pc = probe_col.upper()
    wbs_u = wbs_col.upper() if wbs_col else None
    name_u = name_col.upper() if name_col else None
    print(f"duplication + cost probe (split column = {probe_col}):")
    for pid in sample:
        gate = latest[pid]
        proj_cols = ["ROW_ID", "PLANVIEW_ID", "SNAPSHOT", probe_col]
        for c in (wbs_col, name_col):
            if c:
                proj_cols.append(c)
        rows = client.fetch_table(
            TBL_ITEM_RECORD, columns=proj_cols,
            where="PLANVIEW_ID = %s AND SNAPSHOT = %s", params=[pid, gate],
        )
        rows.columns = [c.upper() for c in rows.columns]
        n_splits = rows[pc].nunique()

        line = f"  {pid} (gate {gate}): {n_splits} splits, {len(rows)} items"
        if wbs_u:
            sets = list(rows.groupby(pc)[wbs_u].apply(lambda s: set(s.astype(str))))
            shared = set.intersection(*sets) if len(sets) > 1 else set()
            union = set.union(*sets) if sets else set()
            line += f"; WBS {len(shared)}/{len(union)} shared"
        if wbs_u and name_u:
            ident = rows[wbs_u].astype(str) + " | " + rows[name_u].astype(str)
            per_ident = rows.assign(IDENT=ident).groupby("IDENT")[pc].nunique()
            dup_idents = set(per_ident[per_ident > 1].index)
            line += f"; {len(dup_idents)} identities (WBS+name) in >1 split"
            if dup_idents:
                same, diff = _cost_probe(pid, rows, pc, wbs_u, name_u, dup_idents)
                line += f" [same-cost {same} (true dup) / diff-cost {diff}]"
        print(line)

    print(
        "\nReading: 'same-cost' duplicates are the same WBS+name+cost in more than "
        "one split (aggregating double-counts them). 'diff-cost' are distinct items "
        "that merely share a generic WBS+name (aggregating is correct)."
    )


if __name__ == "__main__":
    main()
