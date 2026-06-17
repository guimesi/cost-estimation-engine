"""Workflow state: step inventory, init, and (future) navigation helpers.

Holds the canonical step list / labels and the ``init_state`` factory that
seeds Streamlit ``session_state`` defaults. The step list is a placeholder
single-step flow until the Cost Estimation Engine workflow is specified - the
foundation (router, sidebar plumbing, session contract) is what's wired up
here so the domain steps just slot in later.

Mirrors the Data Quality app's ``utils/session/`` split (state / navigation /
sidebar). The legacy ``utils.session_state`` re-export shim can be added if
external callers need it.
"""
from __future__ import annotations

import logging
from typing import Dict, List

import streamlit as st

logger = logging.getLogger(__name__)


# Ordered list of workflow steps. Placeholder until the CEE flow is specified.
STEPS: List[str] = [
    "home",
]

STEP_LABELS: Dict[str, str] = {
    "home": "Home",
}


def init_state() -> None:
    defaults = {
        "current_step": "home",
        "sample_mode": True,  # True = cap rows (sample); False = full dataset
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
