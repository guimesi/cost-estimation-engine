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

/* Hover tooltip: calculation rationale on values (step 3). The text lives in
   the data-tip attribute; newlines in it render as line breaks (pre-line). */
.cee-tip {
    position: relative;
    border-bottom: 1px dotted #9ca3af;
    cursor: help;
}
.cee-tip::after {
    content: attr(data-tip);
    position: absolute;
    left: 50%;
    bottom: calc(100% + 8px);
    transform: translateX(-50%);
    background: #1f2937;
    color: #f9fafb;
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 400;
    line-height: 1.4;
    white-space: pre-line;
    width: max-content;
    max-width: 360px;
    text-align: left;
    box-shadow: 0 4px 12px rgba(0,0,0,0.18);
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.12s ease-in-out;
    z-index: 1000;
    pointer-events: none;
}
.cee-tip::before {
    content: "";
    position: absolute;
    left: 50%;
    bottom: calc(100% + 2px);
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: #1f2937;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.12s ease-in-out;
    z-index: 1000;
    pointer-events: none;
}
.cee-tip:hover::after, .cee-tip:hover::before { opacity: 1; visibility: visible; }

/* Category comparison table (step 3) - HTML so each value can carry a
   .cee-tip; mirrors st.dataframe's look. */
.cee-cmp { width: 100%; border-collapse: collapse; margin-bottom: 0.9rem; font-size: 0.9rem; }
.cee-cmp th, .cee-cmp td { padding: 0.45rem 0.7rem; border-bottom: 1px solid #e5e7eb; }
.cee-cmp th { text-align: left; color: #6b7280; font-weight: 600; font-size: 0.8rem; }
.cee-cmp th.num, .cee-cmp td.num { text-align: right; font-variant-numeric: tabular-nums; }
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
