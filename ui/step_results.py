"""Step 3 - dashboard: original vs updated comparison + CSV downloads.

Every cost/hours value carries a hover tooltip (``.cee-tip`` in the global
theme) with the calculation rationale: the formula, the factors actually
applied in this run (LRC F + USD rate; blended MFC factor), and the context of
each side of the comparison.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.schema import (
    COL_BASE_MATERIAL_CODE_MISSING,
    COL_BASE_MATERIAL_FACTOR_MISSING,
    COL_DESCRIPTION,
    COL_EXECUTION_SPLIT,
    COL_ITEM_ID,
    COL_LRC_FACTOR,
    COL_LRC_USD_RATE,
    COL_QUANTITY,
    COL_TOTAL_COST_NEW,
    COL_TOTAL_COST_ORIG,
    COL_TOTAL_HOURS_NEW,
    COL_TOTAL_HOURS_ORIG,
    COL_VENDOR_SHOP_FAB_CODE_MISSING,
    COL_VENDOR_SHOP_FAB_FACTOR_MISSING,
    COL_WBS,
    COST_CATEGORIES,
    HOUR_CATEGORIES,
)
from src.csv_export import build_lines_csv, build_summary_csv
from src.models import Comparison, EstimationResult
from utils.helpers import delta_color_from, fmt_hours, fmt_money, fmt_pct_change, fmt_qty
from utils.session.navigation import prev_step, restart_app

# Neutral baseline fill for the "Original" series (not a status colour, so it
# stays a local literal rather than living in utils.colors).
_NEUTRAL_GRAY = "#94a3b8"

_DELTA_TIP = "Δ = Updated - Original"
_PCT_TIP = "% change = (Updated - Original) / Original × 100"


def _tip_html(text: str, tip: str) -> str:
    """Wrap ``text`` in a hover tooltip carrying the calculation rationale."""
    if not tip:
        return text
    return f'<span class="cee-tip" data-tip="{escape(tip)}">{text}</span>'


def _run_rationale(result: EstimationResult) -> dict:
    """Tooltip texts explaining how each number of this run was computed.

    Keys: ``cost_orig`` / ``cost_new`` / ``hour_orig`` / ``hour_new`` (dicts by
    category key) plus ``total_cost_orig`` / ``total_cost_new`` /
    ``total_hours_orig`` / ``total_hours_new``. All factors quoted are the ones
    actually applied: the LRC pair is constant per run; MFC varies per line
    code, so the material tooltips show the blended effective factor.
    """
    lines = result.lines
    f_lrc = float(lines[COL_LRC_FACTOR].iloc[0])
    usd = float(lines[COL_LRC_USD_RATE].iloc[0])
    n = result.n_lines
    sel = result.selection.label
    orig_ctx = f"original estimate, priced {result.original_period}"
    labor_facts = f"F (LRC labor multiplier) = {f_lrc:.3f}\nUSD rate = ${usd:,.2f}/h"

    hour_cats = {c.key: c for c in HOUR_CATEGORIES}
    missing_by_key = {
        "bm": int(lines[COL_BASE_MATERIAL_FACTOR_MISSING].sum()),
        "vsf": int(lines[COL_VENDOR_SHOP_FAB_FACTOR_MISSING].sum()),
    }
    no_code_by_key = {
        "bm": int(lines[COL_BASE_MATERIAL_CODE_MISSING].sum()),
        "vsf": int(lines[COL_VENDOR_SHOP_FAB_CODE_MISSING].sum()),
    }

    cost_orig, cost_new, hour_orig, hour_new = {}, {}, {}, {}
    for c in HOUR_CATEGORIES:
        hour_orig[c.key] = (
            f"Sum of {c.orig_col} over the {n} included line(s)\n({orig_ctx})."
        )
        hour_new[c.key] = (
            f"{c.new_col} = {c.orig_col} × F\n{labor_facts}\n"
            f"Applied per line and summed over {n} line(s)\nfor {sel}."
        )
    for c in COST_CATEGORIES:
        cost_orig[c.key] = (
            f"Sum of {c.orig_col} over the {n} included line(s)\n({orig_ctx})."
        )
        if c.key in hour_cats:  # labor: recomputed from hours
            h = hour_cats[c.key]
            cost_new[c.key] = (
                f"{c.new_col} = ({h.orig_col} × F) × USD rate\n{labor_facts}\n"
                f"Applied per line and summed over {n} line(s)\nfor {sel}."
            )
        else:  # material: original cost scaled by the per-code MFC factor
            cmp = next(x for x in result.cost_categories if x.key == c.key)
            eff = f"{cmp.updated / cmp.original:.3f}" if cmp.original else "n/a"
            missing = missing_by_key.get(c.key, 0)
            no_code = no_code_by_key.get(c.key, 0)
            miss_note = (
                f"\n⚠ {missing} line(s) had no MFC factor (kept at 1.0)."
                if missing
                else ""
            )
            no_code_note = (
                f"\n∅ {no_code} line(s) have no MFC code (updated cost 0)."
                if no_code
                else ""
            )
            cost_new[c.key] = (
                f"{c.new_col} = {c.orig_col} × MFC factor\n"
                f"Factor matched per line's material code for {sel}.\n"
                f"Blended effective factor = {eff}{miss_note}{no_code_note}"
            )

    cost_labels = " + ".join(c.label for c in COST_CATEGORIES)
    hour_labels = " + ".join(c.label for c in HOUR_CATEGORIES)
    return {
        "cost_orig": cost_orig,
        "cost_new": cost_new,
        "hour_orig": hour_orig,
        "hour_new": hour_new,
        "total_cost_orig": (
            f"TOTAL_COST_ORIG = {cost_labels}\n"
            f"(the 5 original category costs; {orig_ctx})."
        ),
        "total_cost_new": (
            f"TOTAL_COST_NEW = {cost_labels}\n"
            f"Labor: hours × F × USD rate · Material: cost × MFC factor\n"
            f"{labor_facts}\nSelection: {sel}."
        ),
        "total_hours_orig": (
            f"TOTAL_HOURS_ORIG = {hour_labels}\n"
            f"(the 3 original labor hour categories; {orig_ctx})."
        ),
        "total_hours_new": (
            f"TOTAL_HOURS_NEW = {hour_labels}\n"
            f"Each = original hours × F\nF (LRC labor multiplier) = {f_lrc:.3f}\n"
            f"Selection: {sel}."
        ),
    }


def render() -> None:
    result: EstimationResult = st.session_state.get("result")
    if result is None:
        st.info("Run an estimation first.")
        st.button("← Back", on_click=prev_step)
        return

    st.subheader("3. Estimation result")
    header = f"**{result.project.label}** · {result.selection.label} · {result.n_lines} items"
    if COL_EXECUTION_SPLIT in result.lines.columns:
        included = sorted(result.lines[COL_EXECUTION_SPLIT].astype(str).unique())
        header += f" · splits: {', '.join(included)}"
    st.caption(header)
    # Doc v2 section 8: the comparison names both contexts. The original's
    # location is not recorded in ADR, so its context is time-only: the
    # COST_UPDATE pricing period (doc v2 says COST_BASIS, but the real data
    # keeps the period in COST_UPDATE; COST_BASIS is a per-line scenario label).
    orig_ctx = f"priced {result.original_period}"
    new_ctx = result.selection.label
    st.caption(
        f"Comparing **original** ({orig_ctx}; location not recorded in ADR) vs "
        f"**updated** ({new_ctx})."
    )

    for w in result.warnings:
        st.warning(w)

    tips = _run_rationale(result)
    st.caption("💡 Hover any value to see how it was calculated.")

    _render_totals(result, tips)
    st.divider()
    _render_category_breakdown(
        "Cost by category", result.cost_categories, fmt_money, orig_ctx, new_ctx,
        tips["cost_orig"], tips["cost_new"],
    )
    _render_chart(
        "Cost by category (USD)", result.cost_categories,
        tips["cost_orig"], tips["cost_new"],
    )
    _render_category_breakdown(
        "Hours by category", result.hour_categories, fmt_hours, orig_ctx, new_ctx,
        tips["hour_orig"], tips["hour_new"],
    )
    _render_chart(
        "Hours by category", result.hour_categories,
        tips["hour_orig"], tips["hour_new"],
    )

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


def _render_totals(result: EstimationResult, tips: dict) -> None:
    c1, c2 = st.columns(2)
    with c1:
        _total_metric(
            "Total Cost", result.total_cost, fmt_money,
            tips["total_cost_orig"], tips["total_cost_new"],
        )
    with c2:
        _total_metric(
            "Total Hours", result.total_hours, fmt_hours,
            tips["total_hours_orig"], tips["total_hours_new"],
        )


def _total_metric(label: str, cmp: Comparison, fmt, orig_tip: str, new_tip: str) -> None:
    st.markdown(
        f'<div class="cee-card"><h4>{label}</h4>'
        f"<p>Original: <b>{_tip_html(fmt(cmp.original), orig_tip)}</b><br>"
        f"Updated: <b>{_tip_html(fmt(cmp.updated), new_tip)}</b></p>"
        f"<p>{_tip_html(f'Δ {fmt(cmp.delta)}', _DELTA_TIP)} "
        f'<span style="color:{delta_color_from(cmp.original, cmp.updated)}">'
        f"({_tip_html(fmt_pct_change(cmp.original, cmp.updated), _PCT_TIP)})"
        f"</span></p></div>",
        unsafe_allow_html=True,
    )


def _render_category_breakdown(
    title: str, comps, fmt, orig_ctx: str, new_ctx: str,
    orig_tips: dict, new_tips: dict,
) -> None:
    """Per-category comparison table, with each side's context in its header.

    Doc v2 section 8 asks the comparison to carry the original estimation's
    location/time (COST_BASIS period; location missing from ADR) and the new
    estimation's location/time (the user's selection). Both are constant per
    run, so they live in the column headers rather than repeated per row.

    Rendered as an HTML ``.cee-cmp`` table (not ``st.dataframe``) so every
    value can carry a ``.cee-tip`` hover with its calculation rationale.
    """
    st.markdown(f"#### {title}")
    head = (
        f"<tr><th>Category</th><th class='num'>Original ({escape(orig_ctx)})</th>"
        f"<th class='num'>Updated ({escape(new_ctx)})</th>"
        f"<th class='num'>Δ</th><th class='num'>% change</th></tr>"
    )
    rows = []
    for c in comps:
        rows.append(
            f"<tr><td>{escape(c.label)}</td>"
            f"<td class='num'>{_tip_html(fmt(c.original), orig_tips.get(c.key, ''))}</td>"
            f"<td class='num'>{_tip_html(fmt(c.updated), new_tips.get(c.key, ''))}</td>"
            f"<td class='num'>{_tip_html(fmt(c.delta), _DELTA_TIP)}</td>"
            f"<td class='num'>"
            f"{_tip_html(fmt_pct_change(c.original, c.updated), _PCT_TIP)}</td></tr>"
        )
    st.markdown(
        f"<table class='cee-cmp'>{head}{''.join(rows)}</table>",
        unsafe_allow_html=True,
    )


def _render_chart(title: str, comps, orig_tips: dict, new_tips: dict) -> None:
    labels = [c.label for c in comps]
    # Colour each Updated bar by the direction of its change: a category whose
    # cost/hours went up is red, down is green, flat/undefined yellow - the same
    # semantics as the totals delta (utils.helpers.delta_color_from).
    updated_colors = [delta_color_from(c.original, c.updated) for c in comps]
    # Bar hover carries the same calculation rationale as the table tooltips.
    hover = "%{x}<br><b>%{y:,.2f}</b><br><br>%{customdata}<extra></extra>"

    def _cd(tips):
        return [tips.get(c.key, "").replace("\n", "<br>") for c in comps]

    fig = go.Figure()
    fig.add_bar(name="Original", x=labels, y=[c.original for c in comps],
                marker_color=_NEUTRAL_GRAY,
                customdata=_cd(orig_tips), hovertemplate=hover)
    fig.add_bar(name="Updated", x=labels, y=[c.updated for c in comps],
                marker_color=updated_colors,
                customdata=_cd(new_tips), hovertemplate=hover)
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
        code_missing = (
            view[COL_BASE_MATERIAL_CODE_MISSING]
            | view[COL_VENDOR_SHOP_FAB_CODE_MISSING]
        )
        # A line can hit both cases (one side without code, the other without
        # factor); the no-code marker wins since cost 0 is the stronger effect.
        mfc_status = pd.Series("", index=view.index)
        mfc_status[mfc_missing] = "⚠ missing"
        mfc_status[code_missing] = "∅ no code (0)"
        table = pd.DataFrame(
            {
                "Item": view[COL_ITEM_ID].astype(str),
                "WBS": view[COL_WBS].astype(str),
                "Description": view[COL_DESCRIPTION].astype(str),
                "Qty": view[COL_QUANTITY].map(fmt_qty),
                "MFC": mfc_status,
                "Cost (orig)": view[COL_TOTAL_COST_ORIG].map(fmt_money),
                "Cost (new)": view[COL_TOTAL_COST_NEW].map(fmt_money),
                "Δ Cost": (view[COL_TOTAL_COST_NEW] - view[COL_TOTAL_COST_ORIG]).map(
                    fmt_money
                ),
                "Hours (orig)": view[COL_TOTAL_HOURS_ORIG].map(fmt_hours),
                "Hours (new)": view[COL_TOTAL_HOURS_NEW].map(fmt_hours),
            }
        )
        st.dataframe(
            table, hide_index=True, use_container_width=True,
            column_config={
                "Qty": st.column_config.TextColumn(
                    "Qty",
                    help="Display only - never used in a formula (original "
                         "values are already quantity-inclusive line totals).",
                ),
                "MFC": st.column_config.TextColumn(
                    "MFC",
                    help="⚠ when the line's material code has no MFC factor "
                         "for the selection; its material cost is kept "
                         "unchanged (factor 1.0).",
                ),
                "Cost (orig)": st.column_config.TextColumn(
                    "Cost (orig)",
                    help="TOTAL_COST_ORIG = sum of the line's 5 original "
                         "category costs (Spec + VSF + Base Material + FSF + "
                         "Field Labor).",
                ),
                "Cost (new)": st.column_config.TextColumn(
                    "Cost (new)",
                    help="TOTAL_COST_NEW = sum of the 5 recalculated costs. "
                         "Labor: hours × F × USD rate; material: cost × MFC "
                         "factor per code.",
                ),
                "Δ Cost": st.column_config.TextColumn(
                    "Δ Cost", help="Cost (new) - Cost (orig).",
                ),
                "Hours (orig)": st.column_config.TextColumn(
                    "Hours (orig)",
                    help="TOTAL_HOURS_ORIG = sum of the line's 3 original "
                         "labor hour categories.",
                ),
                "Hours (new)": st.column_config.TextColumn(
                    "Hours (new)",
                    help="TOTAL_HOURS_NEW = sum of the 3 recalculated hour "
                         "categories (each = original hours × F).",
                ),
            },
        )
        if mfc_missing.any():
            st.caption(
                "⚠ MFC missing: no material factor for the selection; that line's "
                "material cost was left unchanged (factor 1.0)."
            )
        if code_missing.any():
            st.caption(
                "∅ no code (0): the line has no MFC code in ADR; the material "
                "calculation is not executed and its updated cost is 0."
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
