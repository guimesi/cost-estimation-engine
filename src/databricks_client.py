# pyright: reportArgumentType=false
"""
Databricks SQL client wrapper.

Connects to a Databricks SQL Warehouse via ``databricks-sql-connector``;
identity is resolved by ``databricks.sdk.core.Config`` (unified headless
auth). Inside Databricks Apps the platform injects DATABRICKS_HOST +
DATABRICKS_CLIENT_ID/SECRET (the app's service principal, OAuth M2M);
locally use DATABRICKS_HOST + DATABRICKS_TOKEN or a ~/.databrickscfg
profile. There is deliberately NO browser-based auth path - the app runs
headless.

Returns pandas DataFrames. Two paths to fetch data:

- :meth:`DatabricksClient.fetch_table` - fast Arrow path
  (``cursor.fetchall_arrow().to_pandas()``). Used for wide table reads.
- :meth:`DatabricksClient.fetch_query` - Python-rows path
  (``cursor.fetchall``). Use it for small reference / lookup datasets.

Callers keep the historical pyformat ``%s`` placeholder contract (inherited
from the Snowflake era); :func:`_translate_placeholders` rewrites them to the
connector's native named ``:pN`` markers so values are still bound
server-side (injection-safe), never interpolated.

A shared client (:func:`get_shared_client` / :func:`close_shared_client`)
lets multiple call sites within a single Streamlit run reuse one open
connection instead of re-handshaking per query.

Reads are qualified with ``SETTINGS.dbx_catalog`` / ``SETTINGS.dbx_schema``
(the Unity Catalog namespace holding the migrated tables; names match the
Snowflake originals one-to-one).
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Sequence, Tuple

import pandas as pd

from config.settings import SETTINGS

logger = logging.getLogger(__name__)


def _resolve_location() -> tuple:
    """Resolve the ``(catalog, schema)`` used to qualify table reads.

    Currently reads straight from ``SETTINGS``. Kept as a function (rather
    than inlining) so a future domain registry can override the location
    without touching call sites.
    """
    return SETTINGS.dbx_catalog, SETTINGS.dbx_schema


def _resolve_http_path() -> str:
    """Resolve the SQL Warehouse HTTP path.

    ``DATABRICKS_SQL_HTTP_PATH`` (full path) wins; otherwise the path is
    built from ``DATABRICKS_WAREHOUSE_ID`` - which is what a Databricks App
    receives when a ``sql-warehouse`` resource is attached to it.
    """
    if SETTINGS.dbx_http_path:
        return SETTINGS.dbx_http_path
    if SETTINGS.dbx_warehouse_id:
        return f"/sql/1.0/warehouses/{SETTINGS.dbx_warehouse_id}"
    raise RuntimeError(
        "No SQL Warehouse configured: set DATABRICKS_SQL_HTTP_PATH or "
        "DATABRICKS_WAREHOUSE_ID (in Databricks Apps, attach a "
        "sql-warehouse resource to the app)."
    )


def _translate_placeholders(
    sql: str, params: Optional[Sequence[object]]
) -> Tuple[str, Optional[Dict[str, object]]]:
    """Rewrite pyformat ``%s`` slots to connector-native named markers.

    ``"X IN (%s, %s)"`` with ``[a, b]`` becomes ``"X IN (:p0, :p1)"`` with
    ``{"p0": a, "p1": b}``. Values stay bound server-side; this only changes
    the marker dialect, never inlines a literal.
    """
    if params is None:
        return sql, None
    parts = sql.split("%s")
    if len(parts) - 1 != len(params):
        raise ValueError(
            f"Placeholder mismatch: {len(parts) - 1} %s slots, "
            f"{len(params)} params"
        )
    out = parts[0]
    named: Dict[str, object] = {}
    for i, (value, tail) in enumerate(zip(params, parts[1:])):
        named[f"p{i}"] = value
        out += f":p{i}" + tail
    return out, named


class DatabricksClient:
    """Thin wrapper over databricks.sql. Instantiated lazily."""

    def __init__(self) -> None:
        self._conn = None

    def connect(self):
        if self._conn is not None:
            return self._conn

        # Imported lazily so that mock mode / unit tests do not require the
        # databricks packages.
        from databricks import sql as dbsql  # type: ignore
        from databricks.sdk.core import Config  # type: ignore

        cfg = Config()
        host = (cfg.host or "").removeprefix("https://").removeprefix("http://")
        if not host:
            raise RuntimeError(
                "No Databricks host configured: set DATABRICKS_HOST (and "
                "DATABRICKS_TOKEN for local development)."
            )
        self._conn = dbsql.connect(
            server_hostname=host,
            http_path=_resolve_http_path(),
            credentials_provider=lambda: cfg.authenticate,
        )
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def qualified(self, table_name: str) -> str:
        """Return ``catalog.schema.table`` for the resolved location.

        Exposed so call sites that compose their own SQL (projected reads,
        aggregations, subquery filters) qualify tables the same way
        :meth:`fetch_table` does, without duplicating the location logic.
        """
        catalog, schema = _resolve_location()
        return f"{catalog}.{schema}.{table_name}"

    def fetch_table(
        self,
        table_name: str,
        limit: Optional[int] = None,
        where: Optional[str] = None,
        params: Optional[Sequence[object]] = None,
        columns: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        """Fetch a table as DataFrame, qualified with the resolved
        ``catalog.schema``.

        Uses the Arrow path (``fetchall_arrow().to_pandas()``) - fastest for
        wide result sets.

        Args:
            table_name: bare table name (qualified internally).
            limit: optional row cap (``None`` = no LIMIT clause).
            where: optional SQL WHERE fragment (without the ``WHERE`` keyword).
                Use ``%s`` placeholders for any user-supplied literal and pass
                values via ``params`` - they are translated to native named
                markers and bound server-side, so this module performs no
                quoting / escaping (injection-safe).
            params: positional parameter values matching ``%s`` slots in
                ``where``. Ignored when ``where`` is falsy.
            columns: optional projection - the exact columns to SELECT
                (``None`` = ``SELECT *``). Pushing the projection to the
                warehouse avoids transferring unused columns on wide tables.
        """
        conn = self.connect()
        qualified = self.qualified(table_name)
        select_list = ", ".join(columns) if columns else "*"
        query = f"SELECT {select_list} FROM {qualified}"  # nosec B608 - table/columns come from config.schema constants, never user input; user values are bound via params
        if where:
            query += f" WHERE {where}"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        query, named = _translate_placeholders(query, params if where else None)
        cur = conn.cursor()
        try:
            if named:
                cur.execute(query, named)
            else:
                cur.execute(query)
            df = cur.fetchall_arrow().to_pandas()
        finally:
            cur.close()
        # Normalize column names to uppercase (the app's canonical convention,
        # inherited from the Snowflake era; Databricks may return lowercase)
        df.columns = [c.upper() for c in df.columns]
        return df

    def fetch_query(
        self, sql: str, params: Optional[Sequence[object]] = None
    ) -> pd.DataFrame:
        """Run an arbitrary SELECT and return the result as a DataFrame.

        Uses ``cur.fetchall()`` (Python rows -> pandas) instead of the Arrow
        path. Use this for small reference / aggregate datasets; use
        :meth:`fetch_table` for wide table reads.

        ``params`` binds ``%s`` placeholders server-side (translated to named
        markers, injection-safe), same as :meth:`fetch_table`.
        """
        conn = self.connect()
        query, named = _translate_placeholders(sql, params)
        cur = conn.cursor()
        try:
            if named:
                cur.execute(query, named)
            else:
                cur.execute(query)
            rows = cur.fetchall()
            cols = [d[0].upper() for d in cur.description]
        finally:
            cur.close()
        return pd.DataFrame(rows, columns=cols)

    def __enter__(self) -> "DatabricksClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# =============================================================================
# Process-wide shared client (so multiple reads in one Streamlit run share a
# single connection handshake)
# =============================================================================

_SHARED: Optional[DatabricksClient] = None


def get_shared_client() -> DatabricksClient:
    """Return a process-wide cached :class:`DatabricksClient`.

    The first call opens the connection; subsequent calls reuse it. Lifetime
    is the Streamlit script process; call :func:`close_shared_client` on
    restart / reset.
    """
    global _SHARED
    if _SHARED is None:
        _SHARED = DatabricksClient()
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
