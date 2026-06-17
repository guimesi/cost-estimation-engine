"""End-to-end UI smoke test via Streamlit AppTest (mock data)."""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from src.adr_repository import list_projects, load_project_lines
from src.emma_reference import available_selections, load_lrc, load_mfc
from src.estimation_engine import run_estimation

APP = "app.py"


def _click(at, label):
    for b in at.button:
        if b.label == label:
            b.click().run()
            return
    raise AssertionError(f"button {label!r} not found; have {[b.label for b in at.button]}")


def test_step1_renders_without_error():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert any("Select a project" in m.value for m in at.subheader)


def test_full_click_flow_to_results():
    at = AppTest.from_file(APP).run()
    pid = list_projects()[0].project_id

    # Step 1: select a project, then advance.
    at.button(key=f"pick_{pid}").click().run()
    assert not at.exception
    assert at.session_state["selected_project_id"] == pid
    _click(at, "Next →")
    assert at.session_state["current_step"] == "parameters"

    # Step 2: Back returns to project selection, then forward again.
    _click(at, "← Back")
    assert at.session_state["current_step"] == "project_selection"
    _click(at, "Next →")

    # Step 2: defaults are valid; run the estimation.
    _click(at, "Estimate →")
    assert not at.exception
    assert at.session_state["current_step"] == "results"
    assert at.session_state["result"] is not None

    # Results: Restart resets everything back to the start.
    _click(at, "Restart")
    assert at.session_state["current_step"] == "project_selection"
    assert at.session_state["selected_project_id"] is None
    assert at.session_state["result"] is None


def test_results_step_renders_with_seeded_result():
    project = list_projects()[0]
    selection = available_selections()[0]
    result = run_estimation(
        project, load_project_lines(project.project_id), load_mfc(), load_lrc(), selection
    )
    at = AppTest.from_file(APP)
    at.session_state["selected_project_id"] = project.project_id
    at.session_state["selection"] = selection
    at.session_state["result"] = result
    at.session_state["current_step"] = "results"
    at.run()
    assert not at.exception
    # Two CSV download buttons present.
    assert len(at.get("download_button")) == 2
