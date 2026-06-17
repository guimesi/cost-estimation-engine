"""SnowflakeClient against a fake connection (no real Snowflake)."""
from __future__ import annotations

import pandas as pd

import src.snowflake_client as sc


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        self.conn.last_query = query
        self.conn.last_params = params

    def fetch_pandas_all(self):
        return pd.DataFrame({"a": [1], "b": [2]})  # lowercase -> client uppercases

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
    client = sc.SnowflakeClient()
    client._conn = _FakeConn()  # connect() short-circuits when _conn is set
    return client


def test_fetch_table_uppercases_columns_and_builds_query():
    client = _client_with_fake()
    df = client.fetch_table("MY_TABLE", limit=10, where="X = %s", params=["v"])
    assert list(df.columns) == ["A", "B"]
    assert "MY_TABLE" in client._conn.last_query
    assert "LIMIT 10" in client._conn.last_query
    assert client._conn.last_params == ["v"]


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
    monkeypatch.setattr(sc.SnowflakeClient, "connect", lambda self: fake)
    with sc.SnowflakeClient() as client:
        assert client.connect() is fake


def test_resolve_location_reads_settings():
    db, schema = sc._resolve_location()
    assert db == sc.SETTINGS.sf_database
    assert schema == sc.SETTINGS.sf_schema


def test_shared_client_singleton(monkeypatch):
    monkeypatch.setattr(sc.SnowflakeClient, "connect", lambda self: setattr(self, "_conn", _FakeConn()) or self._conn)
    sc.close_shared_client()
    a = sc.get_shared_client()
    b = sc.get_shared_client()
    assert a is b
    sc.close_shared_client()
    assert sc._SHARED is None
