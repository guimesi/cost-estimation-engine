"""
Streamlit entry point for the Cost Estimation Engine.

Run with:  streamlit run app.py

Router foundation from the data-quality-app: a ``current_step -> renderer``
dispatch, one sidebar build, and one global stylesheet per render. The flow is
three steps: pick a project -> choose Location + Period -> view the comparison
and download the CSV.
"""
from __future__ import annotations

import streamlit as st

from ui import step_parameters, step_project_selection, step_results, step_welcome
from ui._theme import inject_global_css
from utils.session_state import (
    consume_scroll_to_top,
    init_state,
    inject_sidebar_css,
    render_progress_sidebar,
    render_sample_mode_toggle,
    render_sidebar_brand,
    render_sidebar_footer,
)

st.set_page_config(
    page_title="Cost Estimation Engine",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

STEP_RENDERERS = {
    "welcome": step_welcome.render,
    "project_selection": step_project_selection.render,
    "parameters": step_parameters.render,
    "results": step_results.render,
}


def main() -> None:
    init_state()
    consume_scroll_to_top()

    inject_sidebar_css()
    render_sidebar_brand()
    render_progress_sidebar()
    render_sample_mode_toggle()
    render_sidebar_footer()

    inject_global_css()

    st.title("Cost Estimation Engine")

    current = st.session_state.current_step
    renderer = STEP_RENDERERS.get(current)
    if renderer is None:
        st.error(f"Unknown step: {current}")
        return
    renderer()


if __name__ == "__main__":
    main()
