"""
Streamlit entry point for the Cost Estimation Engine.

Run with:  streamlit run app.py

Router foundation copied from the Data Quality app: a ``current_step ->
renderer`` dispatch, one sidebar build, and one global stylesheet injected per
render. The step inventory is a placeholder single ``home`` step until the CEE
workflow is specified.
"""
from __future__ import annotations

import streamlit as st

from ui import step_home
from ui._theme import inject_global_css
from utils.session_state import (
    init_state,
    inject_sidebar_css,
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
    "home": step_home.render,
}


def main() -> None:
    init_state()

    inject_sidebar_css()
    render_sidebar_brand()
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
