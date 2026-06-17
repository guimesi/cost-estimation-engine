"""Workflow state: step inventory, init, and selection reset helpers.

Three-step flow: pick a project -> choose Location + Period -> view the
comparison + download the CSV. Navigation lives in
:mod:`utils.session.navigation`; sidebar rendering in
:mod:`utils.session.sidebar`. ``utils.session_state`` re-exports everything.
"""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

# Ordered workflow steps.
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
        "current_step": "project_selection",
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
    """Reset the whole workflow back to the project picker (Restart)."""
    st.session_state.selected_project_id = None
    st.session_state.selection = None
    st.session_state.result = None
    st.session_state.current_step = "project_selection"
