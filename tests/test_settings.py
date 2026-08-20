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
        s.data_source = "databricks"  # type: ignore[misc]
