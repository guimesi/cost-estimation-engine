"""Determinism + shape of the mock ADR / EMMA data."""
from __future__ import annotations

import pandas as pd

from config.schema import (
    ADR_TABLES,
    COL_ITEM_ID,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    MFC_CODE,
)
from src import mock_data


def test_adr_tables_are_deterministic():
    for name in ADR_TABLES:
        a = mock_data.fetch_mock_table(name)
        b = mock_data.fetch_mock_table(name)
        pd.testing.assert_frame_equal(a, b)


def test_emma_frames_are_deterministic():
    pd.testing.assert_frame_equal(mock_data.mock_mfc(), mock_data.mock_mfc())
    pd.testing.assert_frame_equal(mock_data.mock_lrc(), mock_data.mock_lrc())


def test_unknown_table_raises():
    import pytest

    with pytest.raises(KeyError):
        mock_data.fetch_mock_table("NOT_A_TABLE")


def test_mfc_covers_every_code():
    mfc = mock_data.mock_mfc()
    assert set(mfc[MFC_CODE]) == set(mock_data.MFC_CODES)


def test_lrc_keyed_on_location_period():
    lrc = mock_data.mock_lrc()
    keys = list(zip(lrc[LRC_LOCATION_CODE], lrc[LRC_PERIOD]))
    assert len(keys) == len(set(keys)) == len(mock_data.LOCATIONS) * len(mock_data.PERIODS)


def test_returned_frames_are_copies():
    t = mock_data.fetch_mock_table(ADR_TABLES[0])
    t.loc[0, COL_ITEM_ID] = "MUTATED"
    fresh = mock_data.fetch_mock_table(ADR_TABLES[0])
    assert fresh.loc[0, COL_ITEM_ID] != "MUTATED"
