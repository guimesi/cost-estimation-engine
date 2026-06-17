"""Shared pytest fixtures.

Mirrors the Data Quality app: an autouse fixture pins the data source to
``mock`` regardless of the shell ``DATA_SOURCE`` so tests never hit Snowflake.
"""
from __future__ import annotations

import dataclasses

import pytest

from config.settings import SETTINGS


@pytest.fixture(autouse=True)
def _force_mock_data_source(monkeypatch):
    """Pin ``SETTINGS.data_source = "mock"`` for every test.

    ``SETTINGS`` is a frozen dataclass, so we patch the module-level instance
    with a mock-forced copy on every module that imported it by reference.
    """
    mock_settings = dataclasses.replace(SETTINGS, data_source="mock", emma_source="mock")
    monkeypatch.setattr("config.settings.SETTINGS", mock_settings)
    monkeypatch.setattr("src.snowflake_client.SETTINGS", mock_settings)
    yield
