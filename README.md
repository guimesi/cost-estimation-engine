# Cost Estimation Engine

A Streamlit + Snowflake app that re-estimates an existing ADR project estimate
for a user-selected **Location** and **Time Period** by applying EMMA market
factors (MFC for materials, LRC for labor), then shows an original-vs-updated
comparison and exports a CSV.

It shares its foundation with the sibling
[`data-quality-app`](../data-quality-app): the same Snowflake client,
env-driven settings, `mock`/`snowflake` data-source switch, global theme,
session/router plumbing, and pytest + ruff + CI harness.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # only needed for snowflake mode
streamlit run app.py          # or: make run
```

Default `DATA_SOURCE=mock` ships deterministic synthetic ADR + EMMA data, so
the full 3-step flow works with no Snowflake connection.

## The flow

1. **Project** — pick a project that has ADR estimations loaded (latest
   snapshot is used).
2. **Location & Period** — choose from the (Location, Period) pairs present in
   both the MFC and LRC reference data.
3. **Estimation** — see total cost & hours (original vs updated, absolute + %),
   a per-category breakdown (Specialty Subcontractor, Vendor Shop, Base
   Material, Field Shop Fabrication, Field Labor), grouped bar charts, and two
   CSV downloads (line-level + category summary).

## Calculation logic

For the selected location/period the engine pulls one labor factor + USD rate
(LRC) and a per-code material factor table (MFC):

| Category | Type | Formula |
|---|---|---|
| Specialty Subcontractor | labor | `SPEC_H_NEW = DB_SPEC_H × F_lrc` ; `SPEC_COST_NEW = SPEC_H_NEW × USD_R` |
| Field Shop Fabrication | labor | `FSF_H_NEW = DB_FSF_H × F_lrc` ; `FSF_COST_NEW = FSF_H_NEW × USD_R` |
| Base Material | material | `BASE_MATERIAL_COST_NEW = DB_BM_C × F_mfc[base_code]` |
| Vendor Shop Fabrication | material | `VENDOR_SHOP_FAB_COST_NEW = DB_VSF_C × F_mfc[vsf_code]` |
| Field Labor | pass-through | carried from ADR databook (no factor) |
| **Total Cost** | | `VSF + SPEC + BM + FSF + FIELD_LABOR` |
| **Total Hours** | | `SPEC_H + FSF_H + FIELD_LABOR_H` |

Confirmed interpretations of the spec: **Field Labor is a pass-through** (the
doc lists it only as a totals input), and the **single LRC factor per
(location, period) applies to both labor categories** (no labor-type code in
LRC). See [CLAUDE.md](CLAUDE.md) for the full assumptions log.

## Tests / lint

```bash
DATA_SOURCE=mock pytest -q    # 39 tests, ~95% coverage
ruff check .
```

CI ([.github/workflows/tests.yml](.github/workflows/tests.yml)) runs both with
`--cov-fail-under=90`.

## Layout

```
app.py                       # Streamlit router (current_step -> renderer)
config/
  settings.py                # env-driven Settings (DATA_SOURCE + Snowflake)
  schema.py                  # canonical column names, ADR table names, categories
src/
  models.py                  # ProjectRef / FactorSelection / Comparison / EstimationResult
  snowflake_client.py        # connector wrapper (fetch_table / fetch_query + shared client)
  mock_data.py               # deterministic ADR 4-table + EMMA MFC/LRC
  adr_repository.py          # list projects + join 4 ADR tables (latest snapshot)
  emma_reference.py          # MFC/LRC load + selections + factor lookups
  estimation_engine.py       # vectorized calc + run_estimation -> EstimationResult
  csv_export.py              # line-level + category-summary CSV
ui/
  _theme.py                  # one global stylesheet (status colours via sentinels)
  step_project_selection.py  # Step 1
  step_parameters.py         # Step 2
  step_results.py            # Step 3 (comparison + charts + downloads)
utils/
  colors.py / helpers.py     # status hexes + money/hours/% formatting
  session_state.py           # slim re-export shim over utils/session/*
  session/                   # state / navigation / sidebar
tests/                       # engine, emma, adr, csv, mock, helpers, snowflake, AppTest
```

## Snowflake mode

`adr_repository` and `emma_reference` branch on `SETTINGS.is_mock`. The
Snowflake path is wired (it reads the 4 ADR tables and the MFC/LRC references
through the shared client) but the exact source column names are placeholders —
reconcile the raw→canonical maps in [config/schema.py](config/schema.py)
(`MFC_RAW_RENAME` / `LRC_RAW_RENAME`) and the ADR table projections against the
real schema. The calculation engine never changes.
