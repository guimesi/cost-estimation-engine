"""Step 1 project search: filter by PlanView ID OR name, case-insensitive."""
from __future__ import annotations

from src.models import ProjectRef
from ui.step_project_selection import _filter

_PROJECTS = [
    ProjectRef(project_id="PV-10293", project_name="Unit 4 Revamp", snapshot_id="GATE3", n_items=1204),
    ProjectRef(project_id="PV-10311", project_name="Cooling Loop Expansion", snapshot_id="GATE2", n_items=862),
    ProjectRef(project_id="PV-20055", project_name="Tank Farm Phase 2", snapshot_id="GATE3", n_items=2011),
]


def test_empty_query_returns_all():
    assert _filter(_PROJECTS, "") == _PROJECTS
    assert _filter(_PROJECTS, "   ") == _PROJECTS


def test_filter_by_planview_id():
    out = _filter(_PROJECTS, "10311")
    assert [p.project_id for p in out] == ["PV-10311"]


def test_filter_by_name_case_insensitive():
    out = _filter(_PROJECTS, "tank farm")
    assert [p.project_id for p in out] == ["PV-20055"]


def test_filter_matches_id_or_name():
    # "10" hits two PlanView IDs; "revamp" hits one name - the union is by token,
    # but a single query matches a project if it's in EITHER field.
    assert {p.project_id for p in _filter(_PROJECTS, "PV-10")} == {"PV-10293", "PV-10311"}
    assert {p.project_id for p in _filter(_PROJECTS, "REVAMP")} == {"PV-10293"}


def test_no_match_returns_empty():
    assert _filter(_PROJECTS, "zzz") == []
