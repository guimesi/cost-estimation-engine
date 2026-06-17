"""One consolidated main-area stylesheet, injected once in ``app.main()``.

The three status hexes live ONLY in :mod:`utils.colors` and are embedded here
via ``__GREEN__`` / ``__YELLOW__`` / ``__RED__`` sentinels swapped at inject
time (brace-safe). Don't reintroduce a per-step ``<style>`` block or a
hardcoded status hex.
"""
from __future__ import annotations

import streamlit as st

from utils.colors import STATUS_GREEN, STATUS_RED, STATUS_YELLOW

_GLOBAL_CSS = """
<style>
/* Cards */
.cee-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.1rem 1.35rem;
    background: #ffffff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    margin-bottom: 0.9rem;
}
.cee-card h3, .cee-card h4 { margin-top: 0; }
.cee-card.selected { border-color: #f59e0b; box-shadow: 0 0 0 2px #fde68a; }

/* Selected badge */
.cee-badge {
    display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; background: #f59e0b; color: #1f2937;
}

/* Status pills */
.cee-pill {
    display: inline-block; padding: 0.12rem 0.55rem; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; color: #fff;
}
.cee-pill.green  { background: __GREEN__; }
.cee-pill.yellow { background: __YELLOW__; color: #1f2937; }
.cee-pill.red    { background: __RED__; }

/* Delta text colour */
.cee-up   { color: __RED__;   font-weight: 600; }
.cee-down { color: __GREEN__; font-weight: 600; }
.cee-flat { color: __YELLOW__; font-weight: 600; }
</style>
"""


def inject_global_css() -> None:
    """Inject the one canonical main-area stylesheet. Call once per render."""
    css = (
        _GLOBAL_CSS
        .replace("__GREEN__", STATUS_GREEN)
        .replace("__YELLOW__", STATUS_YELLOW)
        .replace("__RED__", STATUS_RED)
    )
    st.markdown(css, unsafe_allow_html=True)
