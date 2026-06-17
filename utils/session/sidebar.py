"""Sidebar rendering: CSS, brand, and the sample-mode toggle.

Placeholder foundation mirroring the Data Quality app's sidebar split. The
progress stepper / project filter land once the CEE workflow is specified.
"""
from __future__ import annotations

import streamlit as st


def inject_sidebar_css() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { background: #0f172a; }
        section[data-testid="stSidebar"] * { color: #e2e8f0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown("### 💰 Cost Estimation Engine")
    st.sidebar.caption("Snowflake-backed Streamlit app")


def render_sample_mode_toggle() -> None:
    st.session_state.sample_mode = st.sidebar.toggle(
        "Sample mode (cap rows)",
        value=st.session_state.get("sample_mode", True),
        help="On: cap rows per table for fast iteration. Off: fetch the full dataset.",
    )


def render_sidebar_footer() -> None:
    st.sidebar.divider()
    st.sidebar.caption("Bootstrapped from data-quality-app")
