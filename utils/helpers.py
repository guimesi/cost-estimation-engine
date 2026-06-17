"""Formatting + delta-colour helpers shared by the UI and charts."""
from __future__ import annotations

import math

from utils.colors import STATUS_GREEN, STATUS_RED, STATUS_YELLOW


def fmt_money(value: float) -> str:
    """Format a USD amount, e.g. ``$1,234,567``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"${value:,.0f}"


def fmt_hours(value: float) -> str:
    """Format an hours figure, e.g. ``12,340 h``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:,.0f} h"


def fmt_pct(value: float) -> str:
    """Format a percentage change with sign, e.g. ``+4.2%`` / ``n/a``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:+.1f}%"


def delta_color(pct_change: float) -> str:
    """Colour for a cost/hours change: up is bad (red), down is good (green).

    A re-estimation that *increases* projected cost or hours is flagged red;
    a decrease green; a flat / undefined change yellow.
    """
    if pct_change is None or (isinstance(pct_change, float) and math.isnan(pct_change)):
        return STATUS_YELLOW
    if pct_change > 0.05:
        return STATUS_RED
    if pct_change < -0.05:
        return STATUS_GREEN
    return STATUS_YELLOW
