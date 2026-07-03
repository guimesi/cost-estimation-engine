"""Slim re-export shim preserving a single import surface for session helpers.

Implementation lives under ``utils/session/*``. Add new symbols to BOTH the
sub-module and the ``__all__`` list here.
"""
from __future__ import annotations

from utils.session.navigation import (
    consume_scroll_to_top,
    goto,
    next_step,
    prev_step,
    restart_app,
)
from utils.session.sidebar import (
    inject_sidebar_css,
    render_progress_sidebar,
    render_sidebar_brand,
    render_sidebar_footer,
)
from utils.session.state import (
    STEP_LABELS,
    STEPS,
    clear_run_state,
    init_state,
    set_project,
)

__all__ = [
    "STEPS",
    "STEP_LABELS",
    "init_state",
    "set_project",
    "clear_run_state",
    "next_step",
    "prev_step",
    "goto",
    "restart_app",
    "consume_scroll_to_top",
    "inject_sidebar_css",
    "render_sidebar_brand",
    "render_progress_sidebar",
    "render_sidebar_footer",
]
