# Business Questions - Cost Estimation Engine

Open questions for the business team that requested the app. They come from
ambiguities in the spec and from the real ADR/EMMA data. Each item lists the
**current behavior** so the team can simply confirm or correct it.

Two versions below: a **Quick version** (one line each) and a **Detailed
version** (with context). Both are bilingual - English (🇬🇧) and Portuguese (🇧🇷).

Status: ⬜ open · ⏸ parked (not sent) · ⏳ awaiting business · ✅ confirmed · ✏️ changed - _update as answers come in._

---

## Quick version / Versão enxuta

**A. Calculation logic / Lógica de cálculo**

1. ✏️ **Field Labor** - 🇬🇧 NO. Spec gained a Field Labor Calculation: re-estimate with the LRC factor + USD rate, same as the other labor categories. · 🇧🇷 NAO. O spec ganhou uma seção de cálculo: reestimar com o fator LRC + taxa USD, igual às outras categorias de labor. **Done.**
2. ✅ **Single LRC factor** - 🇬🇧 CONFIRMED. One LRC factor + USD rate per (location, period) applies to every labor calculation; no labor-type breakdown. · 🇧🇷 CONFIRMADO. Um fator LRC + taxa USD por (location, period) vale para todo cálculo de labor; sem distinção por tipo.
3. ✏️ **Missing MFC factor** - 🇬🇧 Keep unchanged (factor 1.0) + flag it; added a per-line missing-MFC flag (CSV + results). DQ rule = separate follow-up. · 🇧🇷 Manter inalterado (fator 1.0) + sinalizar; adicionado flag por linha (CSV + resultados). Regra de DQ = follow-up separado. **Done.**
4. ✏️ **QUANTITY** - 🇬🇧 `DB_*` are already quantity-inclusive totals (no extra multiply); QUANTITY is display-only, now shown in the step-3 table + CSV. · 🇧🇷 `DB_*` já são totais com quantidade (sem multiplicar de novo); QUANTITY é só visualização, agora na tabela do step 3 + CSV. **Done.**
11. ✏️ **DB_* vs un-prefixed cost columns** - 🇬🇧 The REAL original hours/costs are the columns WITHOUT the `DB_` prefix (`SPEC_S_C`, `SPEC_S_C_COST`, ...); `DB_*` are databook reference only, kept for display. Engine rewired. · 🇧🇷 As horas/custos originais REAIS são as colunas SEM o prefixo `DB_` (`SPEC_S_C`, `SPEC_S_C_COST`, ...); as `DB_*` são só referência do databook, mantidas para exibição. Engine reapontado. **Done.**
12. ✏️ **NULL MFC code -> updated cost 0** - 🇬🇧 When the line's `BASE_MATERIAL_MFC` / `VENDOR_SHOP_FAB_MFC` is NULL, the material calculation is not executed and the updated cost is 0. The EMMA-gap case (code present, factor missing) stays as Q3: keep at 1.0 + flag. · 🇧🇷 Quando o `BASE_MATERIAL_MFC` / `VENDOR_SHOP_FAB_MFC` da linha é NULL, o cálculo de material não roda e o custo atualizado é 0. O caso de lacuna na EMMA (código presente, fator faltando) segue como Q3: mantém 1.0 + flag. **Done.**

**B. Scope & data / Escopo e dados**

5. ✅ **Latest snapshot** - 🇬🇧 CONFIRMED. Auto-pick the latest; no user choice. Order: Gate3 (newest) > Gate2 > Screen (oldest). · 🇧🇷 CONFIRMADO. Auto-seleciona o mais recente; sem escolha do usuário. Ordem: Gate3 (mais novo) > Gate2 > Screen (mais antigo).
6. ✅ **Multiple ADRs/splits** - 🇬🇧 Keep current behavior: sum by Snapshot+PlanView, include splits entirely (don't use split as an aggregation splitter). Project 1101168 pinned for SME (Emanuel) review. · 🇧🇷 Manter: somar por Snapshot+PlanView, incluir splits inteiros (não usar split como separador). 1101168 com pin para revisão do SME (Emanuel).
7. ✏️ **Offered Location/Period** - 🇬🇧 CHANGED: business wants these selectable and flagged. Any LRC pair is now selectable; missing material is flagged with a "missing from reference" message. · 🇧🇷 MUDOU: business quer selecionável e sinalizado. Qualquer par LRC agora é selecionável; material faltante é sinalizado com mensagem de "faltando na referência".
8. ✅ **EMMA file naming** - 🇬🇧 CONFIRMED. Ignore filenames, route by content: labor has USD rates, material has codes. Exactly what the loader does. · 🇧🇷 CONFIRMADO. Ignorar nomes, rotear pelo conteúdo: labor tem USD rates, material tem códigos. Exatamente o que o loader faz.

**C. Output & reporting / Saída e relatório**

9. ⏸ **Time Period format** (NOT sent to business) - 🇬🇧 Canonical granularity (year+semester?); compare multiple periods at once? · 🇧🇷 Granularidade canônica (ano+semestre?); comparar vários períodos de uma vez?
10. ✏️ **Rounding & currency** - 🇬🇧 Costs = 2 decimals (mirror ADR), done. Currency USD only. Still under business review: ADR may include hours inside "total cost". · 🇧🇷 Custos = 2 casas (replicar ADR), feito. Moeda só USD. Ainda em revisão do business: ADR pode incluir horas dentro do "total cost".

---

## Detailed version / Versão detalhada

### A. Calculation logic / Lógica de cálculo

#### Q1 - Field Labor  ✏️ RESOLVED (2026-06-19)
**Resolution:** the business added a *Field Labor Calculation* to the spec. Field Labor is now re-estimated with the LRC multiplier `F` and USD rate, exactly like Specialty Subcontractor and Field Shop Fabrication: `FIELD_LABOR = DB_FL_H * F`, `FIELD_LABOR_COST = FIELD_LABOR * USD_R`. Implemented in `src/estimation_engine.py`; it now varies with Location/Period. (Doc typo noted: the Field Labor output table mislabels its rows as "Specialty Subcontractor"; the formulas are unambiguous.)

**Current behavior:** Field Labor is carried through unchanged (no factor applied) - it only appears in the totals; the spec gives it no re-estimation formula.

- 🇬🇧 The spec defines re-estimation factors for Specialty Subcontractor, Field Shop Fabrication, Base Material and Vendor Shop Fabrication, but **not** for Field Labor - so it stays equal to the databook value and never changes with Location/Period. Is that intended? If Field Labor *should* be adjusted, which factor applies (the LRC labor multiplier? the USD rate conversion? a separate factor)?
- 🇧🇷 O spec define fatores de reestimativa para Specialty Subcontractor, Field Shop Fabrication, Base Material e Vendor Shop Fabrication, mas **não** para Field Labor - então ele fica igual ao databook e nunca muda com Location/Period. Isso é intencional? Se Field Labor *deve* ser ajustado, qual fator se aplica (o multiplicador de labor do LRC? a conversão pela taxa USD? um fator separado)?

#### Q2 - Single LRC factor for both labor categories  ✅ CONFIRMED (2026-06-19)
**Resolution:** correct as-is. Labor calculations apply the LRC factor to the databook hours and multiply by the USD rate; the LRC match considers only location and period, applying equally to every labor category (Specialty Subcontractor, Field Shop Fabrication, and now Field Labor). No change needed.

**Current behavior:** the same LRC `FactorMultiplier` + `totalUSDRate` for the (Location, Period) is applied to **both** Specialty Subcontractor and Field Shop Fabrication (LRC has no labor-type code).

- 🇬🇧 LRC has one factor/USD rate per Location+Period with no labor-type breakdown. We apply that same pair to both Specialty Subcontractor and Field Shop Fabrication. Is a single labor factor for both categories correct, or should each labor category have its own?
- 🇧🇷 O LRC tem um fator/taxa USD por Location+Period, sem distinção por tipo de labor. Aplicamos o mesmo par às duas categorias (Specialty Subcontractor e Field Shop Fabrication). Um único fator de labor para ambas está correto, ou cada categoria deveria ter o seu?

#### Q3 - Material code with no MFC factor  ✏️ RESOLVED (2026-06-19)
**Resolution:** keep the line and leave its material cost unchanged (factor 1.0), and flag it. Confirmed, plus we now emit an explicit per-line flag (`BASE_MATERIAL_FACTOR_MISSING` / `VENDOR_SHOP_FAB_FACTOR_MISSING`) in the line-level CSV and a "⚠ MFC missing" marker in the step-3 line table, on top of the existing aggregate warning and step-2 coverage preview. The suggested data-quality rule (ensure every material has a valid MFC) is recorded as a separate follow-up (see Follow-ups), owned by the data pipeline rather than the estimation engine.

**Current behavior:** if a line's material code has no MFC factor for the selected Location/Period, the cost is left unchanged (factor = 1.0) and a warning is shown; the line is never dropped.

- 🇬🇧 When a material code has no MFC match for the chosen Location/Period, we keep the original cost (factor 1.0) and flag it. Is "leave unchanged + warn" the right business behavior, or should we instead: block the run, use a default/fallback factor, exclude those lines, or route them to manual review?
- 🇧🇷 Quando um código de material não tem fator MFC para a Location/Period escolhida, mantemos o custo original (fator 1.0) e sinalizamos. "Manter inalterado + avisar" é o comportamento correto, ou deveríamos: bloquear a execução, usar um fator padrão, excluir essas linhas, ou enviá-las para revisão manual?

#### Q4 - QUANTITY usage / nature of databook costs  ✏️ RESOLVED (2026-06-19)
**Resolution:** the databook estimates already account for material quantities, so the `DB_*` values are line totals; the engine just adjusts them by the factors and never multiplies by QUANTITY (calculation confirmed unchanged). QUANTITY is for visualization only: it is now shown in the step-3 line-level table and included in the line-level CSV.

**Current behavior:** QUANTITY is loaded but not used in any formula - the re-estimation operates directly on the databook `DB_*` cost/hour values, treated as line totals.

- 🇬🇧 Our formulas apply factors directly to the databook costs/hours and don't use QUANTITY. Are the `DB_*` values already line totals (quantity-inclusive)? If they're per-unit, should the engine multiply by QUANTITY anywhere?
- 🇧🇷 Nossas fórmulas aplicam os fatores diretamente sobre os custos/horas do databook e não usam QUANTITY. Os valores `DB_*` já são totais por linha (já incluem a quantidade)? Se forem por unidade, o engine deveria multiplicar por QUANTITY em algum ponto?

#### Q11 - DB_* vs un-prefixed cost columns  ✏️ RESOLVED (2026-07-07)
**Resolution:** the business corrected the engine's input columns: in `ADR_FACT_ESTIMATECOSTRESULTS`, the REAL original hours/costs are the columns **without** the `DB_` prefix (`SPEC_S_C`, `SPEC_S_C_COST`, `FIELD_SHOP_FAB`, `FIELD_SHOP_FAB_COST`, `FIELD_LABOR`, `FIELD_LABOR_COST`, `BASE_MATERIAL_COST`, `VENDOR_SHOP_FAB_COST`) - hours included. The `DB_*` twins are databook **reference** values: keep reading and showing them (line-level CSV + reference), but no formula uses them. Implemented: new canonical `*_ORIG` columns feed the engine and the "Original" side of every comparison; `DB_*` are carried as display-only reference. (Same doc-vs-data inversion family as the EMMA filenames and COST_BASIS/COST_UPDATE - the spec doc writes its formulas with `DB_*` names.)

**Previous behavior:** the engine (and the spec doc's formulas) used the `DB_*` columns as the original estimate - both as the "Original" side of the comparison and as the base values the factors multiply.

- 🇬🇧 Follow-up to confirm: are the un-prefixed values also quantity-inclusive line totals, like Q4 established for `DB_*`? The engine assumes yes (no multiply by QUANTITY anywhere). Also worth a doc fix: the spec's formulas are written with `DB_*` names.
- 🇧🇷 Follow-up a confirmar: os valores sem prefixo também são totais por linha com quantidade inclusa, como o Q4 estabeleceu para `DB_*`? O engine assume que sim (não multiplica por QUANTITY em lugar nenhum). Também vale corrigir a doc: as fórmulas do spec usam os nomes `DB_*`.

#### Q12 - NULL MFC code on the line -> updated material cost 0  ✏️ RESOLVED (2026-07-10)
**Resolution:** business fix to the material calculation: when the line's MFC code is NULL in ADR (`BASE_MATERIAL_MFC` for Base Material, `VENDOR_SHOP_FAB_MFC` for Vendor Shop Fab), the calculation is **not executed** and the expected updated cost is **0**. Confirmed scope: this applies ONLY to the NULL-code case; the Q3 case (code present, EMMA factor missing for the selection) keeps today's behavior - cost unchanged (factor 1.0) + flag. Implemented: factor 0 per blank-code line side, per-line `*_CODE_MISSING` flags (line-level CSV + "∅ no code (0)" in the step-3 table), an engine warning, and a step-2 info with the zeroed original material cost. NULL-ish codes are normalized to `""` at ingestion.

**Previous behavior:** a NULL code fell into the same bucket as a missing EMMA factor: cost kept unchanged (factor 1.0) + flagged.

**Data verification (2026-07-10, project 1084329 via `scripts/inspect_no_code_cost.py`):** across ALL snapshots of the project (129,337 cost rows), 28,715 have no `BASE_MATERIAL_MFC` and 101,724 no `VENDOR_SHOP_FAB_MFC` - and **every one of them carries zero original cost** in the corresponding column. (The app's step-3 warnings quote smaller counts because they cover only the latest snapshot's lines after the step-2 split filter; the script now scopes to the latest snapshot too.) So the rule changes no totals on this project (0 either way); it only becomes visible if a no-code line with cost ever appears. Also observed: the un-prefixed cost columns are typed `NUMBER(18,2)` in the live schema (the `DB_*` twins are strings).

- 🇬🇧 Follow-up (data quality): should lines without any MFC code exist in ADR at all? If they are data errors, the zeroing hides them from the total - worth a DQ rule alongside the Q3 one.
- 🇧🇷 Follow-up (qualidade de dados): linhas sem código MFC deveriam existir no ADR? Se forem erro de dado, o zeramento as esconde do total - vale uma regra de DQ junto com a do Q3.

### B. Scope & data / Escopo e dados

#### Q5 - Definition of "latest snapshot"  ✅ CONFIRMED (2026-06-19)
**Resolution:** auto-pick the latest is correct; no per-gate user choice needed. EMCAPS refines costs at each milestone, so the most recent estimate is an equal-or-refined version of the previous. Gate order (per the available data): Gate3 (most recent) > Gate2 > Screen (oldest), which matches the engine's `SNAPSHOT_PRIORITY`. (Our map also keeps GATE1/GATE4/GATE5 as a harmless, forward-compatible superset.)

**Current behavior:** "latest snapshot" = the most advanced stage gate per project, ranked SCREEN < GATE1 < … < GATE5 (not by calendar date). Always auto-selected.

- 🇬🇧 We pick each project's most advanced gate as the "latest snapshot" (SCREEN < GATE1 < … < GATE5), not the most recent by date. Is that ordering correct? Should users be able to choose a specific snapshot/gate instead of always the latest?
- 🇧🇷 Pegamos o gate mais avançado de cada projeto como "latest snapshot" (SCREEN < GATE1 < … < GATE5), não o mais recente por data. Essa ordenação está correta? O usuário deveria poder escolher um snapshot/gate específico em vez de sempre o mais recente?

#### Q6 - Multiple ADRs/splits per project  ✅ RESOLVED for v1 + ⏳ SME pin (2026-06-19)
**Resolution:** keep the current logic - sum costs by Snapshot + PlanView_ID and include execution splits ENTIRELY (do not use EXECUTION_SPLIT as an aggregation splitter). The business believes splits are scope partitions like ISBL/OSBL (Inside/Outside Battery Limits). Project 1101168 looks unique and possibly non-compliant (the base vs `USGC Reconfig Studies` scenario found below); it is pinned for review with an SME (Emanuel). No code change: the engine already aggregates all splits.

**Update (2026-07-03):** by business request, step 2 now shows the project's EXECUTION_SPLITs as checkboxes (default all on, with Select all) so the user chooses which splits enter the comparison. Default behavior is unchanged (all splits included); this also gives manual control over overlapping-split cases like 1101168 while the SME review is pending.

**Status:** business answered "need more information." Current behavior is unchanged (aggregate all items at the latest snapshot).

**Diagnostic (2026-06-19, real Snowflake, `scripts/inspect_adr_splits.py`):**
- 56 projects; 5 (9%) have >1 `EXECUTION_SPLIT` at the latest gate (51/3/1/1). `ADR_ID` has the IDENTICAL distribution, so EXECUTION_SPLIT and ADR_ID are effectively 1:1 here (one ADR per split) and affect the same 5 projects.
- Item-level duplication probe (same WBS+name in >1 split): 1096196 -> 0; 1084329 -> 1; 1084351 -> 15; 1089342 -> 94; 1101168 -> 5064. So 4 of 5 multi-split projects are effectively ADDITIVE (splits hold different items; high WBS-code overlap was benign), and aggregating is correct. One (1101168) shows ~5k repeated item identities -> possible double-counting there.

**V1 recommendation:** keep aggregating all items (current behavior). ~91% of projects have a single split, and most multi-split ones are additive, so aggregating is right for the vast majority; switching to pick-one would break the additive cases. Flag the duplication outlier for the business/SME.

**Decision to relay (with the numbers):** are EXECUTION_SPLIT/ADR_ID additive partitions of one project scope (keep aggregating) or can they overlap/duplicate the same scope (then we need a dedup or pick-one rule, e.g., for projects like 1101168)?

**Cost-probe results (2026-06-19):** per multi-split project, same-cost (true duplicate) / diff-cost counts: 1096196 -> 0 dup; 1084329 -> 0/1; 1084351 -> 9/6; 1089342 -> 36/58; 1101168 -> **4627/437**. So in 4 of 5 projects true duplication is negligible (0, 0, 9, 36 items) and aggregating is correct. One project (1101168) has ~4.6k items identical (same WBS+name+databook cost) across its two splits -> genuine double-counting at scale.

**V1 recommendation:** keep aggregating (correct for ~55/56 projects). Concrete question for the business/SME: project 1101168 has ~4,600 items identical (WBS+name+cost) across its two EXECUTION_SPLITs - is that a data error / superseded split (dedup or pick-one) or intentional (legitimately counted twice)? The answer decides the rule. Optional V1 safeguard (implement only after the semantic answer): detect + warn on projects with heavy same-cost duplication, without changing the calc.

**Sample (1101168, via `scripts/sample_split_duplicates.py`):** the two splits are named `NA` (19,977 items) and `USGC Reconfig Studies` (19,059 items) - i.e. they look like a base case vs a study scenario of the SAME scope, not two additive parts. Same-cost identities are the same item+cost in both splits (e.g. `0-215-8"-G3A-3 Demo TA` -> 5 items `[0.63,0.8,0.9,1.9,4.0]` in both); diff-cost identities are the same item re-priced by the study (e.g. `HCU-1-STRCT` -> NA 518.0 vs USGC 286.0). So summing both splits double-counts this project. (Caveat: many same-cost matches are $0 demo items that don't affect the total, but non-zero exact matches exist, so the cost double-count is real.)

**Current behavior:** a project (PLANVIEW_ID) at its latest gate may contain multiple ADR estimates/splits; we currently include all item rows at that snapshot.

- 🇬🇧 A PlanView project can have multiple ADR estimates/splits at the same gate. Today we include every item at the latest snapshot. Should we instead select a single ADR/split (e.g., the primary one), or is aggregating all items the intended behavior?
- 🇧🇷 Um projeto PlanView pode ter múltiplos ADRs/splits no mesmo gate. Hoje incluímos todos os itens do snapshot mais recente. Deveríamos selecionar um único ADR/split (ex.: o principal), ou agregar todos os itens é o comportamento desejado?

#### Q7 - Offered (Location, Period) pairs  ✏️ CHANGED (2026-06-19)
**Business decision:** for v1, flag these exact errors. When a selected Location/Period lacks material factors, allow the selection and show a message stating the missing reference value. This reverses the earlier "keep hidden" call: the app now offers **every LRC (Location, Period) pair** (`labor_selections()`), and the step-2 coverage panel flags any material codes missing from the MFC reference (count, dollar exposure, and the list of missing codes), noting that labor is still re-estimated. Implemented; the old `labor_only_selections()` "hidden combos" note was removed.

**Prior clarification (still true):** partial coverage was already selectable + flagged (Q3); this change additionally makes the fully labor-only pairs selectable.

**Real-data check (via `scripts/inspect_labor_only.py`):** the case is real. Of the EMMA pairs, 225 are in both MFC and LRC, **5 are labor-only** (LRC, no MFC) - Philippines (PH.BTN_P)/4Q2024, Montana (US.BIL_P)/2Q2024 and /4Q2024, Wyoming (US.LBB_P)/2Q2024 and /4Q2024 - and 64 are material-only (MFC, no LRC, also excluded). So the SME question can name these 5 specific combos. (Aside: periods are quarterly, e.g. `2Q2024`, not semesters - relevant if Q9 Time Period is revisited.)

**Current behavior:** the dropdowns only offer (Location, Period) pairs present in **both** MFC and LRC references (the intersection), guaranteeing a valid labor lookup.

- 🇬🇧 We only let users pick Location/Period combinations that exist in both MFC and LRC. A combo with labor (LRC) but only partial material (MFC) coverage is hidden entirely. Is that acceptable, or should such combos be selectable (with the missing-material warning)?
- 🇧🇷 Só deixamos o usuário escolher combinações de Location/Period presentes tanto no MFC quanto no LRC. Uma combinação com labor (LRC) mas cobertura parcial de material (MFC) fica totalmente oculta. Isso é aceitável, ou tais combinações deveriam ser selecionáveis (com o aviso de material faltante)?

#### Q8 - EMMA files with inverted names  ✅ CONFIRMED (2026-06-19)
**Resolution:** ignore the filenames and route by content. The rule from the business: labor factors contain USD rates; material factors contain codes. This is exactly what `src/emma_excel.py::_classify` already does (a `code` column -> material; `totalUSDRate`/`factorMultiplier` -> labor). No change needed.

**Current behavior:** the real `MFC.xlsx` / `LRC.xlsx` exports were observed with their contents swapped (the file named MFC held the labor columns). The loader routes each file by its columns, not its filename.

- 🇬🇧 The two EMMA exports came with contents crossed (the file named "MFC" contained labor columns and vice-versa). We currently classify each workbook by its columns to stay correct either way. Can you confirm the authoritative mapping (which file holds material vs labor), and will the eventual Snowflake tables follow the documented naming?
- 🇧🇷 Os dois exports do EMMA vieram com o conteúdo trocado (o arquivo chamado "MFC" continha colunas de labor e vice-versa). Hoje classificamos cada planilha pelas colunas para ficar correto de qualquer jeito. Vocês confirmam o mapeamento oficial (qual arquivo é material e qual é labor), e as futuras tabelas no Snowflake seguirão a nomenclatura documentada?

### C. Output & reporting / Saída e relatório

#### Q9 - Time Period format / granularity  ⏸ PARKED - not sent to business
**Status:** this question was intentionally left out of the round sent to the business (which is why their reply numbers Rounding as "Q9"). Kept here as a parked item in case it's sent later. No answer pending.

**Current behavior:** period is treated as a label (e.g., year + semester like `2024-H1`); one period per run.

- 🇬🇧 What is the canonical Time Period format and granularity (year + semester? quarter? month)? Do users ever need to compare multiple periods side by side in one run, or is one period per estimation enough?
- 🇧🇷 Qual é o formato e a granularidade canônicos do Time Period (ano + semestre? trimestre? mês)? Os usuários precisam comparar vários períodos lado a lado numa mesma execução, ou um período por estimativa basta?

#### Q10 - Rounding, precision & currency  ✏️ PARTIAL (2026-06-19)
**Resolution so far:** cost fields use 2 decimals, mirroring how ADR stores them in Snowflake (implemented: `fmt_money` now shows 2 decimals; the summary CSV already rounded to 2). Currency is USD only. **Still under business review:** ADR's "total cost" may include hours summed in with costs (a non-obvious case they are checking) - if confirmed, the total-cost composition (not just rounding) may need to change. That is tracked as a follow-up. (Note: the business referred to this as "Q9"; here it is Q10. Q9 = Time Period is parked / not sent.)

**Current rounding:** on-screen money shows 2 decimals (`$1,234.00`), hours whole (`12,340 h`), percentages 1 decimal; the **summary** CSV rounds to 2 decimals; the **line-level** CSV is unrounded (full precision). All amounts are USD (via the LRC `totalUSDRate`).

**Current behavior:** outputs in USD; the on-screen comparison rounds to whole values, the summary CSV rounds to 2 decimals.

- 🇬🇧 Are there rounding/precision rules for executive reporting and the CSV (decimals, currency formatting)? Is USD the only output currency, or is any further conversion expected beyond the LRC USD rate?
- 🇧🇷 Existem regras de arredondamento/precisão para o relatório executivo e o CSV (casas decimais, formatação de moeda)? USD é a única moeda de saída, ou espera-se alguma conversão adicional além da taxa USD do LRC?

---

## Notes on the spec document / Observações sobre o documento

Minor internal inconsistencies spotted in the briefing doc - they do **not**
affect the engine (the canonical schema handles them), but worth confirming:

- 🇬🇧 The *Field Shop Fabrication* input table mislabels its inputs (it lists `DB_BASE_MATERIAL_COST` / `BASE_MATERIAL_MFC`), but the formula and the engine correctly use `DB_FSF_H` with the **LRC** labor factor, not MFC.
- 🇧🇷 A tabela de input de *Field Shop Fabrication* rotula os inputs errado (lista `DB_BASE_MATERIAL_COST` / `BASE_MATERIAL_MFC`), mas a fórmula e o engine usam corretamente `DB_FSF_H` com o fator de labor do **LRC**, não MFC.
- 🇬🇧 In the totals table, Field Labor uses the label `FL_C` for both hours and cost; the engine separates `DB_FIELD_LABOR_H` and `DB_FIELD_LABOR_C`.
- 🇧🇷 Na tabela de totais, Field Labor usa o rótulo `FL_C` tanto para horas quanto para custo; o engine separa `DB_FIELD_LABOR_H` e `DB_FIELD_LABOR_C`.
- 🇬🇧 **Doc v2 (section 8) says the original estimation's time period comes from `COST_BASIS`, but the real data disagrees** (checked 2026-07-03 via `scripts/inspect_cost_basis.py`): `COST_UPDATE` holds the quarterly period ("2Q2019"), constant per project/gate, while `COST_BASIS` is a free-text pricing-basis/scenario label ("TA"/"NTA", "Fab Yard - China") that varies between items. The app uses `COST_UPDATE` for the period; worth relaying to Pedro for a doc fix.
- 🇧🇷 **A doc v2 (seção 8) diz que o período da estimativa original vem do `COST_BASIS`, mas os dados reais discordam** (verificado em 2026-07-03 via `scripts/inspect_cost_basis.py`): o `COST_UPDATE` guarda o período trimestral ("2Q2019"), constante por projeto/gate, enquanto o `COST_BASIS` é um rótulo livre de cenário/base de pricing ("TA"/"NTA", "Fab Yard - China") que varia entre itens. O app usa `COST_UPDATE` para o período; vale repassar ao Pedro para corrigir a doc.

---

## Follow-ups / Próximos passos

- ⬜ **Un-prefixed values quantity-inclusive?** (Q11). 🇬🇧 Q4 confirmed `DB_*` are quantity-inclusive line totals; confirm the same holds for the un-prefixed originals the engine now uses. · 🇧🇷 O Q4 confirmou que as `DB_*` são totais por linha com quantidade; confirmar se o mesmo vale para as colunas sem prefixo que o engine agora usa.
- ⏳ **ADR "total cost" composition** (Q10). 🇬🇧 Business is checking whether ADR sums hours into "total cost"; if so, the total-cost formula (not just rounding) may need to change. Costs-to-2-decimals is already done. · 🇧🇷 Business verificando se o ADR soma horas dentro do "total cost"; se sim, a fórmula do total (não só o arredondamento) pode mudar. Custos com 2 casas já feito.
- ⏳ **SME pin: project 1101168 splits** (Q6). 🇬🇧 Review with Emanuel whether 1101168's `NA` vs `USGC Reconfig Studies` splits (base vs scenario, ~4.6k duplicated items) are a data issue. v1 keeps aggregating all splits. · 🇧🇷 Revisar com o Emanuel se os splits `NA` vs `USGC Reconfig Studies` do 1101168 (base vs cenário, ~4,6k itens duplicados) são problema de dado. A v1 mantém a agregação de todos os splits.
- ⏳ **SME confirm: the 5 labor-only combos** (Q7). 🇬🇧 The app now lets these be selected and flags the missing material; confirm whether the missing MFC for Philippines/Montana/Wyoming 2024 quarters is expected or a reference gap to fill. · 🇧🇷 O app agora permite selecionar e sinaliza o material faltante; confirmar se a ausência de MFC para Philippines/Montana/Wyoming (trimestres 2024) é esperada ou uma lacuna a preencher.
- ⬜ **DQ rule: every material has a valid MFC** (from Q3). 🇬🇧 The estimation engine flags missing MFC factors per line, but a proactive data-quality rule that ensures every material code has a (valid) MFC for the relevant locations/periods belongs to the data pipeline (e.g., the sibling data-quality-app), not this engine. To be scoped separately. · 🇧🇷 O motor de estimativa sinaliza fatores MFC faltantes por linha, mas uma regra de DQ proativa que garanta que todo código de material tenha um MFC (válido) para as localidades/períodos pertence ao pipeline de dados (ex.: o data-quality-app), não a este motor. A ser escopado separadamente.
