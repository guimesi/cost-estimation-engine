# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repo.
The README is for humans; this file is the working map.

## What this app is

The **Cost Estimation Engine** - a Streamlit + Snowflake app that re-estimates
an existing **ADR** project estimate for a user-chosen **Location** + **Time
Period** by applying **EMMA** market factors (MFC for materials, LRC for
labor), then shows an original-vs-updated comparison and exports a CSV.

It was bootstrapped from the sibling [`data-quality-app`](../data-quality-app)
and reuses that foundation: the Snowflake client, env-driven settings,
`mock`/`snowflake` switch, one global theme, session/router plumbing, and the
pytest + ruff + CI harness.

Two data-source modes via `DATA_SOURCE`:
- `mock` (default): deterministic synthetic ADR + EMMA from `src/mock_data.py`.
- `snowflake`: real reads through `src/snowflake_client.py`.

Tests always run against `mock` (autouse fixture in `tests/conftest.py`).

## The workflow (3 steps)

`utils/session/state.py::STEPS` = `project_selection` -> `parameters` ->
`results`. `app.py` routes `current_step` to the matching `ui/step_*.render`.

1. `step_project_selection` - pick a project with ADR estimations (latest
   snapshot). Sets `selected_project_id`.
2. `step_parameters` - choose Location + Period (only pairs present in BOTH MFC
   and LRC), runs the engine, stores the `EstimationResult` in
   `session_state.result`.
3. `step_results` - totals + per-category breakdown + grouped bar charts + two
   CSV downloads.

## Repo layout

```
app.py                         # router (current_step -> renderer)
config/
  settings.py                  # env-driven Settings (DATA_SOURCE + Snowflake)
  schema.py                    # SINGLE SOURCE for canonical column names,
                               #   ADR table names, COST/HOUR category tuples,
                               #   and raw->canonical EMMA rename maps
src/
  models.py                    # ProjectRef / FactorSelection / Comparison /
                               #   EstimationResult
  snowflake_client.py          # connector wrapper (fetch_table / fetch_query)
  mock_data.py                 # deterministic ADR master -> 4 tables + EMMA
  adr_repository.py            # list_projects + load_project_lines (joins the
                               #   4 ADR tables, latest snapshot per project)
  emma_reference.py            # load_mfc/load_lrc, available_selections,
                               #   lrc_lookup, mfc_factor_map
  estimation_engine.py         # estimate_lines (vectorized) + run_estimation
  csv_export.py                # build_lines_csv / build_summary_csv
ui/
  _theme.py                    # one global stylesheet
  step_project_selection.py / step_parameters.py / step_results.py
utils/
  colors.py                    # STATUS_GREEN/YELLOW/RED (single source)
  helpers.py                   # fmt_money/fmt_hours/fmt_pct + delta_color
  session_state.py             # slim re-export shim over utils/session/*
  session/                     # state.py / navigation.py / sidebar.py
tests/                         # 39 tests, ~95% coverage
```

## Calculation rules (the core contract)

Implemented in `src/estimation_engine.py::estimate_lines`, vectorized:

```
# Labor (LRC factor F + USD rate USD_R for the selected location/period,
# applied to BOTH labor categories):
SPEC_H_NEW = DB_SPEC_H * F     SPEC_COST_NEW = SPEC_H_NEW * USD_R
FSF_H_NEW  = DB_FSF_H  * F     FSF_COST_NEW  = FSF_H_NEW  * USD_R
# Material (MFC factor matched per line code, location, period):
BASE_MATERIAL_COST_NEW   = DB_BM_C  * F_mfc[BASE_MATERIAL_MFC]
VENDOR_SHOP_FAB_COST_NEW = DB_VSF_C * F_mfc[VENDOR_SHOP_FAB_MFC]
# Field Labor: pass-through (no factor)
# Totals:
TOTAL_HOURS_NEW = SPEC_H_NEW + FSF_H_NEW + FIELD_LABOR_H_NEW
TOTAL_COST_NEW  = VSF + SPEC + BM + FSF + FIELD_LABOR  (the 5 *_NEW costs)
```

### Assumptions log (where the doc was ambiguous - confirmed with the user)

1. **Field Labor is a pass-through** - the doc lists `FIELD_LABOR` /
   `FIELD_LABOR_COST` only as totals inputs and gives no re-estimation formula,
   so the engine carries the ADR databook values unchanged.
2. **One LRC factor + USD rate per (location, period) applies to BOTH labor
   categories** (Specialty Subcontractor and Field Shop Fabrication). LRC has
   no labor-type code.
3. **Mock ADR table split is a modeling choice.** The doc names the 4 ADR
   tables but not their exact columns. `src/mock_data.py` builds ONE master
   row per item and projects it onto the 4 tables on shared keys
   (`ITEM_ID`, `SNAPSHOT_ID`, `PROJECT_ID`); `adr_repository._join_tables`
   reconstructs the canonical line frame. Real column names get reconciled
   there + in `config/schema.py` without touching the engine.
4. **Missing MFC factor for a line's code** -> factor `1.0` (cost unchanged)
   plus a recorded warning, never a dropped line. **Missing LRC** for the
   selection raises `LookupError` (a guard - the UI only offers selections
   present in both references).

## Patterns to follow (inherited from data-quality-app)

- **Canonical names in ONE place** (`config/schema.py`). The engine, repo, mock
  data, CSV and UI all import column-name constants from there - never hardcode
  a column string. A schema reconciliation is a one-file edit.
- **One global stylesheet; status hexes only in `utils/colors.py`** (injected
  via `__GREEN__`/`__YELLOW__`/`__RED__` sentinels in `ui/_theme.py`). Don't
  reintroduce a per-step `<style>` block or a hardcoded status hex.
- **Slim re-exports preserve public API** (`utils/session_state.py`). Add new
  symbols to BOTH the sub-module and the `__all__` list.
- **Engine is pure + vectorized.** `estimate_lines` does not mutate its input
  and uses column ops, not `.apply` row loops. Keep new calc here, UI-free and
  unit-tested.
- **Reference lookups don't silently pass.** A missing factor is warned/raised,
  not treated as success (see assumption 4).
- **`from __future__ import annotations` everywhere** - `ruff check` catches
  missing `typing` imports (F821) even though they don't fail at runtime.
- **Tests always run against `mock`** - the autouse fixture pins
  `SETTINGS.data_source = "mock"` on every module that imported it.

## How to run things

```bash
pip install -r requirements.txt
streamlit run app.py            # also: make run
DATA_SOURCE=mock pytest -q      # also: make test
ruff check .                    # matches CI
```

CI runs `ruff check` then `pytest` with `DATA_SOURCE=mock`
(`--cov-fail-under=90`; current ~95%).

## Adding things

- **A new cost/hour category**: add the canonical `*_NEW` column + a
  `CostCategory`/`HourCategory` tuple in `config/schema.py`, compute it in
  `estimate_lines`, and it automatically flows into totals, comparisons, the
  CSV, and the charts (they all iterate the category tuples).
- **A new workflow step**: add to `STEPS`/`STEP_LABELS` in
  `utils/session/state.py`, create `ui/step_*.py` with a `render()`, wire it
  into `STEP_RENDERERS` in `app.py`.
- **Wiring real Snowflake**: fill the raw→canonical maps in `config/schema.py`
  and verify the ADR table projections / join keys in `adr_repository` against
  the real schema. The engine and UI don't change.

## Friction points

- **`available_selections` is the intersection of MFC and LRC** (location,
  period). The UI only offers those pairs, which guarantees a valid LRC lookup
  for any selection - the `LookupError` in the engine is a guard, not a normal
  path. If you bypass the UI (tests), pick a selection from
  `available_selections()`.
- **Mock determinism**: every mock frame is built once at import with a
  fixed-seed RNG (`_seed(name)` via `zlib.crc32`, process-stable). The 4 ADR
  tables are projections of one master, so the join always reconstructs the
  same rows. Don't introduce `Math.random`-style nondeterminism or per-call
  rebuilds.
- **`SnowflakeClient._resolve_location` reads `SETTINGS` directly** (no domain
  registry here, unlike the sibling app). If CEE grows domains, reintroduce a
  domain-preferring resolver.
```
