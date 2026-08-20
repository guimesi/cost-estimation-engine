# Cost Estimation Engine

A Streamlit + Databricks app that re-estimates an existing ADR project estimate
for a user-selected **Location** and **Time Period** by applying EMMA market
factors (MFC for materials, LRC for labor), then shows an original-vs-updated
comparison and exports a CSV.

It shares its foundation with the sibling
[`data-quality-app`](../data-quality-app): the same Databricks client,
env-driven settings, `mock`/`databricks` data-source switch, global theme,
session/router plumbing, and pytest + ruff + CI harness. It deploys as a
**Databricks App** (see [deploy/README.md](deploy/README.md)).

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # only needed for databricks mode
streamlit run app.py          # or: make run
```

Default `DATA_SOURCE=mock` ships deterministic synthetic ADR + EMMA data, so
the full 3-step flow works with no warehouse connection.

## The flow

1. **Project** - pick a project that has ADR estimations loaded (latest
   snapshot is used).
2. **Location & Period** - pick which EXECUTION_SPLITs to include, then any
   (Location, Period) pair with an LRC labor factor; missing material (MFC)
   coverage is flagged, not hidden (business Q7).
3. **Estimation** - see total cost & hours (original vs updated, absolute + %),
   a per-category breakdown (Specialty Subcontractor, Vendor Shop, Base
   Material, Field Shop Fabrication, Field Labor), grouped bar charts, and two
   CSV downloads (line-level + category summary).

## Calculation logic

For the selected location/period the engine pulls one labor factor + USD rate
(LRC) and a per-code material factor table (MFC):

| Category | Type | Formula |
|---|---|---|
| Specialty Subcontractor | labor | `SPEC_H_NEW = SPEC_H_ORIG × F_lrc` ; `SPEC_COST_NEW = SPEC_H_NEW × USD_R` |
| Field Shop Fabrication | labor | `FSF_H_NEW = FSF_H_ORIG × F_lrc` ; `FSF_COST_NEW = FSF_H_NEW × USD_R` |
| Field Labor | labor | `FIELD_LABOR_H_NEW = FIELD_LABOR_H_ORIG × F_lrc` ; `FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW × USD_R` |
| Base Material | material | `BASE_MATERIAL_COST_NEW = BASE_MATERIAL_COST_ORIG × F_mfc[base_code]` |
| Vendor Shop Fabrication | material | `VENDOR_SHOP_FAB_COST_NEW = VENDOR_SHOP_FAB_COST_ORIG × F_mfc[vsf_code]` |
| **Total Cost** | | `VSF + SPEC + BM + FSF + FIELD_LABOR` (the 5 `*_NEW` costs) |
| **Total Hours** | | `SPEC_H + FSF_H + FIELD_LABOR_H` |

Confirmed interpretations of the spec: **Field Labor IS re-estimated** with the
same LRC factor (business Q1); the **single LRC factor + USD rate per
(location, period) applies to all three labor categories** (no labor-type code
in LRC); the engine's inputs are the un-prefixed `*_ORIG` cost-table columns -
the `DB_*` twins are databook reference, display-only (business Q11); a line
with **no MFC code** gets updated material cost **0** (business Q12), while a
code with **no factor** for the selection keeps its cost (factor 1.0) and is
flagged (business Q3). See [CLAUDE.md](CLAUDE.md) for the full assumptions
log.

## Tests / lint

```bash
DATA_SOURCE=mock pytest -q    # 76 tests, ~97% coverage
ruff check .
```

CI ([.github/workflows/tests.yml](.github/workflows/tests.yml)) runs both with
`--cov-fail-under=90`.

## Layout

```
app.py                       # Streamlit router (current_step -> renderer)
config/
  settings.py                # env-driven Settings (DATA_SOURCE + Databricks)
  schema.py                  # canonical column names, ADR table names, categories
src/
  models.py                  # ProjectRef / FactorSelection / Comparison / EstimationResult
  databricks_client.py       # SQL Warehouse wrapper (fetch_table / fetch_query + shared client)
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
tests/                       # engine, emma, adr, csv, mock, helpers, databricks, AppTest
```

## Databricks mode

`adr_repository` and `emma_reference` branch on `SETTINGS.is_mock`. The
Databricks path reads the ADR tables (and, once landed, the MFC/LRC reference
tables) from Unity Catalog - default namespace
`entai_sandbox_catalog.data_quality_scorecards`, table names identical to the
Snowflake originals - through a SQL Warehouse. Identity is resolved headlessly
by `databricks.sdk.core.Config`: the app service principal inside Databricks
Apps, or `DATABRICKS_HOST` + `DATABRICKS_TOKEN` locally (no browser auth). The
raw->canonical maps live in [config/schema.py](config/schema.py); the
calculation engine never changes.

Deploying to Databricks Apps (app creation, warehouse resource, Unity Catalog
grants) is documented in [deploy/README.md](deploy/README.md).
