"""Formatting + delta-colour helpers."""
from __future__ import annotations

import math

from utils.colors import STATUS_GREEN, STATUS_RED, STATUS_YELLOW
from utils.helpers import delta_color, fmt_hours, fmt_money, fmt_pct


def test_fmt_money():
    assert fmt_money(1234567) == "$1,234,567"
    assert fmt_money(float("nan")) == "-"
    assert fmt_money(None) == "-"


def test_fmt_hours():
    assert fmt_hours(12340) == "12,340 h"
    assert fmt_hours(None) == "-"


def test_fmt_pct():
    assert fmt_pct(4.25) == "+4.2%"
    assert fmt_pct(-3.1) == "-3.1%"
    assert fmt_pct(math.nan) == "n/a"


def test_delta_color_semantics():
    assert delta_color(5.0) == STATUS_RED      # cost up = bad
    assert delta_color(-5.0) == STATUS_GREEN   # cost down = good
    assert delta_color(0.0) == STATUS_YELLOW   # flat
    assert delta_color(math.nan) == STATUS_YELLOW
