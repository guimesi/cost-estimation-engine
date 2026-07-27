# Cost Estimation Engine - Short Technical Brief

Condensed version of `cost-engine-whitepaper.md`, for AI/programmatic
integrators. Python + pandas; the engine is pure and usable without the
Streamlit UI.

## What it does

Re-estimates an existing project cost estimate for a user-chosen
`(Location, Period)`. Inputs: the project's original line items from **ADR**
(latest snapshot per project, auto-selected) and market factors from **EMMA**
(**MFC** = material factors per commodity code; **LRC** = labor factor + USD
rate per location/period). Output: updated per-line values, category and total
original-vs-updated comparisons, warnings, and two CSVs. Deterministic,
read-only, no forecasting, no quantity math (originals are quantity-inclusive
line totals), no currency conversion.

## Calculation contract (`src/estimation_engine.py::estimate_lines`)

Labor - one LRC lookup `(location, period) -> (F, USD_R)` applies to ALL three
labor categories (Specialty Subcontractor, Field Shop Fab, Field Labor):

```
H_NEW    = H_ORIG * F
COST_NEW = H_NEW * USD_R
```

Material - per-code MFC map `(code, location, period) -> factor`, applied to
`BASE_MATERIAL_COST_ORIG` and `VENDOR_SHOP_FAB_COST_ORIG` independently:

```
COST_NEW = COST_ORIG * factor[line's MFC code]
```

Totals: `TOTAL_HOURS_NEW` = sum of the 3 hour categories; `TOTAL_COST_NEW` =
sum of the 5 cost categories (spec, vsf, bm, fsf, fl).

Two distinct "no MFC" cases (never conflate):

- **No code on the line** (NULL/blank): calculation not executed, updated cost
  **0**, flag `*_CODE_MISSING`.
- **Code present, no EMMA factor** for the selection: factor **1.0** (cost
  unchanged), flag `*_FACTOR_MISSING`. Use the flag to tell a defaulted 1.0
  from a real 1.0.

Both add warnings to the result. Missing LRC raises `LookupError` (guard only;
select from `labor_selections()` to avoid it).

## Data

- **ADR** (Snowflake, ~800k rows): item record (`ROW_ID` key, `PLANVIEW_ID`
  project, `SNAPSHOT` gate label ranked SCREEN < GATE1 < ... ), cost results
  (8 original hour/cost columns WITHOUT the `DB_` prefix = engine inputs; the
  `DB_*` twins are display-only reference), qty (display only). Reads are
  projected + filtered server-side.
- **EMMA**: `EMMA_SOURCE` = mock/excel/snowflake. Excel quirk: workbooks are
  routed by COLUMNS, not filename (real exports had contents crossed).
- Canonical column names live ONLY in `config/schema.py`.
- Original context is time-only: period from `COST_UPDATE` (mode of non-blank
  values); the original location is not recorded. `COST_BASIS` is a per-line
  scenario label, not the period.

## API quickstart

```python
from src.adr_repository import list_projects, load_project_lines
from src.emma_reference import load_mfc, load_lrc, labor_selections
from src.estimation_engine import run_estimation
from src.diagnostics import mfc_coverage
from src.csv_export import build_lines_csv, build_summary_csv

project = list_projects()[0]
lines = load_project_lines(project.project_id)      # latest snapshot
mfc, lrc = load_mfc(), load_lrc()
selection = labor_selections(lrc)[0]                # any LRC (location, period)
cov = mfc_coverage(lines, mfc, selection)           # optional pre-flight
result = run_estimation(project, lines, mfc, lrc, selection)
# result.total_cost.original/.updated/.delta/.pct_change, result.cost_categories,
# result.hour_categories, result.warnings, result.original_period, result.lines
csv1, csv2 = build_lines_csv(result), build_summary_csv(result)
```

## Gotchas

1. Updated material cost 0 + `*_CODE_MISSING=True` means "not executed by
   business rule", not "free".
2. `pct_change` is NaN when the original is 0.
3. Snapshot/gate choice is automatic (latest only).
4. Doc-vs-data inversions are a pattern here: EMMA filenames, COST_UPDATE vs
   COST_BASIS, un-prefixed vs `DB_*` inputs. The code follows the data.
5. Mock mode (`DATA_SOURCE=mock`, the default) is fully deterministic; tests
   always run against it.
