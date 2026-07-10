"""Domain models for the Cost Estimation Engine.

Line-level data stays in pandas DataFrames (the engine is vectorized); these
dataclasses wrap the project/selection identity and the summarized comparison
the UI and CSV render.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Union

import pandas as pd


@dataclass(frozen=True)
class ProjectRef:
    """A project that has ADR estimations loaded, at its latest snapshot."""

    project_id: str
    project_name: str
    # Stage-gate label from Snowflake (e.g. "GATE3") or an integer in mock mode.
    snapshot_id: Union[int, str]
    n_items: int
    # When the original estimate was priced (ADR COST_UPDATE, e.g. "2Q2019").
    # The original WHERE is not recorded in ADR (doc v2 section 8), so the
    # original context is time-only; "n/a" when the source carries no period.
    original_period: str = "n/a"

    @property
    def label(self) -> str:
        return f"{self.project_id} - {self.project_name}"


@dataclass(frozen=True)
class FactorSelection:
    """The user's chosen Location + Time Period for the re-estimation."""

    location_code: str
    location_name: str
    period: str

    @property
    def label(self) -> str:
        return f"{self.location_name} - {self.period}"


@dataclass(frozen=True)
class Comparison:
    """Original vs updated for one category (or a total), with deltas."""

    key: str
    label: str
    original: float
    updated: float

    @property
    def delta(self) -> float:
        return self.updated - self.original

    @property
    def pct_change(self) -> float:
        """Percentage change, or NaN when the original baseline is zero."""
        if self.original == 0:
            return math.nan
        return (self.updated - self.original) / self.original * 100.0


@dataclass(frozen=True)
class MfcCoverage:
    """How well the MFC reference covers a project's material codes for a selection.

    A pre-flight diagnostic computed before running the engine: it quantifies the
    gap the engine would otherwise only report as a warning - how many distinct
    material codes lack an MFC factor for the chosen (Location, Period), and how
    much databook material cost that leaves unchanged (factor 1.0).
    """

    total_codes: int
    matched_codes: int
    missing_codes: List[str]
    total_material_cost: float
    unmatched_material_cost: float
    # Lines with NO MFC code at all (NULL/blank in ADR): the engine sets their
    # updated material cost to 0 (business rule 2026-07-10). Tracked separately
    # from missing_codes, which is a reference gap for codes that DO exist.
    no_code_lines: int = 0
    no_code_material_cost: float = 0.0

    @property
    def missing_count(self) -> int:
        return len(self.missing_codes)

    @property
    def is_fully_covered(self) -> bool:
        return not self.missing_codes

    @property
    def matched_pct(self) -> float:
        """Share of distinct codes with a factor (100% when there are none)."""
        if self.total_codes == 0:
            return 100.0
        return self.matched_codes / self.total_codes * 100.0

    @property
    def unmatched_cost_pct(self) -> float:
        """Share of material cost left unchanged for lack of a factor."""
        if self.total_material_cost == 0:
            return 0.0
        return self.unmatched_material_cost / self.total_material_cost * 100.0


@dataclass(frozen=True)
class EstimationResult:
    """Everything the dashboard + CSV need from one re-estimation run."""

    project: ProjectRef
    selection: FactorSelection
    lines: pd.DataFrame                       # full per-line frame (orig + updated)
    cost_categories: List[Comparison]         # per-category cost comparisons
    hour_categories: List[Comparison]         # per-category hour comparisons
    total_cost: Comparison
    total_hours: Comparison
    warnings: List[str] = field(default_factory=list)
    # Time period the ORIGINAL databook estimate was priced at (ADR COST_UPDATE,
    # e.g. "2Q2019" - doc v2 says COST_BASIS, but the real data shows the period
    # lives in COST_UPDATE; COST_BASIS is a per-line scenario label). The
    # original location is not recorded in ADR (doc v2 section 8), so the
    # original context is time-only; "n/a" when the source rows carry no period.
    original_period: str = "n/a"

    @property
    def n_lines(self) -> int:
        return len(self.lines)
