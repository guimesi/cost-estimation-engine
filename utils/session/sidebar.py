"""Sidebar: CSS, brand, progress stepper, sample-mode toggle, footer."""
from __future__ import annotations

import streamlit as st

from utils.session.state import STEP_LABELS, STEPS


def inject_sidebar_css() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { background: #0f172a; }
        section[data-testid="stSidebar"] * { color: #e2e8f0; }
        .cee-step { padding: 0.35rem 0.6rem; border-radius: 8px; margin: 0.15rem 0;
                    font-size: 0.92rem; }
        .cee-step.done    { color: #94a3b8; }
        .cee-step.current { background: #1e293b; color: #fbbf24; font-weight: 600; }
        .cee-step.todo    { color: #64748b; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown("### 💰 Cost Estimation Engine")
    st.sidebar.caption("ADR × EMMA re-estimation")


def render_progress_sidebar() -> None:
    current = st.session_state.get("current_step", STEPS[0])
    try:
        cur_i = STEPS.index(current)
    except ValueError:
        # Pre-workflow (welcome screen): nothing is current, all steps upcoming.
        cur_i = -1
    st.sidebar.markdown("#### Progress")
    html = []
    for i, step in enumerate(STEPS):
        state = "current" if i == cur_i else ("done" if i < cur_i else "todo")
        marker = "●" if i == cur_i else ("✓" if i < cur_i else "○")
        html.append(
            f'<div class="cee-step {state}">{marker} {i + 1}. {STEP_LABELS[step]}</div>'
        )
    st.sidebar.markdown("".join(html), unsafe_allow_html=True)


def render_sample_mode_toggle() -> None:
    st.session_state.sample_mode = st.sidebar.toggle(
        "Sample mode (cap rows)",
        value=st.session_state.get("sample_mode", True),
        help="On: cap rows per table for fast iteration. Off: fetch the full dataset.",
    )


def render_sidebar_footer() -> None:
    st.sidebar.divider()
    st.sidebar.caption("Bootstrapped from data-quality-app")
