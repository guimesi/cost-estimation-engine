"""Step 2 - choose Location + Time Period, then run the re-estimation."""
from __future__ import annotations

import streamlit as st

from src.diagnostics import mfc_coverage
from src.estimation_engine import run_estimation
from src.models import FactorSelection, ProjectRef
from ui._data import (
    available_selections,
    list_projects,
    load_lrc,
    load_mfc,
    load_project_lines,
)
from utils.helpers import fmt_money
from utils.session.navigation import next_step, prev_step, restart_app


def _project_ref(project_id: str) -> ProjectRef:
    for p in list_projects():
        if p.project_id == project_id:
            return p
    raise KeyError(project_id)


def _render_coverage(project_id: str, selection: FactorSelection) -> None:
    """Preview MFC factor coverage for the selection before the run.

    Anticipates the engine's missing-factor warning and puts a dollar figure on
    it, so the user knows up front how much material cost won't be re-estimated.
    """
    lines = load_project_lines(project_id)
    cov = mfc_coverage(lines, load_mfc(), selection)

    if cov.is_fully_covered:
        st.success(
            f"✓ All {cov.total_codes} material code(s) have an MFC factor for "
            f"{selection.label}."
        )
        return

    st.warning(
        f"{cov.missing_count} of {cov.total_codes} material code(s) have no MFC "
        f"factor for {selection.label}. "
        f"{fmt_money(cov.unmatched_material_cost)} of material cost "
        f"({cov.unmatched_cost_pct:.0f}%) will be left unchanged (factor 1.0)."
    )
    with st.expander(f"Show {cov.missing_count} missing code(s)"):
        st.write(", ".join(cov.missing_codes))


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

    _render_coverage(project_id, selection)

    st.divider()
    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        st.button("← Back", on_click=prev_step)
    with cols[1]:
        st.button("Restart", on_click=restart_app)
    with cols[2]:
        if st.button("Estimate →", type="primary"):
            with st.spinner("Running re-estimation…"):
                lines = load_project_lines(project_id)
                result = run_estimation(
                    project, lines, load_mfc(), load_lrc(), selection
                )
            st.session_state.selection = selection
            st.session_state.result = result
            next_step()
            st.rerun()
