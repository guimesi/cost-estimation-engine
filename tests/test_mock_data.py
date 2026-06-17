"""Determinism contract for the shared mock RNG."""
from __future__ import annotations

from src import mock_data


def test_reseed_is_stable_across_calls():
    mock_data._reseed_rng_for("widget")
    first = mock_data.RNG.integers(0, 1_000_000, size=10).tolist()
    mock_data._reseed_rng_for("widget")
    second = mock_data.RNG.integers(0, 1_000_000, size=10).tolist()
    assert first == second


def test_reseed_differs_by_name():
    mock_data._reseed_rng_for("alpha")
    a = mock_data.RNG.integers(0, 1_000_000, size=10).tolist()
    mock_data._reseed_rng_for("beta")
    b = mock_data.RNG.integers(0, 1_000_000, size=10).tolist()
    assert a != b
