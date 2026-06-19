"""Show concrete examples of item duplication across EXECUTION_SPLITs.

Companion to inspect_adr_splits.py for business Q6. For ONE project (default
PLANVIEW 1101168, override with an argument) at its latest gate, it lists the
distinct splits and prints sample item identities (WBS + name) that appear in
more than one split, with the per-split item counts and costs, so you can see
whether the same item+cost literally repeats (double-counting) or the costs
differ (distinct items sharing a generic name).

    python scripts/sample_split_duplicates.py            # 1101168
    python scripts/sample_split_duplicates.py 1089342    # another project

Run with DATA_SOURCE=snowflake + SNOWFLAKE_* in .env. Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import COL_ITEM_ID, COST_CATEGORIES, TBL_ITEM_RECORD  # noqa: E402
from src.adr_repository import _sf_load_project_lines, _snapshot_rank  # noqa: E402
from src.snowflake_client import get_shared_client  # noqa: E402

_COST_COLS = [c.orig_col for c in COST_CATEGORIES]


def _find(columns, *needles):
    for c in columns:
        u = c.upper()
        if all(n in u for n in needles):
            return c
    return None


def _print_samples(title, idents, md, split_c):
    print(f"\n=== {title} ===")
    for ident in idents:
        sub = md[md["IDENT"] == ident]
        per = sub.groupby(split_c)["COST"].agg(
            items="size", costs=lambda s: sorted(set(s))
        )
        print(f"  {ident}")
        for split, r in per.iterrows():
            print(f"     split {split}: {r['items']} item(s), cost(s) {r['costs']}")


def main() -> None:
    pid = sys.argv[1] if len(sys.argv) > 1 else "1101168"
    client = get_shared_client()
    item_t = client.qualified(TBL_ITEM_RECORD)

    cols = list(client.fetch_table(TBL_ITEM_RECORD, limit=5).columns)
    split_col = _find(cols, "EXECUTION", "SPLIT") or _find(cols, "SPLIT")
    wbs_col = _find(cols, "WB")
    name_col = _find(cols, "ITEM", "NAME")
    if not (split_col and wbs_col and name_col):
        print(f"missing a needed column: split={split_col} wbs={wbs_col} name={name_col}")
        return

    snaps = client.fetch_query(
        f"SELECT DISTINCT SNAPSHOT FROM {item_t} WHERE PLANVIEW_ID = %s", params=[pid]
    )
    if snaps.empty:
        print(f"No rows for project {pid!r}.")
        return
    snaps = snaps.assign(_r=_snapshot_rank(snaps["SNAPSHOT"]))
    gate = snaps.loc[snaps["_r"].idxmax(), "SNAPSHOT"]
    print(f"project {pid}, latest gate {gate}")

    rows = client.fetch_table(
        TBL_ITEM_RECORD, columns=["ROW_ID", split_col, wbs_col, name_col],
        where="PLANVIEW_ID = %s AND SNAPSHOT = %s", params=[pid, gate],
    )
    rows.columns = [c.upper() for c in rows.columns]
    sc, wc, nc = split_col.upper(), wbs_col.upper(), name_col.upper()
    print(f"items per split: {rows[sc].value_counts().to_dict()}")

    lines = _sf_load_project_lines(pid)
    md = rows.rename(columns={"ROW_ID": COL_ITEM_ID}).merge(
        lines[[COL_ITEM_ID, *_COST_COLS]], on=COL_ITEM_ID, how="inner"
    )
    md["COST"] = md[_COST_COLS].sum(axis=1).round(2)
    md["IDENT"] = md[wc].astype(str) + " | " + md[nc].astype(str)

    nsplit = md.groupby("IDENT")[sc].nunique()
    dup = set(nsplit[nsplit > 1].index)
    md = md[md["IDENT"].isin(dup)]
    spans = md.groupby(["IDENT", "COST"])[sc].nunique()
    same = list(spans[spans > 1].index.get_level_values(0).unique())
    diff = [i for i in dup if i not in set(same)]
    print(f"\n{len(dup)} duplicated identities: {len(same)} same-cost, {len(diff)} diff-cost")

    _print_samples("SAME-COST (same WBS+name+cost in >1 split = double-count)", same[:10], md, sc)
    _print_samples("DIFF-COST (distinct items sharing a generic name)", diff[:5], md, sc)


if __name__ == "__main__":
    main()
