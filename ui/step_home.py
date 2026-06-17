"""Home step - placeholder landing screen.

The first real CEE workflow step replaces this. It exists so the router has
something to render and ``streamlit run app.py`` works on a fresh checkout.
"""
from __future__ import annotations

import streamlit as st

from config.settings import SETTINGS


def render() -> None:
    st.markdown(
        '<div class="cee-card">'
        "<h3>Cost Estimation Engine</h3>"
        "<p>Foundation scaffolded from <code>data-quality-app</code> "
        "(Snowflake client, settings, theme, session, CI/test harness).</p>"
        "<p>Workflow steps land once the domain specification is wired in.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Data source: **{SETTINGS.data_source}**")
