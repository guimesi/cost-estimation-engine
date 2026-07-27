# Cost Estimation Engine - Technical White Paper

Audience: an AI model (or any programmatic integrator) that needs to understand
and leverage this engine. This document explains what the engine does, what
data it consumes, the exact calculation contract, its edge-case semantics, and
the programmatic entry points to call it without the UI.

Repo: `cost-estimation-engine` (Python, pandas, Streamlit front end, Snowflake
back end). The engine itself is pure Python + pandas and fully usable without
Streamlit.

---

## 1. What it does

The engine **re-estimates an existing project cost estimate for a different
location and time period**.

Input: a project's original estimate line items (from **ADR**, the estimating
system of record) plus market adjustment factors (from **EMMA**: **MFC** for
materials, **LRC** for labor). The user (or caller) picks a target
`(Location, Period)`; the engine multiplies each line's original hours/costs by
the applicable factors and produces an updated estimate, an
original-vs-updated comparison (per category and total), per-line diagnostics,
warnings, and two CSV exports.

It answers: *"This project was estimated at 2Q2019 prices. What would it cost
in, say, US Gulf Coast at 1Q2026 rates?"*

The engine does NOT create estimates from scratch, does not forecast, and does
not modify any source data. It is a deterministic, read-only, factor-based
re-pricing of an existing estimate.

---

## 2. Domain concepts and vocabulary

| Term | Meaning |
|---|---|
| **ADR** | Source system holding project estimates as line items ("estimation items"), snapshotted at stage gates. |
| **Snapshot / Gate** | A version of a project's estimate. Labels: `SCREEN < GATE1 < GATE2 < GATE3 < ...` (later gate = more recent). The engine always uses the **latest** snapshot per project. |
| **EMMA** | Reference source for market factors. Two datasets: MFC and LRC. |
| **MFC** (Material Factor Code) | Per-commodity material factors. Keyed by `(material code, location, period)` -> factor value. Each ADR line carries up to two material codes (base material, vendor shop fab) that are matched against this. |
| **LRC** (Labor Rate Code) | Labor factors. Keyed by `(location, period)` -> `(factor multiplier F, total USD rate USD_R)`. There is NO labor-type code: one pair applies to all labor categories. |
| **Location + Period** | The target pricing context the caller selects, e.g. ("USGC", "1Q2026"). |
| **Original period** | The pricing period of the ORIGINAL estimate, read from ADR's `COST_UPDATE` column (e.g. "2Q2019"). The original *location* is not recorded in ADR, so the original context is time-only. |
| **Execution split** | Scope partition labels on lines (e.g. ISBL/OSBL). Callers may filter lines by split before estimating; the engine itself is split-agnostic. |

### The five cost categories and three hour categories

Costs (order matters for display, defined in `config/schema.py::COST_CATEGORIES`):

1. Specialty Subcontractor (`spec`) - labor
2. Vendor Shop Fabrication (`vsf`) - material
3. Base Material (`bm`) - material
4. Field Shop Fabrication (`fsf`) - labor
5. Field Labor (`fl`) - labor

Hours (`HOUR_CATEGORIES`): Specialty Subcontractor, Field Shop Fabrication,
Field Labor. (Material categories have no hours.)

---

## 3. The calculation contract

Implemented in `src/estimation_engine.py::estimate_lines` - pure and
vectorized (no input mutation, no row loops). All inputs are the canonical
`*_ORIG` columns.

### 3.1 Labor

One LRC lookup per run: `(location_code, period) -> (F, USD_R)`. The same
factor `F` and rate `USD_R` apply to ALL THREE labor categories:

```
SPEC_H_NEW        = SPEC_H_ORIG        * F     SPEC_COST_NEW        = SPEC_H_NEW        * USD_R
FSF_H_NEW         = FSF_H_ORIG         * F     FSF_COST_NEW         = FSF_H_NEW         * USD_R
FIELD_LABOR_H_NEW = FIELD_LABOR_H_ORIG * F     FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R
```

Note the structure: new hours = original hours scaled by F; new cost = **new
hours** times the USD rate. The original labor *cost* columns are used only on
the "Original" side of comparisons, never in the new-cost formula.

If no LRC row exists for the selection, `estimate_lines` raises `LookupError`.
This is a guard, not a normal path: the UI only offers selections that exist
in LRC (`labor_selections()`).

### 3.2 Material

A per-code factor map is built once per run:
`mfc_factor_map(mfc, location_code, period) -> {code: factor}`. Each line
carries two material codes (`BASE_MATERIAL_MFC`, `VENDOR_SHOP_FAB_MFC`),
matched independently:

```
BASE_MATERIAL_COST_NEW   = BASE_MATERIAL_COST_ORIG   * factor[BASE_MATERIAL_MFC]
VENDOR_SHOP_FAB_COST_NEW = VENDOR_SHOP_FAB_COST_ORIG * factor[VENDOR_SHOP_FAB_MFC]
```

### 3.3 Two distinct "no MFC" cases - do NOT conflate them

This is the most important edge-case semantics in the engine:

| Case | Condition | Behavior | Per-line flag |
|---|---|---|---|
| **Code missing** | The line has NO MFC code (NULL/blank in ADR, normalized to `""`) | The material calculation is **not executed**: effective factor `0.0`, updated cost `0` | `BASE_MATERIAL_CODE_MISSING` / `VENDOR_SHOP_FAB_CODE_MISSING` |
| **Factor missing** | The line HAS a code, but EMMA has no factor for it at the selection | Factor defaults to `1.0` (cost carried unchanged), never dropped | `BASE_MATERIAL_FACTOR_MISSING` / `VENDOR_SHOP_FAB_FACTOR_MISSING` |

Both cases append a human-readable warning to the run's `warnings` list. The
flags exist so a defaulted `1.0` is distinguishable from a genuine factor that
happens to equal `1.0`. Blank-code detection is centralized in
`estimation_engine.blank_code_mask` (NULL, `""`, `"nan"`, `"none"`, `"null"`,
whitespace) and reused by the coverage diagnostic so preview and run can never
disagree.

### 3.4 Totals

Per line, then summed for comparisons:

```
TOTAL_HOURS_NEW = SPEC_H_NEW + FSF_H_NEW + FIELD_LABOR_H_NEW
TOTAL_COST_NEW  = SPEC_COST_NEW + VENDOR_SHOP_FAB_COST_NEW + BASE_MATERIAL_COST_NEW
                  + FSF_COST_NEW + FIELD_LABOR_COST_NEW
TOTAL_HOURS_ORIG / TOTAL_COST_ORIG = same sums over the *_ORIG columns
```

### 3.5 What the engine deliberately does NOT do

- **No quantity math.** Original values are quantity-inclusive line totals
  (business decision, 2026-06-19); factors apply directly to them. `QUANTITY`
  is carried for display only.
- **No `DB_*` inputs.** The ADR cost table carries two parallel column sets.
  The `DB_*` ("databook") columns are REFERENCE values, display-only. The real
  engine inputs are the columns WITHOUT the `DB_` prefix (business correction,
  2026-07-07). No formula reads a `DB_*` column. (The spec doc writes its
  formulas with `DB_*` names; the data proved otherwise.)
- **No currency conversion, no escalation curves, no interpolation.** If a
  factor is missing, the behavior is exactly the fallback described above.
- **No source mutation.** Reads only.

---

## 4. The data

### 4.1 ADR line items (the estimate being re-priced)

Four Snowflake tables (names in `config/schema.py`):

- `ADR_DIM_ESTIMATEITEMRECORD` - item identity: `ROW_ID` (item key),
  `PLANVIEW_ID` (project id), `FILE_NAME` (project display name), `SNAPSHOT`
  (gate label), WBS, description, `COST_BASIS`, `COST_UPDATE`,
  `EXECUTION_SPLIT`.
- `ADR_FACT_ESTIMATECOSTRESULTS` - the numbers, joined on `ROW_ID`: the eight
  original hours/costs (`SPEC_S_C`, `SPEC_S_C_COST`, `FIELD_SHOP_FAB`,
  `FIELD_SHOP_FAB_COST`, `FIELD_LABOR`, `FIELD_LABOR_COST`,
  `BASE_MATERIAL_COST`, `VENDOR_SHOP_FAB_COST`), their eight `DB_*` databook
  twins, and the two MFC codes (`BASE_MATERIAL_MFC`, `VENDOR_SHOP_FAB_MFC`).
- `ADR_FACT_ESTIMATEQTYRESULTS` - `QUANTITY` per `ROW_ID` (display only).
- `ADR_DIM_ESTIMATEDESIGNDETAILS` - an EAV table (one row per design
  parameter). Carries nothing the engine needs; intentionally NOT joined.

Scale: the live base is roughly 800k rows across dozens of columns, so the
repository (`src/adr_repository.py`) pushes work to Snowflake: project listing
is a server-side `GROUP BY PLANVIEW_ID, SNAPSHOT` aggregation; line loading
reads only one project's latest-snapshot rows, projected to the needed columns
and filtered server-side (cost/qty tables have no project key, so they are
filtered via a `ROW_ID IN (subquery)` on the item table).

Data-quality handling on ingest: numerics may arrive as strings ("0", "9.47")
and are coerced (`errors="coerce"`, NaN -> 0.0); NULL-ish MFC codes are
normalized to `""`; NULL execution splits become the visible bucket
`"(not set)"`.

"Latest snapshot" = highest-ranked gate per project via `SNAPSHOT_PRIORITY`
(`SCREEN=0 ... GATE5=5`); unknown labels fall back to numeric parsing (mock
uses integers), then to lowest rank. There is no per-gate user choice.

### 4.2 EMMA reference (the factors)

Canonical frames after ingestion (`config/schema.py` rename maps):

- **MFC** (material): `MFC_CODE`, `MFC_LOCATION`, `MFC_LOCATION_CODE`,
  `MFC_DESCRIPTION`, `MFC_FACTOR_VALUE`, `MFC_PERIOD`.
- **LRC** (labor): `LRC_LOCATION`, `LRC_LOCATION_CODE`,
  `LRC_FACTOR_MULTIPLIER`, `LRC_PERIOD`, `LRC_TOTAL_USD_RATE`.

EMMA has its own source switch (`EMMA_SOURCE`): `mock`, `excel`, or
`snowflake`. In `excel` mode two workbooks are dropped in `EMMA_DIR` (default
`data/`). Important quirk: the real Excel exports were observed with contents
CROSSED versus their filenames (the file named `MFC.xlsx` held labor columns
and vice versa), so `src/emma_excel.py` routes each workbook **by its columns,
not its filename**: a sheet with a `code` column is the Material/MFC frame; a
sheet with `factorMultiplier` + `totalUSDRate` and no code column is the
Labor/LRC frame. Never trust the filenames.

### 4.3 Canonical schema - the single source of truth

`config/schema.py` defines every canonical column name, the ADR table names,
the raw-to-canonical rename maps, the snapshot priority, and the category
tuples. Nothing else in the codebase hardcodes a column string. If you extend
the engine, import constants from there.

Naming convention: `*_ORIG` = original ADR inputs; `DB_*` = databook
reference (display only); `*_NEW` = engine outputs.

### 4.4 Selection coverage semantics

Three selection sets in `src/emma_reference.py`:

- `labor_selections(lrc)` - every `(Location, Period)` with an LRC row. **This
  is what the UI offers.** Labor is always computable; material coverage may be
  partial and is flagged, not blocked (business Q7).
- `available_selections(mfc, lrc)` - the stricter LRC-and-MFC intersection
  (fully material-covered pairs). Kept for diagnostics.
- `labor_only_selections(mfc, lrc)` - LRC pairs with zero MFC rows.

Pre-flight coverage: `src/diagnostics.py::mfc_coverage(lines, mfc, selection)`
returns an `MfcCoverage` with distinct-code coverage, the original material
cost that would stay unchanged (factor-missing case), and the separate
no-code bucket (lines whose updated material cost will be 0). It mirrors the
engine's matching exactly, so the preview always agrees with the run.

---

## 5. Programmatic API (how to leverage the engine without the UI)

Everything below is plain Python + pandas; no Streamlit required.

```python
from src.adr_repository import list_projects, load_project_lines
from src.emma_reference import load_mfc, load_lrc, labor_selections
from src.estimation_engine import run_estimation, estimate_lines
from src.diagnostics import mfc_coverage
from src.models import FactorSelection
from src.csv_export import build_lines_csv, build_summary_csv

# 1. Discover projects (each ProjectRef = latest snapshot, item count,
#    original pricing period).
projects = list_projects()
project = projects[0]

# 2. Load its canonical line frame (latest snapshot only).
lines = load_project_lines(project.project_id)

# Optional: filter by execution split before estimating (the UI's step-2
# checkboxes do exactly this).
# lines = lines[lines["EXECUTION_SPLIT"].isin({"ISBL"})]

# 3. Load EMMA and pick a target context.
mfc, lrc = load_mfc(), load_lrc()
selection = labor_selections(lrc)[0]   # or FactorSelection("USGC", "US Gulf Coast", "1Q2026")

# 4. Optional pre-flight: how well does MFC cover this project's codes?
cov = mfc_coverage(lines, mfc, selection)   # cov.matched_pct, cov.no_code_lines, ...

# 5. Run.
result = run_estimation(project, lines, mfc, lrc, selection)

result.total_cost.original / .updated / .delta / .pct_change
result.cost_categories        # list[Comparison], one per category
result.hour_categories
result.warnings               # list[str] - missing-code / missing-factor notices
result.original_period        # e.g. "2Q2019" (mode of COST_UPDATE, "n/a" if absent)
result.lines                  # full per-line frame: inputs + factors + flags + outputs

# 6. Exports.
lines_csv = build_lines_csv(result)      # per-line detail file
summary_csv = build_summary_csv(result)  # category-level comparison
```

Lower-level: `estimate_lines(lines, mfc, lrc, selection)` returns
`(augmented_frame, warnings)` if you only want the frame.

### Key result objects (`src/models.py`)

- `ProjectRef(project_id, project_name, snapshot_id, n_items, original_period)`
  - `snapshot_id` is a gate string in Snowflake mode, an int in mock mode.
- `FactorSelection(location_code, location_name, period)` - frozen dataclass;
  the engine matches on `location_code` + `period`.
- `Comparison(key, label, original, updated)` with derived `delta` and
  `pct_change` (`pct_change` is NaN when the original is 0 - handle it).
- `EstimationResult` - project, selection, the per-line frame, category and
  total comparisons, warnings, and `original_period`.
- `MfcCoverage` - pre-flight coverage stats (see 4.4).

### Per-line output columns added by the engine

Applied factors: `LRC_FACTOR`, `LRC_USD_RATE`, `BASE_MATERIAL_FACTOR`,
`VENDOR_SHOP_FAB_FACTOR`. Flags: the four `*_CODE_MISSING` /
`*_FACTOR_MISSING` booleans. Outputs: the eight `*_NEW` hour/cost columns plus
`TOTAL_HOURS_ORIG/NEW` and `TOTAL_COST_ORIG/NEW`.

---

## 6. Configuration and data-source modes

Env-driven via `config/settings.py` (`SETTINGS`):

| Variable | Values | Effect |
|---|---|---|
| `DATA_SOURCE` | `mock` (default) / `snowflake` | Where ADR lines come from. |
| `EMMA_SOURCE` | `mock` / `excel` / `snowflake` (defaults to `DATA_SOURCE`) | Where MFC/LRC come from. Allows ADR-from-Snowflake + EMMA-from-Excel (the interim setup). |
| `EMMA_DIR` | path (default `data/`) | Where the two Excel workbooks live in `excel` mode. |
| Snowflake creds | account/user/etc. | Consumed by `src/snowflake_client.py`. |

Mock mode is fully deterministic: one master frame per import with fixed-seed
RNG, projected onto the 4 ADR tables, so joins always reconstruct the same
rows. Tests always run in mock mode (autouse fixture pins both sources).

The Streamlit UI adds an `st.cache_data` layer (`ui/_data.py`) over the same
functions; programmatic callers hit the repository directly and can add their
own caching.

---

## 7. Semantics, invariants, and gotchas for an integrating AI

1. **Determinism**: same inputs -> same outputs. No randomness in the engine.
2. **Purity**: `estimate_lines` copies its input; nothing mutates source data.
3. **Warnings are part of the result, not exceptions.** The only exception in
   the normal calculation path is `LookupError` for a missing LRC pair (avoid
   it by selecting from `labor_selections()`). Missing MFC coverage degrades
   gracefully per the two-case rule (section 3.3). `load_project_lines` raises
   `KeyError` for an unknown project.
4. **Interpret updated material cost 0 correctly.** A zero updated material
   cost with `*_CODE_MISSING=True` means "calculation not executed by business
   rule", not "the material is free". Check the flags before reasoning about
   per-line numbers.
5. **Factor 1.0 is ambiguous without the flag.** Use `*_FACTOR_MISSING` to
   tell a defaulted 1.0 from a real 1.0.
6. **Original context is time-only.** ADR does not record where the original
   estimate was priced, only when (`COST_UPDATE`, summarized as the mode of
   non-blank values). `COST_BASIS` looks like it should be the period but is a
   free-text per-line scenario label ("TA", "Fab Yard - China"); it is carried
   per line for reference only. (Verified against real data, 2026-07-03; the
   spec doc says otherwise.)
7. **Doc-vs-data inversions are a pattern in this domain.** Three confirmed
   cases: EMMA filenames crossed (route by columns), period in `COST_UPDATE`
   not `COST_BASIS`, and engine inputs being the un-prefixed columns not the
   `DB_*` ones the spec formulas name. When the spec and the data disagree,
   this codebase follows the data, with the decision logged in
   `docs/business-questions.md` and CLAUDE.md.
8. **Snapshot selection is automatic.** Callers cannot pick a gate; the latest
   per project is always used. If you need a historical gate you must extend
   the repository.
9. **`pct_change` is NaN when the original is 0** - guard before formatting.
10. **All money values are line totals in the estimate's currency basis; the
    LRC `TOTAL_USD_RATE` prices labor in USD.** No further currency handling
    exists.

---

## 8. Quality harness

- `DATA_SOURCE=mock pytest -q` - full suite, ~95% coverage (CI gate at 90%).
- `ruff check .` - lint, matches CI.
- `scripts/inspect_adr_schema.py`, `scripts/inspect_cost_basis.py`,
  `scripts/inspect_no_code_cost.py` - live-schema verification scripts used to
  reconcile the doc-vs-data questions above.
- Mock `DB_*` values are deliberately `*_ORIG * 0.9`, so any wiring mixup
  between the reference and input column sets breaks tests.

---

## 9. Glossary of file entry points

| Path | Role |
|---|---|
| `src/estimation_engine.py` | The calculation: `estimate_lines`, `run_estimation`, `blank_code_mask`. |
| `src/adr_repository.py` | `list_projects`, `load_project_lines` (mock + Snowflake paths). |
| `src/emma_reference.py` | `load_mfc`, `load_lrc`, selection sets, `lrc_lookup`, `mfc_factor_map`. |
| `src/emma_excel.py` | Excel EMMA loader (routes workbooks by columns). |
| `src/diagnostics.py` | `mfc_coverage` pre-flight. |
| `src/csv_export.py` | `build_lines_csv`, `build_summary_csv`. |
| `src/models.py` | `ProjectRef`, `FactorSelection`, `Comparison`, `MfcCoverage`, `EstimationResult`. |
| `config/schema.py` | Canonical column names, rename maps, category tuples, snapshot priority. |
| `config/settings.py` | Env-driven `SETTINGS`. |
| `app.py` + `ui/` | Streamlit workflow (welcome + 3 steps); a thin consumer of everything above. |
