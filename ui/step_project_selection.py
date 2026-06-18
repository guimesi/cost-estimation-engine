"""Step 1 - pick a project that has ADR estimations loaded.

Scales to many projects: a shared search box filters by PlanView ID or name,
and three interchangeable layouts (table / dropdown / cards) let you pick the
one that reads best. The selected project id lives in session state; the bottom
nav advances once something is selected.
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.models import ProjectRef
from ui._data import list_projects
from utils.session.navigation import next_step, restart_app
from utils.session.state import set_project

_LAYOUTS = ["Table", "Dropdown", "Cards"]
_PAGE_SIZE = 10


def render() -> None:
    st.subheader("1. Select a project")
    st.caption("Only projects with ADR estimations loaded are listed.")

    projects = list_projects()
    if not projects:
        st.warning("No projects with ADR estimations were found.")
        return

    layout = st.radio("View", _LAYOUTS, horizontal=True)
    query = st.text_input("Search", placeholder="PlanView ID or project name…")
    filtered = _filter(projects, query)
    st.caption(f"Showing {len(filtered)} of {len(projects)} projects.")

    if not filtered:
        st.info("No project matches the search.")
    elif layout == "Table":
        _render_table(filtered)
    elif layout == "Dropdown":
        _render_dropdown(filtered)
    else:
        _render_cards(filtered)

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


def _filter(projects: list[ProjectRef], query: str) -> list[ProjectRef]:
    q = query.strip().lower()
    if not q:
        return projects
    return [
        p for p in projects
        if q in p.project_id.lower() or q in p.project_name.lower()
    ]


def _select(project_id: str) -> None:
    """Set the project and rerun if it changed (keeps the highlight in sync)."""
    if st.session_state.get("selected_project_id") != project_id:
        set_project(project_id)
        st.rerun()


# --- Layout: table (sortable, single-row selection) ------------------------
def _render_table(projects: list[ProjectRef]) -> None:
    df = pd.DataFrame(
        [
            {
                "PlanView ID": p.project_id,
                "Project": p.project_name,
                "Snapshot": str(p.snapshot_id),
                "Items": p.n_items,
            }
            for p in projects
        ]
    )
    event = st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"Items": st.column_config.NumberColumn(format="%d")},
    )
    rows = event.selection.rows if event and event.selection else []
    if rows:
        _select(projects[rows[0]].project_id)
    else:
        st.caption("Click a row to select a project.")


# --- Layout: dropdown (filter-narrowed select + detail card) ---------------
def _render_dropdown(projects: list[ProjectRef]) -> None:
    ids = [p.project_id for p in projects]
    labels = {p.project_id: f"{p.project_id} — {p.project_name}" for p in projects}
    current = st.session_state.get("selected_project_id")
    index = ids.index(current) if current in ids else 0

    chosen_id = st.selectbox(
        "Project", ids, index=index, format_func=lambda i: labels[i]
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


# --- Layout: cards (paginated) ---------------------------------------------
def _render_cards(projects: list[ProjectRef]) -> None:
    selected_id = st.session_state.get("selected_project_id")
    pages = max(1, math.ceil(len(projects) / _PAGE_SIZE))
    page = min(st.session_state.get("proj_page", 0), pages - 1)
    start = page * _PAGE_SIZE

    for proj in projects[start:start + _PAGE_SIZE]:
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
            _select(proj.project_id)

    if pages > 1:
        nav = st.columns([1, 2, 1])
        with nav[0]:
            if st.button("← Prev", disabled=page <= 0):
                st.session_state.proj_page = page - 1
                st.rerun()
        with nav[1]:
            st.markdown(
                f"<div style='text-align:center'>Page {page + 1} of {pages}</div>",
                unsafe_allow_html=True,
            )
        with nav[2]:
            if st.button("Next →", disabled=page >= pages - 1, key="cards_next_page"):
                st.session_state.proj_page = page + 1
                st.rerun()
