"""Workflow state: step inventory, init, and selection reset helpers.

A ``welcome`` landing screen precedes a three-step flow: pick a project ->
choose Location + Period -> view the comparison + download the CSV. The landing
is intentionally NOT part of ``STEPS`` - ``STEPS`` is the *numbered* workflow
(the stepper and each step's "1./2./3." heading), so the welcome screen sits at
"step 0", outside that numbering. Navigation lives in
:mod:`utils.session.navigation`; sidebar rendering in
:mod:`utils.session.sidebar`. ``utils.session_state`` re-exports everything.
"""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

# The pre-workflow landing screen (not a numbered step; see module docstring).
WELCOME_STEP = "welcome"

# Ordered (numbered) workflow steps.
STEPS: List[str] = [
    "project_selection",
    "parameters",
    "results",
]

STEP_LABELS: Dict[str, str] = {
    "project_selection": "Project",
    "parameters": "Location & Period",
    "results": "Estimation",
}


def init_state() -> None:
    defaults = {
        "current_step": WELCOME_STEP,
        "selected_project_id": None,   # str
        "selection": None,             # src.models.FactorSelection
        "result": None,                # src.models.EstimationResult
        "sample_mode": True,           # cap rows when fetching from Snowflake
        "scroll_to_top": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def set_project(project_id: str) -> None:
    """Select a project and drop any downstream selection/result."""
    if st.session_state.get("selected_project_id") != project_id:
        st.session_state.selection = None
        st.session_state.result = None
    st.session_state.selected_project_id = project_id


def clear_run_state() -> None:
    """Reset the whole workflow back to the welcome landing (Restart)."""
    st.session_state.selected_project_id = None
    st.session_state.selection = None
    st.session_state.result = None
    st.session_state.current_step = WELCOME_STEP
