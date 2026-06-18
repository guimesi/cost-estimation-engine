"""Step 1 - pick a project that has ADR estimations loaded.

Scales to many projects via a single searchable dropdown: the select's built-in
type-to-filter matches the "PlanView ID — name" label, so typing either narrows
the list. The chosen project's details show in a card below; the selected id
lives in session state and the bottom nav advances once something is picked.
"""
from __future__ import annotations

import streamlit as st

from src.models import ProjectRef
from ui._data import list_projects
from utils.session.navigation import next_step, restart_app
from utils.session.state import set_project


def render() -> None:
    st.subheader("1. Select a project")
    st.caption("Only projects with ADR estimations loaded are listed.")

    projects = list_projects()
    if not projects:
        st.warning("No projects with ADR estimations were found.")
        return

    _render_dropdown(projects)

    st.divider()
    cols = st.columns([1, 1, 4])
    with cols[0]:
        st.button("Restart", on_click=restart_app)
    with cols[1]:
        st.button(
            "Next →",
            type="primary",
            disabled=st.session_state.get("selected_project_id") is None,
            on_click=next_step,
        )


def _render_dropdown(projects: list[ProjectRef]) -> None:
    ids = [p.project_id for p in projects]
    labels = {p.project_id: f"{p.project_id} — {p.project_name}" for p in projects}
    current = st.session_state.get("selected_project_id")
    index = ids.index(current) if current in ids else 0

    chosen_id = st.selectbox(
        f"Project ({len(projects)} available)",
        ids,
        index=index,
        format_func=lambda i: labels[i],
        help="Type a PlanView ID or project name to filter.",
    )
    if chosen_id and chosen_id != current:
        set_project(chosen_id)

    chosen = next(p for p in projects if p.project_id == chosen_id)
    st.markdown(
        f'<div class="cee-card selected"><h4>{chosen.project_name}'
        ' <span class="cee-badge">SELECTED</span></h4>'
        f"<p><code>{chosen.project_id}</code> &nbsp;·&nbsp; {chosen.n_items} items"
        f" &nbsp;·&nbsp; latest snapshot {chosen.snapshot_id}</p></div>",
        unsafe_allow_html=True,
    )
