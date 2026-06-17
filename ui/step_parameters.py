"""Step 2 - choose Location + Time Period, then run the re-estimation."""
from __future__ import annotations

import streamlit as st

from src.adr_repository import load_project_lines
from src.emma_reference import available_selections, load_lrc, load_mfc
from src.estimation_engine import run_estimation
from src.models import ProjectRef
from utils.session.navigation import next_step, prev_step, restart_app


def _project_ref(project_id: str) -> ProjectRef:
    from src.adr_repository import list_projects

    for p in list_projects():
        if p.project_id == project_id:
            return p
    raise KeyError(project_id)


def render() -> None:
    project_id = st.session_state.get("selected_project_id")
    if not project_id:
        st.info("Pick a project first.")
        st.button("← Back", on_click=prev_step)
        return

    project = _project_ref(project_id)
    st.subheader("2. Location & Time Period")
    st.caption(f"Re-estimating **{project.label}** ({project.n_items} items).")

    selections = available_selections()
    if not selections:
        st.error("No EMMA factors are available (MFC/LRC reference is empty).")
        return

    locations = sorted({s.location_name for s in selections})
    location_name = st.selectbox("Location", locations)

    periods = sorted({s.period for s in selections if s.location_name == location_name})
    period = st.selectbox("Time Period", periods)

    selection = next(
        s for s in selections
        if s.location_name == location_name and s.period == period
    )

    st.divider()
    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        st.button("← Back", on_click=prev_step)
    with cols[1]:
        st.button("Restart", on_click=restart_app)
    with cols[2]:
        if st.button("Estimate →", type="primary"):
            lines = load_project_lines(project_id)
            result = run_estimation(project, lines, load_mfc(), load_lrc(), selection)
            st.session_state.selection = selection
            st.session_state.result = result
            next_step()
            st.rerun()
