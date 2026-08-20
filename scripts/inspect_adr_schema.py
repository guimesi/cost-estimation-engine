"""Dump the real column names of the 4 ADR tables in Unity Catalog.

Run this with your Databricks env configured (DATA_SOURCE=databricks and the
DATABRICKS_* vars in .env) to discover the actual ITPlus column names. Paste the
output back so the raw->canonical ADR rename maps can be filled in
``config/schema.py`` and the join keys verified in ``src/adr_repository.py``.

    python scripts/inspect_adr_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/inspect_adr_schema.py` from anywhere:
# put the project root (this file's parent's parent) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.schema import ADR_TABLES  # noqa: E402
from src.databricks_client import get_shared_client  # noqa: E402


def main() -> None:
    client = get_shared_client()
    for table in ADR_TABLES:
        print("=" * 78)
        print(table)
        print("-" * 78)
        try:
            df = client.fetch_table(table, limit=5)
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            print(f"  ERROR fetching: {exc}")
            continue
        print(f"  rows fetched: {len(df)}  |  columns: {len(df.columns)}")
        for col in df.columns:
            sample = df[col].dropna().head(1).tolist()
            sample_val = sample[0] if sample else "<all null in sample>"
            print(f"    {col:<40} e.g. {sample_val!r}")
    print("=" * 78)


if __name__ == "__main__":
    main()
