# Commits - June 2026

Full descriptions of every commit in the **Cost Estimation Engine** project made in June 2026 (June 17-19, 32 commits). Author: Guilherme Oliveira.

Reverse chronological order (most recent first).

---

## 2026-06-19

### `b46e38c` - docs: add demo-queries.sql (Q6 split double-count + Q7 labor-only) for live Snowflake demo

(no body)

### `e2a7a19` - docs: record real-data findings for Q6 (split names/sample) and Q7 (5 labor-only combos)

Q6: 1101168's splits are named NA vs 'USGC Reconfig Studies' (base vs study scenario), with the same items at identical cost (true double-count) plus re-priced items. Q7: real EMMA data has 5 labor-only pairs (Philippines/Montana/Wyoming, 2024 quarters), so the SME question can name them. Note: periods are quarterly.

### `f727079` - diag: add sample_split_duplicates (Q6) + inspect_labor_only (Q7); Q10 currency=USD

Two read-only diagnostics to validate the email's open points against real data: sample_split_duplicates.py shows concrete duplicated items across splits for one project (default 1101168); inspect_labor_only.py reports whether any (Location, Period) has labor but no material in the real EMMA data. Q10 currency confirmed USD-only; only rounding rules remain.

### `9484c74` - docs(Q6): record cost-probe results; 1101168 has real double-counting

Cost probe confirms splits are additive in 4/5 multi-split projects (true duplicates 0/0/9/36 of tens of thousands of items), but 1101168 has ~4.6k items identical (WBS+name+cost) across its two splits = genuine double-counting. V1: keep aggregating; concrete question staged for business/SME on that outlier.

### `0e4480b` - diag(Q6): add cost probe to inspect_adr_splits

For duplicated WBS+name identities across splits, classify same-cost (same databook cost in >1 split -> likely true double-count) vs differing-cost (distinct items sharing a generic name), reusing _sf_load_project_lines for the coerced costs. Settles the 1101168 ambiguity before the business conversation.

### `ecab0ee` - docs(Q6): record split-diagnostic findings + V1 recommendation

EXECUTION_SPLIT and ADR_ID are 1:1 (same 5/56 projects). Item-level probe shows 4 of 5 multi-split projects are additive (aggregating correct); one (1101168) has ~5k repeated item identities (possible double-count). V1 recommendation: keep aggregating; flag the outlier for business/SME confirmation.

### `ccf1f42` - diag(Q6): enhance inspect_adr_splits (ADR_ID + item-level dup probe)

First run showed 9% of projects (5/56) have >1 EXECUTION_SPLIT at the latest gate, with heavy WBS overlap across splits. Enhance the script to also report ADR_ID and an item-level duplication probe (same WBS+name in >1 split) to tell true double-counting from additive partitions; auto-detect the WBS/name columns so it doesn't depend on COMPLETE_WBC/WBS spelling. Recorded findings in docs/business-questions.md.

### `105b7ea` - docs: mark Time Period (Q9) as parked/not-sent to business

(no body)

### `92abdb9` - docs: Q10 rounding/currency awaiting business; document current rounding

(no body)

### `206e623` - docs: mark Q8 confirmed (route EMMA files by content, not filename)

(no body)

### `70df1d3` - feat: surface labor-only (no-MFC) Location/Period combos in step 2 (business Q7)

Q7 V1 decision (option C): keep the MFC-and-LRC intersection selectable (don't let users run inaccurate estimates without material factors), but surface the LRC-only pairs (labor present, zero MFC) so the business has real examples for the SME follow-up. Add emma_reference.labor_only_selections(), a cached wrapper, and a step-2 expander listing them. Clarified that partial coverage was already selectable + flagged (Q3). Updated tests, CLAUDE.md, docs.

### `472a457` - docs: Q6 open (multiple ADRs/splits); add inspect_adr_splits diagnostic

Business needs more info on Q6, so keep current behavior (aggregate all items at the latest snapshot). Add scripts/inspect_adr_splits.py: counts distinct ADR/split ids per project at the latest gate and checks WBS overlap vs disjoint across splits, so the business can decide aggregate-all vs pick-one. Marked Q6 awaiting in docs/business-questions.md with the decision to relay.

### `71fbdb9` - docs: mark Q5 confirmed (auto-pick latest gate; Gate3>Gate2>Screen)

(no body)

### `1dd686a` - feat: show QUANTITY in results table + CSV (business Q4)

Business confirmed Q4: databook DB_* values are already quantity-inclusive line totals, so the engine keeps applying factors directly and never multiplies by QUANTITY. QUANTITY is for visualization only: add it to the step-3 line-level table (new fmt_qty helper) and to the line-level CSV. Calculation unchanged. Updated helpers, CSV, results UI, tests, CLAUDE.md (new assumption 5), and marked Q4 resolved in docs/business-questions.md.

### `7b90554` - feat: flag missing-MFC lines in the estimation output (business Q3)

Business confirmed Q3: keep the line and leave its material cost unchanged (factor 1.0) when a code has no MFC factor, and flag it. Add explicit per-line flags BASE_MATERIAL_FACTOR_MISSING / VENDOR_SHOP_FAB_FACTOR_MISSING (set in the engine before the 1.0 default), included in the line-level CSV and shown as a '⚠ MFC missing' marker in the step-3 table. This disambiguates a missing factor from a real factor of 1.0. The aggregate warning and step-2 coverage preview stay. The suggested data-quality rule is recorded as a separate follow-up. Updated engine, CSV, results UI, tests, CLAUDE.md assumption 4, and marked Q3 resolved in docs/business-questions.md.

### `7a3c858` - docs: mark Q2 confirmed (single LRC factor for all labor categories)

(no body)

### `30a45bc` - feat(engine): re-estimate Field Labor with LRC factor + USD rate (business Q1)

Business answered Q1: the spec gained a Field Labor Calculation, so Field Labor is no longer a pass-through. It now uses the same LRC multiplier F and USD rate as Specialty Subcontractor and Field Shop Fabrication:

```
FIELD_LABOR_H_NEW    = DB_FIELD_LABOR_H * F
FIELD_LABOR_COST_NEW = FIELD_LABOR_H_NEW * USD_R
```

It now varies with Location/Period. Updated engine, tests, CLAUDE.md assumptions log, and marked Q1 resolved in docs/business-questions.md.

---

## 2026-06-18

### `fa22d66` - docs: add business-questions.docx; drop em-dashes project-wide

Generate a business-facing .docx (English intro + detailed bilingual questions + answer space) via pandoc for the team to fill in. Remove all em/en dashes from docs and UI per project style rule (no travessao): business-questions.md, README.md, data/README.md, and the step 1 dropdown label now use hyphens.

### `91c2d2c` - docs: add bilingual business questions (quick + detailed)

Open questions for the business team covering calculation logic (Field Labor pass-through, single LRC factor, missing-MFC handling, QUANTITY), scope/data (latest snapshot, multiple ADRs, offered Location/Period, EMMA file naming), and output (period format, rounding/currency). Each item states current behavior; quick + detailed versions, EN + PT-BR.

### `fe6f592` - Merge ux-quality-improvements: welcome screen, EMMA coverage, Snowflake read pushdown, searchable project dropdown

(merge commit, no body)

### `6bfaf5d` - Restore explicit project search box above the dropdown

Guarantee the search-by-PlanView-ID-or-name mechanism instead of relying only on the selectbox type-ahead: a text input filters the project list (id OR name, case-insensitive) and the dropdown picks from the result. Add unit tests locking the filter behaviour.

### `6cfb137` - Settle step 1 on the searchable dropdown layout

Drop the layout switcher and the Table/Cards variants now that Dropdown is the chosen design. The select's built-in type-to-filter matches the "PlanView ID - name" label (search by either), so the separate search box is gone too; the picked project's details show in a card below.

### `ddeeca5` - Scale step 1 to many projects + push ADR reads down to Snowflake

Performance (Snowflake path only; mock unchanged):
- SnowflakeClient.fetch_table gains a `columns=` projection and a `qualified()` helper; fetch_query gains bound `params`.
- list_projects now runs a server-side GROUP BY PLANVIEW_ID, SNAPSHOT (one row per project x snapshot) instead of transferring every line item.
- load_project_lines reads only the chosen project's latest-snapshot rows, projected to the needed columns and filtered server-side (WHERE PLANVIEW_ID; cost/qty filtered via ROW_ID IN (subquery) on the item table). Removes the old "load the whole universe then filter in pandas" path.
- With the existing ui/_data cache, re-opening a project is instant.

UI (step 1):
- Shared search box (filter by PlanView ID or name) + 3 switchable layouts (Table with row-selection / Dropdown / paginated Cards) so it stays usable with hundreds/thousands of projects.

Tests + docs: _FakeClient now emulates the aggregation + filtered reads; test_app_flow selects via session state (layout-agnostic); CLAUDE.md updated. 51 tests pass.

### `f6105a6` - Add welcome screen, EMMA coverage preview, and UX/quality polish

UX:
- New "step 0" welcome/landing screen (ui/step_welcome.py) with a ▶ Start button; it's the initial step and sits outside the numbered STEPS, so the 1/2/3 stepper and headings are unchanged. Restart returns to the landing.
- Step 3 charts now colour the "Updated" bars by change direction (up=red, down=green) via utils.helpers; removed dead colour-parity code.
- Step 3 gains a filterable line-level detail table (item/WBS/description).
- "new" label for zero-baseline % changes instead of NaN/"n/a" (fmt_pct_change / delta_color_from).
- Spinner around the Estimate run.

Feature:
- Pre-flight MFC coverage preview in step 2 (src/diagnostics.mfc_coverage + models.MfcCoverage): how many material codes have a factor for the selection and how much material cost would be left unchanged, anticipating the engine warning before the run.

Quality:
- ui/_data.py: st.cache_data wrappers over the data layer (one read per distinct arg instead of one per interaction), keeping src/ UI-free.

Tests + docs: new test_diagnostics, expanded test_helpers/test_app_flow (welcome + restart-to-landing), CLAUDE.md working map updated. 51 tests pass.

### `7464787` - Fix CI: put project root on sys.path for direct pytest invocation

CI runs `pytest -q` directly (not `python -m pytest`), so the project root was not on sys.path and conftest failed with `ModuleNotFoundError: No module named 'config'`. Add `pythonpath = ["."]` to the pytest config so `config`, `src`, etc. resolve. This also lets the coverage.xml artifact be produced (clearing the "no files found" upload warning).

### `4f4e5d0` - Reconcile real ADR Snowflake schema into the canonical line frame

Step 1 was failing with KeyError: 'ITEM_ID' under DATA_SOURCE=snowflake because the ADR tables had no raw->canonical rename (unlike EMMA), and the real ITPlus schema diverges from the mock's modeling assumptions.

Add a Snowflake-specific builder (adr_repository._snowflake_lines) that:
- joins item record + cost results + qty on ROW_ID (-> ITEM_ID); the EAV ADR_DIM_ESTIMATEDESIGNDETAILS table is intentionally not joined,
- renames each table's real headers via new maps in config/schema.py,
- coerces databook numerics that arrive as strings ("0", "9.47").

Project identity = PLANVIEW_ID (name from FILE_NAME). "Latest snapshot" now ranks the SNAPSHOT stage-gate label by SNAPSHOT_PRIORITY (SCREEN < GATE1 < ... < GATE3) instead of a numeric max, so ProjectRef.snapshot_id is int|str. The mock path, engine, UI and CSV are unchanged.

- scripts/inspect_adr_schema.py: dump real ADR columns for reconciliation
- tests: Snowflake reconciliation + gate-priority snapshot selection
- CLAUDE.md: document the real-schema reconciliation + assumptions

---

## 2026-06-17

### `73dd145` - refactor: update inspect_adr_schema script to support execution from any directory via sys.path modification

(no body)

### `542e4ea` - feat: add script to inspect ADR Snowflake schema and sample column values

(no body)

### `5906eaf` - Add EMMA_SOURCE=excel: load MFC/LRC factors from local Excel workbooks

EMMA gains its own source knob (EMMA_SOURCE=mock|excel|snowflake, defaults to DATA_SOURCE) so ADR can come from Snowflake while the EMMA factors are read from local .xlsx files - the interim setup until the MFC/LRC tables land in Snowflake.

The new loader (src/emma_excel.py) routes each workbook to the material or labor frame by its COLUMN STRUCTURE, not its filename: a 'code' column -> Material/MFC, a factorMultiplier + totalUSDRate file -> Labor/LRC. This is correct even though the observed exports are named inverted relative to the spec. Headers are matched case/space/underscore-insensitively (optional MFC_/LRC_ prefix stripped); blank-factor rows are dropped.

- config/settings.py: emma_source / emma_dir + emma_is_mock/emma_is_excel
- src/emma_reference.py: excel branch in load_mfc/load_lrc
- data/ + README, .gitignore (.xlsx ignored), .env.example, requirements (openpyxl)
- tests/test_emma_excel.py + conftest pins emma_source=mock; CLAUDE.md docs

### `ff4a6d0` - Build Cost Estimation Engine domain on the shared foundation

ADR x EMMA re-estimation app: pick a project, choose Location + Time Period, apply EMMA factors (MFC material / LRC labor) to the latest ADR snapshot, and compare original vs updated cost & hours with CSV export.

- config/schema.py: canonical column names + ADR tables + category tuples
- src: models, deterministic mock (4 ADR tables + MFC/LRC), adr_repository (join + latest snapshot), emma_reference (lookups), estimation_engine (vectorized calc), csv_export
- ui: 3-step flow (project -> parameters -> results) + grouped-bar comparison
- 39 tests, ~95% coverage; ruff clean

Confirmed spec readings: Field Labor pass-through; one LRC factor per (location, period) applied to both labor categories.

### `5f4ab6b` - Scaffold Cost Estimation Engine from data-quality-app foundation

Bootstraps the shared base (Snowflake client, env-driven settings, mock/snowflake data-source switch, global theme, session/router plumbing, and the pytest + ruff + pre-commit + CI harness). Domain logic to follow once the Cost Estimation Engine spec is provided.
