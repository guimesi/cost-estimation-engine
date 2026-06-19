"""Step 3 - dashboard: original vs updated comparison + CSV downloads."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.schema import (
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_DESCRIPTION,
    COL_ITEM_ID,
    COL_QUANTITY,
    COL_TOTAL_COST_NEW,
    COL_TOTAL_COST_ORIG,
    COL_TOTAL_HOURS_NEW,
    COL_TOTAL_HOURS_ORIG,
    COL_VENDOR_SHOP_FAB_FACTOR_MISSING,
    COL_WBS,
)
from src.csv_export import build_lines_csv, build_summary_csv
from src.models import Comparison, EstimationResult
from utils.helpers import delta_color_from, fmt_hours, fmt_money, fmt_pct_change, fmt_qty
from utils.session.navigation import prev_step, restart_app

# Neutral baseline fill for the "Original" series (not a status colour, so it
# stays a local literal rather than living in utils.colors).
_NEUTRAL_GRAY = "#94a3b8"


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
    _render_line_table(result)

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
        f'<span style="color:{delta_color_from(cmp.original, cmp.updated)}">'
        f"({fmt_pct_change(cmp.original, cmp.updated)})</span></p></div>",
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
            "% change": fmt_pct_change(c.original, c.updated),
        }
        for c in comps
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_chart(title: str, comps) -> None:
    labels = [c.label for c in comps]
    # Colour each Updated bar by the direction of its change: a category whose
    # cost/hours went up is red, down is green, flat/undefined yellow - the same
    # semantics as the totals delta (utils.helpers.delta_color_from).
    updated_colors = [delta_color_from(c.original, c.updated) for c in comps]
    fig = go.Figure()
    fig.add_bar(name="Original", x=labels, y=[c.original for c in comps],
                marker_color=_NEUTRAL_GRAY)
    fig.add_bar(name="Updated", x=labels, y=[c.updated for c in comps],
                marker_color=updated_colors)
    fig.update_layout(
        title=title, barmode="group", height=340,
        margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_line_table(result: EstimationResult) -> None:
    """Per-line original-vs-updated table with a text filter (item/WBS/desc)."""
    df = result.lines
    with st.expander(f"Line-level detail ({len(df)} items)", expanded=False):
        query = st.text_input(
            "Filter lines", placeholder="item id, WBS, or description…"
        ).strip().lower()

        view = df
        if query:
            haystack = (
                df[COL_ITEM_ID].astype(str).str.lower()
                + " " + df[COL_WBS].astype(str).str.lower()
                + " " + df[COL_DESCRIPTION].astype(str).str.lower()
            )
            view = df[haystack.str.contains(query, regex=False)]
            st.caption(f"{len(view)} of {len(df)} lines match.")

        if view.empty:
            st.info("No lines match the filter.")
            return

        mfc_missing = (
            view[COL_BASE_MATERIAL_FACTOR_MISSING]
            | view[COL_VENDOR_SHOP_FAB_FACTOR_MISSING]
        )
        table = pd.DataFrame(
            {
                "Item": view[COL_ITEM_ID].astype(str),
                "WBS": view[COL_WBS].astype(str),
                "Description": view[COL_DESCRIPTION].astype(str),
                "Qty": view[COL_QUANTITY].map(fmt_qty),
                "MFC": mfc_missing.map({True: "⚠ missing", False: ""}),
                "Cost (orig)": view[COL_TOTAL_COST_ORIG].map(fmt_money),
                "Cost (new)": view[COL_TOTAL_COST_NEW].map(fmt_money),
                "Δ Cost": (view[COL_TOTAL_COST_NEW] - view[COL_TOTAL_COST_ORIG]).map(
                    fmt_money
                ),
                "Hours (orig)": view[COL_TOTAL_HOURS_ORIG].map(fmt_hours),
                "Hours (new)": view[COL_TOTAL_HOURS_NEW].map(fmt_hours),
            }
        )
        st.dataframe(table, hide_index=True, use_container_width=True)
        if mfc_missing.any():
            st.caption(
                "⚠ MFC missing: no material factor for the selection; that line's "
                "material cost was left unchanged (factor 1.0)."
            )


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
