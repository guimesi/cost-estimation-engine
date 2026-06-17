"""Domain models for the Cost Estimation Engine.

Line-level data stays in pandas DataFrames (the engine is vectorized); these
dataclasses wrap the project/selection identity and the summarized comparison
the UI and CSV render.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

import pandas as pd


@dataclass(frozen=True)
class ProjectRef:
    """A project that has ADR estimations loaded, at its latest snapshot."""

    project_id: str
    project_name: str
    snapshot_id: int
    n_items: int

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

    @property
    def n_lines(self) -> int:
        return len(self.lines)
