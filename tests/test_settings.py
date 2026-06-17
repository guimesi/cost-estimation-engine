"""Settings + foundation smoke tests."""
from __future__ import annotations

from config.settings import SETTINGS, Settings


def test_settings_defaults_to_mock_in_tests():
    # The autouse fixture pins mock regardless of the shell env.
    assert SETTINGS.data_source == "mock"
    assert SETTINGS.is_mock is True


def test_settings_is_frozen():
    import pytest

    s = Settings()
    with pytest.raises(Exception):
        s.data_source = "snowflake"  # type: ignore[misc]


def test_max_rows_is_int():
    assert isinstance(SETTINGS.max_rows_per_table, int)
    assert SETTINGS.max_rows_per_table > 0
