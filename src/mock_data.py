"""Deterministic synthetic data for the ``mock`` data source.

Placeholder until the Cost Estimation Engine domain spec lands. The one piece
of foundation worth carrying over verbatim is the determinism contract from
the Data Quality app:

    The module uses one shared, stateful RNG. Because every ``RNG.choice(...)``
    advances it, a builder is only pure if the generator starts from the same
    place each call - so ``_reseed_rng_for(name)`` reseeds from a STABLE hash
    of the name (``zlib.crc32``, NOT the salted built-in ``hash``, so it's
    stable across processes). Call it at the start of every builder that draws
    from ``RNG``, and anchor any "recent" dates to ``_MOCK_NOW`` (captured once
    at import) rather than inline ``datetime.now()``.

This keeps mock output byte-identical across calls regardless of call order,
so scores never drift run-to-run.
"""
from __future__ import annotations

import zlib
from datetime import datetime

import numpy as np

# Captured once at import so "recent"-relative date columns are stable within
# a process (inline datetime.now() differs by microseconds per build).
_MOCK_NOW = datetime.now()

# One shared, stateful module RNG. Reseed per builder via _reseed_rng_for.
RNG = np.random.default_rng(0)


def _reseed_rng_for(name: str) -> None:
    """Reseed the shared module ``RNG`` from a stable hash of ``name``.

    ``zlib.crc32`` is stable across processes (unlike the salted built-in
    ``hash``), so a given builder name always yields the same byte stream.
    """
    RNG.bit_generator.state = np.random.default_rng(
        zlib.crc32(name.encode("utf-8"))
    ).bit_generator.state


def fetch_mock_table(table_name: str):  # pragma: no cover - placeholder
    """Return a deterministic mock DataFrame for ``table_name``.

    Stub: fill in once the CEE table/domain spec is available. Real builders
    must call ``_reseed_rng_for(table_name)`` first.
    """
    raise NotImplementedError(
        "Mock tables are not defined yet - awaiting the Cost Estimation "
        "Engine domain specification."
    )
