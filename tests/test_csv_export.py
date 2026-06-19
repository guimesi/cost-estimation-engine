"""CSV export builders."""
from __future__ import annotations

import pandas as pd

from src.adr_repository import list_projects, load_project_lines
from src.csv_export import build_lines_csv, build_summary_csv
from src.emma_reference import available_selections, load_lrc, load_mfc
from src.estimation_engine import run_estimation


def _result():
    project = list_projects()[0]
    lines = load_project_lines(project.project_id)
    selection = available_selections()[0]
    return run_estimation(project, lines, load_mfc(), load_lrc(), selection)


def test_lines_csv_has_rows_and_updated_columns():
    result = _result()
    csv = build_lines_csv(result)
    assert csv.count("\n") - 1 == result.n_lines  # header + one row per line
    assert "TOTAL_COST_NEW" in csv
    assert "BASE_MATERIAL_FACTOR" in csv
    assert "QUANTITY" in csv  # shown for visualization, not used in any formula


def test_summary_csv_has_cost_and_hours():
    result = _result()
    import io

    frame = pd.read_csv(io.StringIO(build_summary_csv(result)))
    assert set(frame["MEASURE"]) == {"Cost", "Hours"}
    assert "Total Cost" in set(frame["CATEGORY"])
    assert "Total Hours" in set(frame["CATEGORY"])
    assert {"ORIGINAL", "UPDATED", "DELTA", "PCT_CHANGE"}.issubset(frame.columns)
