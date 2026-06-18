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


def _is_zero_baseline(original: float) -> bool:
    """True when the original is missing or zero (percentage is undefined)."""
    if original is None:
        return True
    if isinstance(original, float) and math.isnan(original):
        return True
    return original == 0


def fmt_pct_change(original: float, updated: float) -> str:
    """Percent-change label that names the zero-baseline cases instead of NaN.

    When the original is zero, a percentage is undefined: a non-zero updated
    value is shown as ``new`` (appeared from nothing) and a still-zero updated
    value as ``0.0%``. Otherwise the signed percentage, e.g. ``+4.2%``.
    """
    if _is_zero_baseline(original):
        return "new" if updated else "0.0%"
    return fmt_pct((updated - original) / original * 100.0)


def delta_color_from(original: float, updated: float) -> str:
    """Delta colour from raw original/updated, handling the zero baseline.

    A value that appears from a zero baseline counts as an increase (red);
    a still-zero value is flat (yellow). Otherwise delegates to
    :func:`delta_color` on the percentage change.
    """
    if _is_zero_baseline(original):
        return STATUS_RED if updated else STATUS_YELLOW
    return delta_color((updated - original) / original * 100.0)
