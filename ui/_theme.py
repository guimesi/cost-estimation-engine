"""One consolidated main-area stylesheet, injected once in ``app.main()``.

Mirrors the Data Quality app's H5 pattern: main-area CSS is NOT per-step. The
three status hexes live ONLY in :mod:`utils.colors`; they're embedded here via
``__GREEN__`` / ``__YELLOW__`` / ``__RED__`` sentinels swapped at inject time
(brace-safe - no f-string escaping of the whole sheet). A re-brand is one edit.

Don't reintroduce a per-step ``<style>`` block or a hardcoded status hex.
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
    padding: 1.25rem 1.5rem;
    background: #ffffff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    margin-bottom: 1rem;
}
.cee-card h3 { margin-top: 0; }

/* Status pills */
.cee-pill {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #fff;
}
.cee-pill.green  { background: __GREEN__; }
.cee-pill.yellow { background: __YELLOW__; color: #1f2937; }
.cee-pill.red    { background: __RED__; }
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
