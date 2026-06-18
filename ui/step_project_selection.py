"""Step 1 - pick a project that has ADR estimations loaded."""
from __future__ import annotations

import streamlit as st

from src.adr_repository import list_projects
from utils.session.navigation import next_step, restart_app
from utils.session.state import set_project


def render() -> None:
    st.subheader("1. Select a project")
    st.caption("Only projects with ADR estimations loaded are listed.")

    projects = list_projects()
    if not projects:
        st.warning("No projects with ADR estimations were found.")
        return

    selected_id = st.session_state.get("selected_project_id")

    for proj in projects:
        sel = proj.project_id == selected_id
        cls = "cee-card selected" if sel else "cee-card"
        badge = ' <span class="cee-badge">SELECTED</span>' if sel else ""
        st.markdown(
            f'<div class="{cls}"><h4>{proj.project_name}{badge}</h4>'
            f"<p><code>{proj.project_id}</code> &nbsp;·&nbsp; "
            f"{proj.n_items} items &nbsp;·&nbsp; latest snapshot {proj.snapshot_id}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Select {proj.project_id}", key=f"pick_{proj.project_id}"):
            set_project(proj.project_id)
            st.rerun()

    st.divider()
    cols = st.columns([1, 1, 4])
    with cols[0]:
        st.button("Restart", on_click=restart_app)
    with cols[1]:
        st.button(
            "Next →",
            type="primary",
            disabled=selected_id is None,
            on_click=next_step,
        )
