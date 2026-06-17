"""Step navigation: next / prev / goto / restart + scroll-to-top.

Mirrors the data-quality-app pattern: ``current_step`` is an index into
``STEPS``; the nav helpers move it and request a scroll-to-top so the user
lands at the top of the new step.
"""
from __future__ import annotations

import streamlit as st

from utils.session.state import STEPS, clear_run_state, init_state


def _index() -> int:
    try:
        return STEPS.index(st.session_state.current_step)
    except (ValueError, KeyError, AttributeError):
        # Unknown/missing step (catalog changed between runs): fall back to start.
        return 0


def _request_scroll_to_top() -> None:
    st.session_state.scroll_to_top = True


def goto(step: str) -> None:
    if step in STEPS:
        st.session_state.current_step = step
        _request_scroll_to_top()


def next_step() -> None:
    i = _index()
    if i < len(STEPS) - 1:
        st.session_state.current_step = STEPS[i + 1]
        _request_scroll_to_top()


def prev_step() -> None:
    i = _index()
    if i > 0:
        st.session_state.current_step = STEPS[i - 1]
        _request_scroll_to_top()


def restart_app() -> None:
    """Reset selections and return to the first step."""
    init_state()
    clear_run_state()
    _request_scroll_to_top()


def consume_scroll_to_top() -> None:
    """Emit a one-shot scroll-to-top if the last nav action requested it."""
    if st.session_state.get("scroll_to_top"):
        st.session_state.scroll_to_top = False
        st.markdown(
            "<script>window.parent.document.querySelector('section.main')"
            "?.scrollTo(0,0);</script>",
            unsafe_allow_html=True,
        )
