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

EMMA has its **own** source knob, `EMMA_SOURCE` (`mock`/`excel`/`snowflake`,
defaults to `DATA_SOURCE`), so ADR can come from Snowflake while the MFC/LRC
factors are read from local Excel workbooks - the interim setup until those
tables land in Snowflake. With `EMMA_SOURCE=excel`, drop the two workbooks in
`EMMA_DIR` (default `data/`); `src/emma_excel.py` loads them.

> **Heads-up - the EMMA files are named inverted vs. the spec.** The doc calls
> the per-commodity workbook `MFC.xlsx` (Material) and the multiplier+USD-rate
> workbook `LRC.xlsx` (Labor), and the engine's canonical names follow the doc
> (`MFC_*`=material per code, `LRC_*`=labor). But the real exports were observed
> with their contents crossed (the file named `MFC.xlsx` held the labor columns
> and vice-versa). So the Excel loader **routes each file by its columns, not
> its filename**: a workbook with a `code` column -> Material/MFC frame; a
> workbook with `factorMultiplier`+`totalUSDRate` (no code) -> Labor/LRC frame.
> Correct under either naming; the engine and schema were NOT renamed. (business
> Q8, 2026-06-19: confirmed - ignore filenames, route by content: labor has USD
> rates, material has codes.)

Tests always run against `mock` (autouse fixture in `tests/conftest.py` pins
both `data_source` and `emma_source` to `mock`).

## The workflow (welcome + 3 steps)

`utils/session/state.py::STEPS` = `project_selection` -> `parameters` ->
`results`. `app.py` routes `current_step` to the matching `ui/step_*.render`.

A `welcome` landing screen (`ui/step_welcome.py`) precedes the flow and is the
initial `current_step`. It is deliberately NOT in `STEPS`: `STEPS` is the
*numbered* workflow (the sidebar stepper and each step's "1./2./3." heading), so
the landing sits at "step 0" outside that numbering (`WELCOME_STEP` constant).
Its "▶ Start" button `goto`s `STEPS[0]`. `restart_app`/`clear_run_state` reset
back to the `welcome` landing (so "Restart" returns to step 0). The stepper
shows all-todo when `current_step` isn't in `STEPS`.

1. `step_project_selection` - pick a project with ADR estimations (latest
   snapshot). The selected card shows the project's ORIGINAL pricing context
   (`ProjectRef.original_period`, from `COST_UPDATE`; the original location is
   not recorded in ADR). Sets `selected_project_id`.
2. `step_parameters` - choose Location + Period (any pair with an LRC labor
   factor; missing material coverage is flagged, see Q7). The caption repeats
   the original pricing period as the reference point. Runs the engine, stores
   the `EstimationResult` in `session_state.result`.
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
  adr_repository.py            # list_projects + load_project_lines; mock joins
                               #   in memory, Snowflake aggregates + reads one
                               #   project's lines projected/filtered server-side
  emma_reference.py            # load_mfc/load_lrc, available_selections,
                               #   lrc_lookup, mfc_factor_map
  emma_excel.py                # EMMA_SOURCE=excel loader; routes workbooks to
                               #   material/labor frames by COLUMNS, not filename
  estimation_engine.py         # estimate_lines (vectorized) + run_estimation
  diagnostics.py               # mfc_coverage: pre-flight MFC factor coverage
  csv_export.py                # build_lines_csv / build_summary_csv
ui/
  _theme.py                    # one global stylesheet
  _data.py                     # st.cache_data wrappers over the src data layer
  step_welcome.py              # step 0: landing screen + "▶ Start"
  step_project_selection.py / step_parameters.py / step_results.py
utils/
  colors.py                    # STATUS_GREEN/YELLOW/RED (single source)
  helpers.py                   # fmt_money/fmt_hours/fmt_pct(+_change) + delta_color(_from)
  session_state.py             # slim re-export shim over utils/session/*
  session/                     # state.py / navigation.py / sidebar.py
tests/                         # pytest + ruff, ~95% coverage
```

## Calculation rules (the core contract)

Implemented in `src/estimation_engine.py::estimate_lines`, vectorized:

```
# Labor (LRC factor F + USD rate USD_R for the selected location/period,
# applied to ALL THREE labor categories):
SPEC_H_NEW        = DB_SPEC_H        * F   SPEC_COST_NEW        = SPEC_H_NEW        * USD_R
FSF_H_NEW         = DB_FSF_H         * F   FSF_COST_NEW         = FSF_H_NEW         * USD_R
FIELD_LABOR_H_NEW = DB_FIELD_LABOR_H * F   FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R
# Material (MFC factor matched per line code, location, period):
BASE_MATERIAL_COST_NEW   = DB_BM_C  * F_mfc[BASE_MATERIAL_MFC]
VENDOR_SHOP_FAB_COST_NEW = DB_VSF_C * F_mfc[VENDOR_SHOP_FAB_MFC]
# Totals:
TOTAL_HOURS_NEW = SPEC_H_NEW + FSF_H_NEW + FIELD_LABOR_H_NEW
TOTAL_COST_NEW  = VSF + SPEC + BM + FSF + FIELD_LABOR  (the 5 *_NEW costs)
```

### Assumptions log (where the doc was ambiguous - confirmed with the user)

1. **Field Labor IS re-estimated** (business Q1 answer, 2026-06-19: the spec
   gained a Field Labor Calculation). It uses the same LRC factor F + USD rate
   as the other labor categories: `FIELD_LABOR_H_NEW = DB_FIELD_LABOR_H * F`,
   `FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R`. (Previously a pass-through
   while the spec was silent; it now varies with location/period like the rest.)
2. **One LRC factor + USD rate per (location, period) applies to ALL THREE labor
   categories** (Specialty Subcontractor, Field Shop Fabrication, Field Labor).
   LRC has no labor-type code.
3. **Mock ADR table split is a modeling choice; the REAL ADR schema diverges.**
   `src/mock_data.py` builds ONE master row per item and projects it onto the 4
   tables on shared keys (`ITEM_ID`, `SNAPSHOT_ID`, `PROJECT_ID`);
   `adr_repository._join_tables` reconstructs the canonical frame (mock path,
   which loads the whole small universe in memory).
   The live Snowflake schema (reconciled in `adr_repository._sf_load_project_lines`
   / `_sf_list_projects`, maps in `config/schema.py`, verified via
   `scripts/inspect_adr_schema.py`) is different and handled separately:
   - **Item join key is `ROW_ID`** (-> canonical `ITEM_ID`), not a composite.
   - **`ADR_DIM_ESTIMATEDESIGNDETAILS` is an EAV table** (one row per design
     parameter) carrying nothing the engine needs, so it is NOT joined - only
     item record + cost results + qty are.
   - **Project = `PLANVIEW_ID`**; display name = `FILE_NAME`.
   - **Snapshot = `SNAPSHOT`** (stage-gate label, e.g. `GATE3`), ranked by
     `SNAPSHOT_PRIORITY` (SCREEN < GATE1 < ... < GATE3); "latest snapshot" =
     highest-ranked gate per project, always auto-selected (business Q5,
     2026-06-19: Gate3 newest > Gate2 > Screen oldest; no per-gate user choice).
     `ProjectRef.snapshot_id` is therefore `int | str` (gate label in Snowflake,
     int in mock).
   - Some databook values arrive as **strings** ("0", "9.47") and are coerced.
   - **Reads are pushed to Snowflake, not pulled whole** (the real base is ~800k
     rows × dozens of columns): `list_projects` runs a `GROUP BY PLANVIEW_ID,
     SNAPSHOT` aggregation (one row per project×snapshot, no line items);
     `load_project_lines` reads only the chosen project's latest-snapshot rows,
     **projected to the needed columns** (`SnowflakeClient.fetch_table(columns=)`
     = the rename-map keys) and filtered server-side (`WHERE PLANVIEW_ID=%s`;
     cost/qty have no project key so they're filtered by a `ROW_ID IN (subquery)`
     on the item table). The `ui/_data.py` `st.cache_data` layer then makes
     re-opening a project instant.
   The engine and UI never change - all of this lives in the repo + schema.
4. **Missing MFC factor for a line's code** -> factor `1.0` (cost unchanged)
   plus a recorded warning, never a dropped line (confirmed by business Q3,
   2026-06-19). Each line ALSO carries an explicit
   `BASE_MATERIAL_FACTOR_MISSING` / `VENDOR_SHOP_FAB_FACTOR_MISSING` flag
   (in the CSV + the step-3 line table) so a missing factor is distinguishable
   from a real factor that equals 1.0. (A broader data-quality rule ensuring
   every material has a valid MFC is a separate follow-up, owned by the data
   pipeline, not this engine.) **Missing LRC** for the selection raises
   `LookupError` (a guard - the UI only offers selections present in both
   references).
5. **Databook `DB_*` values are quantity-inclusive line totals** (business Q4,
   2026-06-19): factors are applied directly to them and the engine never
   multiplies by `QUANTITY`. `QUANTITY` is carried for **display only** (shown
   in the step-3 line table and the line-level CSV), not used in any formula.
6. **The comparison names both estimation contexts** (doc v2, 2026-07-02,
   section 8): the ORIGINAL side's context is its pricing period (the original
   *location* is not recorded in ADR, so it is time-only); the NEW side's is the
   user's Location + Period selection. **Doc v2 points the period at
   `COST_BASIS`, but the real data disagrees** (verified via
   `scripts/inspect_cost_basis.py`, 2026-07-03 - same doc-vs-data inversion
   pattern as the EMMA filenames): `COST_UPDATE` holds the clean quarterly
   period ("2Q2019"), constant per project/gate, while `COST_BASIS` is a
   free-text pricing-basis/scenario label ("TA"/"NTA", "Fab Yard - China")
   that varies between items. So `EstimationResult.original_period` summarizes
   `COL_COST_UPDATE` (mode of non-blank values, else "n/a") and drives the
   step-3 context caption/headers + the summary CSV (`ORIGINAL_PERIOD` /
   `NEW_LOCATION_PERIOD`); `COL_COST_BASIS` is carried per line (line-level CSV)
   only. `ProjectRef.original_period` surfaces the same period in steps 1-2
   (Snowflake: `MODE(COST_UPDATE)` inside the `list_projects` aggregation; mock:
   mode per group). Both canonical, mock derives them without consuming the RNG.
   Display only - no formula uses them.

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

- **The UI offers `labor_selections()` = every LRC (location, period) pair**
  (business Q7, 2026-06-19: let users pick any labor pair and flag missing
  material rather than hiding it). Labor is re-estimated from location+period
  alone, so the engine's LRC lookup is valid for every offered pair (the
  `LookupError` is a guard, not a normal path); material with no MFC factor is
  flagged (step-2 coverage warning + per-line flag), not blocked.
  `available_selections()` is the stricter **MFC-and-LRC intersection** (fully
  material-covered pairs) and `labor_only_selections()` the LRC-only pairs; both
  are kept for reference/diagnostics but the UI no longer restricts to the
  intersection. If you bypass the UI (tests), any `labor_selections()` pair runs;
  a pair with no MFC just yields all-material-unchanged + warnings.
- **Mock determinism**: every mock frame is built once at import with a
  fixed-seed RNG (`_seed(name)` via `zlib.crc32`, process-stable). The 4 ADR
  tables are projections of one master, so the join always reconstructs the
  same rows. Don't introduce `Math.random`-style nondeterminism or per-call
  rebuilds.
- **`SnowflakeClient._resolve_location` reads `SETTINGS` directly** (no domain
  registry here, unlike the sibling app). If CEE grows domains, reintroduce a
  domain-preferring resolver.
```
