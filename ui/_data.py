"""Streamlit-cached wrappers over the data layer.

The ``src`` layer is deliberately UI-free (engine/repo import no Streamlit), so
the per-session data cache lives here instead. These thin wrappers add
``st.cache_data`` so reruns and repeated clicks don't re-read the same ADR /
EMMA data - in ``snowflake`` mode that means one query per distinct argument
instead of one per interaction. Cache is keyed on the function args.

If the process switches data source mid-session (it doesn't in normal use),
call ``st.cache_data.clear()`` to drop these.
"""
from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from src.adr_repository import list_projects as _list_projects
from src.adr_repository import load_project_lines as _load_project_lines
from src.emma_reference import available_selections as _available_selections
from src.emma_reference import load_lrc as _load_lrc
from src.emma_reference import load_mfc as _load_mfc
from src.models import FactorSelection, ProjectRef


@st.cache_data(show_spinner=False)
def list_projects() -> List[ProjectRef]:
    """Projects with ADR estimations (cached for the session)."""
    return _list_projects()


@st.cache_data(show_spinner=False)
def load_project_lines(project_id: str) -> pd.DataFrame:
    """A project's latest-snapshot line frame (cached per project id)."""
    return _load_project_lines(project_id)


@st.cache_data(show_spinner=False)
def load_mfc() -> pd.DataFrame:
    """MFC (material) reference frame (cached for the session)."""
    return _load_mfc()


@st.cache_data(show_spinner=False)
def load_lrc() -> pd.DataFrame:
    """LRC (labor) reference frame (cached for the session)."""
    return _load_lrc()


@st.cache_data(show_spinner=False)
def available_selections() -> List[FactorSelection]:
    """(Location, Period) pairs offered to the user (cached for the session)."""
    return _available_selections()
