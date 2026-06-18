# pyright: reportArgumentType=false
"""
Snowflake client wrapper.

Supports externalbrowser auth (default). Returns pandas DataFrames.

Two paths to fetch data:

- :meth:`SnowflakeClient.fetch_table` - fast Arrow path
  (``cursor.fetch_pandas_all``). Used for wide table reads.
- :meth:`SnowflakeClient.fetch_query` - Python-rows path (``cursor.fetchall``).
  Resilient to Snowflake's Arrow per-chunk schema inference
  (``ArrowInvalid: Schema at index N was different ...``); use it for small
  reference / lookup datasets.

A shared client (:func:`get_shared_client` / :func:`close_shared_client`)
lets multiple call sites within a single Streamlit run reuse one open
connection instead of triggering repeated auth round-trips.

NOTE: This is the verbatim foundation copied from the Data Quality app, with
the per-domain database/schema resolution stripped out (the Cost Estimation
Engine has no domain registry yet). ``fetch_table`` qualifies reads with
``SETTINGS.sf_database`` / ``SETTINGS.sf_schema``. If/when CEE grows a domain
registry, reintroduce a ``_resolve_location()`` that prefers the active
domain's database/schema with ``SETTINGS`` as fallback.
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

import pandas as pd

from config.settings import SETTINGS

logger = logging.getLogger(__name__)


def _resolve_location() -> tuple:
    """Resolve the ``(database, schema)`` used to qualify table reads.

    Currently reads straight from ``SETTINGS``. Kept as a function (rather
    than inlining) so a future domain registry can override the location
    without touching call sites.
    """
    return SETTINGS.sf_database, SETTINGS.sf_schema


class SnowflakeClient:
    """Thin wrapper over snowflake.connector. Instantiated lazily."""

    def __init__(self) -> None:
        self._conn = None

    def connect(self):
        if self._conn is not None:
            return self._conn

        # Imported lazily so that mock mode does not require the package
        import snowflake.connector  # type: ignore

        params = {
            "account": SETTINGS.sf_account,
            "user": SETTINGS.sf_user,
            "authenticator": SETTINGS.sf_authenticator,
            "database": SETTINGS.sf_database,
            "schema": SETTINGS.sf_schema,
        }
        if SETTINGS.sf_warehouse:
            params["warehouse"] = SETTINGS.sf_warehouse
        if SETTINGS.sf_role:
            params["role"] = SETTINGS.sf_role

        self._conn = snowflake.connector.connect(**params)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def qualified(self, table_name: str) -> str:
        """Return ``database.schema.table`` for the resolved location.

        Exposed so call sites that compose their own SQL (projected reads,
        aggregations, subquery filters) qualify tables the same way
        :meth:`fetch_table` does, without duplicating the location logic.
        """
        database, schema = _resolve_location()
        return f"{database}.{schema}.{table_name}"

    def fetch_table(
        self,
        table_name: str,
        limit: Optional[int] = None,
        where: Optional[str] = None,
        params: Optional[Sequence[object]] = None,
        columns: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        """Fetch a table as DataFrame, qualified with the resolved
        ``database.schema``.

        Uses the Arrow path (``fetch_pandas_all``) - fastest for wide result
        sets. If you hit an ``ArrowInvalid: Schema at index N was different``
        error, project the columns you need (``columns=...``) or fall back to
        :meth:`fetch_query`.

        Args:
            table_name: bare table name (qualified internally).
            limit: optional row cap (``None`` = no LIMIT clause).
            where: optional SQL WHERE fragment (without the ``WHERE`` keyword).
                Use ``%s`` placeholders for any user-supplied literal and pass
                values via ``params`` - the connector binds them server-side,
                so this module performs no quoting / escaping (injection-safe).
            params: positional parameter values matching ``%s`` slots in
                ``where``. Ignored when ``where`` is falsy.
            columns: optional projection - the exact columns to SELECT
                (``None`` = ``SELECT *``). Pushing the projection to Snowflake
                avoids transferring unused columns on wide tables.
        """
        conn = self.connect()
        qualified = self.qualified(table_name)
        select_list = ", ".join(columns) if columns else "*"
        query = f"SELECT {select_list} FROM {qualified}"
        if where:
            query += f" WHERE {where}"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        cur = conn.cursor()
        try:
            if where and params:
                cur.execute(query, list(params))
            else:
                cur.execute(query)
            df = cur.fetch_pandas_all()
        finally:
            cur.close()
        # Normalize column names to uppercase (Snowflake default)
        df.columns = [c.upper() for c in df.columns]
        return df

    def fetch_query(
        self, sql: str, params: Optional[Sequence[object]] = None
    ) -> pd.DataFrame:
        """Run an arbitrary SELECT and return the result as a DataFrame.

        Uses ``cur.fetchall()`` (Python rows → pandas) instead of the Arrow
        path, so callers are immune to Snowflake's Arrow chunk-schema
        mismatch. Use this for small reference / aggregate datasets; use
        :meth:`fetch_table` for wide system-table reads.

        ``params`` binds ``%s`` placeholders server-side (injection-safe),
        same as :meth:`fetch_table`.
        """
        conn = self.connect()
        cur = conn.cursor()
        try:
            if params:
                cur.execute(sql, list(params))
            else:
                cur.execute(sql)
            rows = cur.fetchall()
            cols = [d[0].upper() for d in cur.description]
        finally:
            cur.close()
        return pd.DataFrame(rows, columns=cols)

    def __enter__(self) -> "SnowflakeClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# =============================================================================
# Process-wide shared client (so multiple reads in one Streamlit run share a
# single auth round-trip)
# =============================================================================

_SHARED: Optional[SnowflakeClient] = None


def get_shared_client() -> SnowflakeClient:
    """Return a process-wide cached :class:`SnowflakeClient`.

    The first call opens the connection (triggering external-browser auth
    when needed); subsequent calls reuse it. Lifetime is the Streamlit
    script process; call :func:`close_shared_client` on restart / reset.
    """
    global _SHARED
    if _SHARED is None:
        _SHARED = SnowflakeClient()
    _SHARED.connect()  # idempotent: returns the existing _conn if any
    return _SHARED


def close_shared_client() -> None:
    """Close and drop the cached shared client. Safe to call when nothing
    is cached (no-op)."""
    global _SHARED
    if _SHARED is not None:
        try:
            _SHARED.close()
        finally:
            _SHARED = None
