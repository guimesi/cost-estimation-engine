"""DatabricksClient against fake connections/modules (no real Databricks)."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pandas as pd
import pytest

import src.databricks_client as dbc


class _FakeArrowTable:
    def to_pandas(self):
        return pd.DataFrame({"a": [1], "b": [2]})  # lowercase -> client uppercases


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        self.conn.last_query = query
        self.conn.last_params = params

    def fetchall_arrow(self):
        return _FakeArrowTable()

    def fetchall(self):
        return [(1, 2), (3, 4)]

    @property
    def description(self):
        return [("a",), ("b",)]

    def close(self):
        self.conn.cursor_closed = True


class _FakeConn:
    def __init__(self):
        self.last_query = None
        self.last_params = None
        self.cursor_closed = False
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def _client_with_fake():
    client = dbc.DatabricksClient()
    client._conn = _FakeConn()  # connect() short-circuits when _conn is set
    return client


# =============================================================================
# Placeholder translation (%s -> :pN named markers)
# =============================================================================
def test_translate_placeholders_rewrites_pyformat():
    sql, named = dbc._translate_placeholders("X = %s AND Y IN (%s, %s)", ["a", 1, 2])
    assert sql == "X = :p0 AND Y IN (:p1, :p2)"
    assert named == {"p0": "a", "p1": 1, "p2": 2}


def test_translate_placeholders_passthrough_without_params():
    sql, named = dbc._translate_placeholders("SELECT 1", None)
    assert sql == "SELECT 1"
    assert named is None


def test_translate_placeholders_mismatch_raises():
    with pytest.raises(ValueError):
        dbc._translate_placeholders("X = %s", ["a", "b"])


# =============================================================================
# Query building + fetch paths
# =============================================================================
def test_fetch_table_uppercases_columns_and_builds_query():
    client = _client_with_fake()
    df = client.fetch_table("MY_TABLE", limit=10, where="X = %s", params=["v"])
    assert list(df.columns) == ["A", "B"]
    assert "MY_TABLE" in client._conn.last_query
    assert "LIMIT 10" in client._conn.last_query
    assert ":p0" in client._conn.last_query  # %s translated to a named marker
    assert client._conn.last_params == {"p0": "v"}


def test_fetch_query_returns_frame():
    client = _client_with_fake()
    df = client.fetch_query("SELECT a, b FROM t")
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2


def test_close_is_idempotent():
    client = _client_with_fake()
    client.close()
    assert client._conn is None
    client.close()  # no-op


def test_context_manager(monkeypatch):
    fake = _FakeConn()
    monkeypatch.setattr(dbc.DatabricksClient, "connect", lambda self: fake)
    with dbc.DatabricksClient() as client:
        assert client.connect() is fake


def test_resolve_location_reads_settings():
    catalog, schema = dbc._resolve_location()
    assert catalog == dbc.SETTINGS.dbx_catalog
    assert schema == dbc.SETTINGS.dbx_schema


def test_qualified_builds_three_part_name():
    client = dbc.DatabricksClient()
    assert client.qualified("T") == (
        f"{dbc.SETTINGS.dbx_catalog}.{dbc.SETTINGS.dbx_schema}.T"
    )


# =============================================================================
# HTTP path resolution
# =============================================================================
def test_resolve_http_path_prefers_full_path(monkeypatch):
    import dataclasses

    s = dataclasses.replace(
        dbc.SETTINGS, dbx_http_path="/sql/1.0/warehouses/explicit", dbx_warehouse_id="w1"
    )
    monkeypatch.setattr(dbc, "SETTINGS", s)
    assert dbc._resolve_http_path() == "/sql/1.0/warehouses/explicit"


def test_resolve_http_path_builds_from_warehouse_id(monkeypatch):
    import dataclasses

    s = dataclasses.replace(dbc.SETTINGS, dbx_http_path="", dbx_warehouse_id="wh123")
    monkeypatch.setattr(dbc, "SETTINGS", s)
    assert dbc._resolve_http_path() == "/sql/1.0/warehouses/wh123"


def test_resolve_http_path_unconfigured_raises(monkeypatch):
    import dataclasses

    s = dataclasses.replace(dbc.SETTINGS, dbx_http_path="", dbx_warehouse_id="")
    monkeypatch.setattr(dbc, "SETTINGS", s)
    with pytest.raises(RuntimeError, match="No SQL Warehouse configured"):
        dbc._resolve_http_path()


# =============================================================================
# connect() wiring (fake databricks modules; the real imports are lazy)
# =============================================================================
@pytest.fixture
def fake_databricks(monkeypatch):
    """Install synthetic ``databricks`` packages so connect() runs offline."""
    connect_mock = MagicMock(return_value=_FakeConn())

    dbx_pkg = types.ModuleType("databricks")
    dbx_sql = types.ModuleType("databricks.sql")
    dbx_sql.connect = connect_mock
    dbx_pkg.sql = dbx_sql

    class _FakeConfig:
        host = "https://adb-123.azuredatabricks.net"

        def __init__(self):
            self.authenticate = MagicMock()

    dbx_sdk = types.ModuleType("databricks.sdk")
    dbx_sdk_core = types.ModuleType("databricks.sdk.core")
    dbx_sdk_core.Config = _FakeConfig
    dbx_sdk.core = dbx_sdk_core

    monkeypatch.setitem(sys.modules, "databricks", dbx_pkg)
    monkeypatch.setitem(sys.modules, "databricks.sql", dbx_sql)
    monkeypatch.setitem(sys.modules, "databricks.sdk", dbx_sdk)
    monkeypatch.setitem(sys.modules, "databricks.sdk.core", dbx_sdk_core)
    return connect_mock


def test_connect_uses_headless_config(monkeypatch, fake_databricks):
    import dataclasses

    s = dataclasses.replace(dbc.SETTINGS, dbx_http_path="", dbx_warehouse_id="wh123")
    monkeypatch.setattr(dbc, "SETTINGS", s)

    client = dbc.DatabricksClient()
    conn = client.connect()
    assert isinstance(conn, _FakeConn)
    kwargs = fake_databricks.call_args.kwargs
    assert kwargs["server_hostname"] == "adb-123.azuredatabricks.net"  # scheme stripped
    assert kwargs["http_path"] == "/sql/1.0/warehouses/wh123"
    assert callable(kwargs["credentials_provider"])
    # Second connect() reuses the open connection (no second handshake).
    assert client.connect() is conn
    assert fake_databricks.call_count == 1


def test_shared_client_singleton(monkeypatch):
    monkeypatch.setattr(
        dbc.DatabricksClient,
        "connect",
        lambda self: setattr(self, "_conn", _FakeConn()) or self._conn,
    )
    dbc.close_shared_client()
    a = dbc.get_shared_client()
    b = dbc.get_shared_client()
    assert a is b
    dbc.close_shared_client()
    assert dbc._SHARED is None
