"""ADR repository: project listing + latest-snapshot line loading."""
from __future__ import annotations

import pytest

from config.schema import (
    ADR_LINE_NUMERIC_COLUMNS,
    COL_BASE_MATERIAL_MFC,
    COL_PROJECT_ID,
    COL_SNAPSHOT_ID,
)
from src import adr_repository as repo


def test_list_projects_returns_latest_snapshot():
    projects = repo.list_projects()
    assert projects
    for p in projects:
        # Mock data has snapshots {1, 2}; latest must be 2.
        assert p.snapshot_id == 2
        assert p.n_items > 0


def test_load_project_lines_has_canonical_columns():
    pid = repo.list_projects()[0].project_id
    lines = repo.load_project_lines(pid)
    assert (lines[COL_PROJECT_ID] == pid).all()
    assert (lines[COL_SNAPSHOT_ID] == 2).all()
    for col in (*ADR_LINE_NUMERIC_COLUMNS, COL_BASE_MATERIAL_MFC):
        assert col in lines.columns


def test_load_unknown_project_raises():
    with pytest.raises(KeyError):
        repo.load_project_lines("PRJ-DOES-NOT-EXIST")
