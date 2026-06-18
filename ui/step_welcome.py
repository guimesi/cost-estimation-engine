"""Step 0 - welcome / landing screen. Press play to begin the workflow."""
from __future__ import annotations

import streamlit as st

from utils.session.navigation import goto
from utils.session.state import STEPS


def render() -> None:
    st.subheader("Welcome 👋")
    st.markdown(
        """
        The **Cost Estimation Engine** re-estimates an existing **ADR** project
        estimate for a **Location** and **Time Period** of your choice - applying
        **EMMA** market factors (MFC for materials, LRC for labor) - then shows an
        original-vs-updated comparison you can export as CSV.

        **How it works - three steps:**

        1. **Project** - pick a project that has ADR estimations loaded.
        2. **Location & Period** - choose where and when, and preview how well the
           EMMA factors cover the project before you run.
        3. **Estimation** - review the comparison, charts, and per-line detail,
           then download the CSV.
        """
    )
    st.divider()
    cols = st.columns([1, 3])
    with cols[0]:
        st.button(
            "▶  Start",
            type="primary",
            key="start_btn",
            use_container_width=True,
            on_click=goto,
            args=(STEPS[0],),
        )
