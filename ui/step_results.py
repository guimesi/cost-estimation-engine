"""Step 3 - dashboard: original vs updated comparison + CSV downloads."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.csv_export import build_lines_csv, build_summary_csv
from src.models import Comparison, EstimationResult
from utils.colors import STATUS_GREEN, STATUS_RED
from utils.helpers import delta_color, fmt_hours, fmt_money, fmt_pct
from utils.session.navigation import prev_step, restart_app


def render() -> None:
    result: EstimationResult = st.session_state.get("result")
    if result is None:
        st.info("Run an estimation first.")
        st.button("← Back", on_click=prev_step)
        return

    st.subheader("3. Estimation result")
    st.caption(f"**{result.project.label}** · {result.selection.label} · {result.n_lines} items")

    for w in result.warnings:
        st.warning(w)

    _render_totals(result)
    st.divider()
    _render_category_breakdown("Cost by category", result.cost_categories, fmt_money)
    _render_chart("Cost by category (USD)", result.cost_categories)
    _render_category_breakdown("Hours by category", result.hour_categories, fmt_hours)
    _render_chart("Hours by category", result.hour_categories)

    st.divider()
    _render_downloads(result)

    st.divider()
    cols = st.columns([1, 1, 4])
    with cols[0]:
        st.button("← Back", on_click=prev_step)
    with cols[1]:
        st.button("Restart", on_click=restart_app)


def _render_totals(result: EstimationResult) -> None:
    c1, c2 = st.columns(2)
    with c1:
        _total_metric("Total Cost", result.total_cost, fmt_money)
    with c2:
        _total_metric("Total Hours", result.total_hours, fmt_hours)


def _total_metric(label: str, cmp: Comparison, fmt) -> None:
    st.markdown(
        f'<div class="cee-card"><h4>{label}</h4>'
        f"<p>Original: <b>{fmt(cmp.original)}</b><br>"
        f"Updated: <b>{fmt(cmp.updated)}</b></p>"
        f'<p>Δ {fmt(cmp.delta)} '
        f'<span style="color:{delta_color(cmp.pct_change)}">'
        f"({fmt_pct(cmp.pct_change)})</span></p></div>",
        unsafe_allow_html=True,
    )


def _render_category_breakdown(title: str, comps, fmt) -> None:
    st.markdown(f"#### {title}")
    rows = [
        {
            "Category": c.label,
            "Original": fmt(c.original),
            "Updated": fmt(c.updated),
            "Δ": fmt(c.delta),
            "% change": fmt_pct(c.pct_change),
        }
        for c in comps
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_chart(title: str, comps) -> None:
    labels = [c.label for c in comps]
    fig = go.Figure()
    fig.add_bar(name="Original", x=labels, y=[c.original for c in comps],
                marker_color="#94a3b8")
    fig.add_bar(name="Updated", x=labels, y=[c.updated for c in comps],
                marker_color="#f59e0b")
    fig.update_layout(
        title=title, barmode="group", height=340,
        margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)
    # Colour cue retained for parity with utils.colors (up=red, down=green).
    _ = (STATUS_RED, STATUS_GREEN)


def _render_downloads(result: EstimationResult) -> None:
    st.markdown("#### Download")
    stem = f"{result.project.project_id}_{result.selection.location_code}_{result.selection.period}"
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇ Line-level estimation (CSV)",
            data=build_lines_csv(result),
            file_name=f"{stem}_lines.csv",
            mime="text/csv",
        )
    with c2:
        st.download_button(
            "⬇ Category summary (CSV)",
            data=build_summary_csv(result),
            file_name=f"{stem}_summary.csv",
            mime="text/csv",
        )
