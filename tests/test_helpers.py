"""Formatting + delta-colour helpers."""
from __future__ import annotations

import math

from utils.colors import STATUS_GREEN, STATUS_RED, STATUS_YELLOW
from utils.helpers import (
    delta_color,
    delta_color_from,
    fmt_hours,
    fmt_money,
    fmt_pct,
    fmt_pct_change,
    fmt_qty,
)


def test_fmt_money():
    assert fmt_money(1234567) == "$1,234,567"
    assert fmt_money(float("nan")) == "-"
    assert fmt_money(None) == "-"


def test_fmt_hours():
    assert fmt_hours(12340) == "12,340 h"
    assert fmt_hours(None) == "-"


def test_fmt_qty():
    assert fmt_qty(1234) == "1,234"        # whole -> no decimals
    assert fmt_qty(2.0) == "2"
    assert fmt_qty(12.5) == "12.50"        # fractional -> 2 decimals
    assert fmt_qty(None) == "-"
    assert fmt_qty(float("nan")) == "-"


def test_fmt_pct():
    assert fmt_pct(4.25) == "+4.2%"
    assert fmt_pct(-3.1) == "-3.1%"
    assert fmt_pct(math.nan) == "n/a"


def test_delta_color_semantics():
    assert delta_color(5.0) == STATUS_RED      # cost up = bad
    assert delta_color(-5.0) == STATUS_GREEN   # cost down = good
    assert delta_color(0.0) == STATUS_YELLOW   # flat
    assert delta_color(math.nan) == STATUS_YELLOW


def test_fmt_pct_change():
    assert fmt_pct_change(100.0, 120.0) == "+20.0%"
    assert fmt_pct_change(100.0, 80.0) == "-20.0%"
    # Zero baseline: a value appearing from nothing is "new", staying zero "0.0%".
    assert fmt_pct_change(0.0, 50.0) == "new"
    assert fmt_pct_change(0.0, 0.0) == "0.0%"
    assert fmt_pct_change(math.nan, 50.0) == "new"


def test_delta_color_from_semantics():
    assert delta_color_from(100.0, 120.0) == STATUS_RED
    assert delta_color_from(100.0, 80.0) == STATUS_GREEN
    assert delta_color_from(100.0, 100.0) == STATUS_YELLOW
    # Zero baseline: appearing from nothing counts as an increase (red).
    assert delta_color_from(0.0, 50.0) == STATUS_RED
    assert delta_color_from(0.0, 0.0) == STATUS_YELLOW
