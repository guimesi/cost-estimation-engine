"""Step 2 - choose execution splits + Location + Time Period, then re-estimate."""
from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from config.schema import COL_EXECUTION_SPLIT
from src.diagnostics import mfc_coverage
from src.estimation_engine import run_estimation
from src.models import FactorSelection, ProjectRef
from ui._data import (
    labor_selections,
    list_projects,
    load_lrc,
    load_mfc,
    load_project_lines,
    project_splits,
)
from utils.helpers import fmt_money
from utils.session.navigation import next_step, prev_step, restart_app


def _project_ref(project_id: str) -> ProjectRef:
    for p in list_projects():
        if p.project_id == project_id:
            return p
    raise KeyError(project_id)


def _sync_split_checkboxes(project_id: str, splits: List[str]) -> None:
    """'Select all' callback: push the master value onto every split checkbox."""
    value = st.session_state[f"splits_all_{project_id}"]
    for s in splits:
        st.session_state[f"split_{project_id}_{s}"] = value


def _render_split_selector(project_id: str, splits: List[str]) -> List[str]:
    """Checkbox per EXECUTION_SPLIT (default all on) + a 'Select all' master.

    Only rendered when the project actually has more than one split (business
    Q6: splits are scope partitions like ISBL/OSBL; letting the user untick one
    also gives manual control over overlapping-split cases like 1101168).
    Checkbox keys are namespaced by project, so switching projects resets the
    selection to all-on.
    """
    if len(splits) <= 1:
        return splits
    st.markdown("**Execution splits to include**")
    st.caption(
        "This project's estimate is divided into execution splits. Untick a "
        "split to leave it out of the comparison."
    )
    st.checkbox(
        "Select all",
        value=True,
        key=f"splits_all_{project_id}",
        on_change=_sync_split_checkboxes,
        args=(project_id, splits),
    )
    selected = []
    for s in splits:
        if st.checkbox(s, value=True, key=f"split_{project_id}_{s}"):
            selected.append(s)
    return selected


def _render_coverage(lines: pd.DataFrame, selection: FactorSelection) -> None:
    """Preview MFC factor coverage for the selection before the run.

    Anticipates the engine's missing-factor warning and puts a dollar figure on
    it, so the user knows up front how much material cost won't be re-estimated.
    Receives the (split-filtered) lines so the preview matches what will run.
    """
    cov = mfc_coverage(lines, load_mfc(), selection)

    if cov.is_fully_covered:
        st.success(
            f"✓ All {cov.total_codes} material code(s) have an MFC factor for "
            f"{selection.label}."
        )
        return

    material = "material factor(s) are" if cov.missing_count != 1 else "material factor is"
    st.warning(
        f"⚠ {cov.missing_count} of {cov.total_codes} {material} missing from the "
        f"MFC (material) reference for {selection.label}. "
        f"{fmt_money(cov.unmatched_material_cost)} of material cost "
        f"({cov.unmatched_cost_pct:.0f}%) will be left unchanged (factor 1.0). "
        "Labor is still re-estimated."
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
    st.caption(
        f"Re-estimating **{project.label}** ({project.n_items} items) · "
        f"originally priced **{project.original_period}** "
        "(original location not recorded in ADR). Pick the new location and "
        "period below."
    )

    # Execution splits (Q6): checkboxes when the project has more than one.
    splits = project_splits(project_id)
    selected_splits = _render_split_selector(project_id, splits)
    lines = load_project_lines(project_id)
    if len(splits) > 1:
        lines = lines[lines[COL_EXECUTION_SPLIT].isin(selected_splits)]
        if selected_splits:
            st.caption(
                f"Including **{len(lines)}** of {project.n_items} items "
                f"({len(selected_splits)}/{len(splits)} splits)."
            )
        else:
            st.error("Select at least one execution split to estimate.")

    selections = labor_selections()
    if not selections:
        st.error("No EMMA labor factors are available (LRC reference is empty).")
        return

    locations = sorted({s.location_name for s in selections})
    location_name = st.selectbox("Location", locations)

    periods = sorted({s.period for s in selections if s.location_name == location_name})
    period = st.selectbox("Time Period", periods)

    selection = next(
        s for s in selections
        if s.location_name == location_name and s.period == period
    )

    if not lines.empty:
        _render_coverage(lines, selection)

    st.divider()
    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        st.button("← Back", on_click=prev_step)
    with cols[1]:
        st.button("Restart", on_click=restart_app)
    with cols[2]:
        if st.button("Estimate →", type="primary", disabled=lines.empty):
            with st.spinner("Running re-estimation…"):
                result = run_estimation(
                    project, lines, load_mfc(), load_lrc(), selection
                )
            st.session_state.selection = selection
            st.session_state.result = result
            next_step()
            st.rerun()
