# Business Questions - Cost Estimation Engine

Open questions for the business team that requested the app. They come from
ambiguities in the spec and from the real ADR/EMMA data. Each item lists the
**current behavior** so the team can simply confirm or correct it.

Two versions below: a **Quick version** (one line each) and a **Detailed
version** (with context). Both are bilingual - English (🇬🇧) and Portuguese (🇧🇷).

Status: ⬜ open · ✅ confirmed · ✏️ changed - _update as answers come in._

---

## Quick version / Versão enxuta

**A. Calculation logic / Lógica de cálculo**

1. ✏️ **Field Labor** - 🇬🇧 NO. Spec gained a Field Labor Calculation: re-estimate with the LRC factor + USD rate, same as the other labor categories. · 🇧🇷 NAO. O spec ganhou uma seção de cálculo: reestimar com o fator LRC + taxa USD, igual às outras categorias de labor. **Done.**
2. ⬜ **Single LRC factor** - 🇬🇧 One LRC factor + USD rate for *both* labor categories - correct? · 🇧🇷 Um único fator LRC + taxa USD para as *duas* categorias de labor - correto?
3. ⬜ **Missing MFC factor** - 🇬🇧 Code with no MFC factor → keep cost unchanged + warn, or another rule? · 🇧🇷 Código sem fator MFC → manter custo inalterado + avisar, ou outra regra?
4. ⬜ **QUANTITY** - 🇬🇧 Are `DB_*` values already line totals, or should we multiply by QUANTITY? · 🇧🇷 Os valores `DB_*` já são totais por linha, ou devemos multiplicar por QUANTITY?

**B. Scope & data / Escopo e dados**

5. ⬜ **Latest snapshot** - 🇬🇧 "Latest" = most advanced gate (SCREEN<…<GATE5); should users pick the gate? · 🇧🇷 "Latest" = gate mais avançado (SCREEN<…<GATE5); o usuário deveria escolher o gate?
6. ⬜ **Multiple ADRs/splits** - 🇬🇧 Include all items at the gate, or pick a single ADR/split? · 🇧🇷 Incluir todos os itens do gate, ou escolher um único ADR/split?
7. ⬜ **Offered Location/Period** - 🇬🇧 Only show combos present in *both* MFC and LRC - acceptable? · 🇧🇷 Mostrar só combinações presentes no MFC *e* no LRC - aceitável?
8. ⬜ **EMMA file naming** - 🇬🇧 Confirm which file is material vs labor (exports came crossed). · 🇧🇷 Confirmar qual arquivo é material e qual é labor (exports vieram trocados).

**C. Output & reporting / Saída e relatório**

9. ⬜ **Time Period format** - 🇬🇧 Canonical granularity (year+semester?); compare multiple periods at once? · 🇧🇷 Granularidade canônica (ano+semestre?); comparar vários períodos de uma vez?
10. ⬜ **Rounding & currency** - 🇬🇧 Rounding/precision rules? USD only, or further conversion? · 🇧🇷 Regras de arredondamento/precisão? Só USD, ou conversão adicional?

---

## Detailed version / Versão detalhada

### A. Calculation logic / Lógica de cálculo

#### Q1 - Field Labor  ✏️ RESOLVED (2026-06-19)
**Resolution:** the business added a *Field Labor Calculation* to the spec. Field Labor is now re-estimated with the LRC multiplier `F` and USD rate, exactly like Specialty Subcontractor and Field Shop Fabrication: `FIELD_LABOR = DB_FL_H * F`, `FIELD_LABOR_COST = FIELD_LABOR * USD_R`. Implemented in `src/estimation_engine.py`; it now varies with Location/Period. (Doc typo noted: the Field Labor output table mislabels its rows as "Specialty Subcontractor"; the formulas are unambiguous.)

**Current behavior:** Field Labor is carried through unchanged (no factor applied) - it only appears in the totals; the spec gives it no re-estimation formula.

- 🇬🇧 The spec defines re-estimation factors for Specialty Subcontractor, Field Shop Fabrication, Base Material and Vendor Shop Fabrication, but **not** for Field Labor - so it stays equal to the databook value and never changes with Location/Period. Is that intended? If Field Labor *should* be adjusted, which factor applies (the LRC labor multiplier? the USD rate conversion? a separate factor)?
- 🇧🇷 O spec define fatores de reestimativa para Specialty Subcontractor, Field Shop Fabrication, Base Material e Vendor Shop Fabrication, mas **não** para Field Labor - então ele fica igual ao databook e nunca muda com Location/Period. Isso é intencional? Se Field Labor *deve* ser ajustado, qual fator se aplica (o multiplicador de labor do LRC? a conversão pela taxa USD? um fator separado)?

#### Q2 - Single LRC factor for both labor categories
**Current behavior:** the same LRC `FactorMultiplier` + `totalUSDRate` for the (Location, Period) is applied to **both** Specialty Subcontractor and Field Shop Fabrication (LRC has no labor-type code).

- 🇬🇧 LRC has one factor/USD rate per Location+Period with no labor-type breakdown. We apply that same pair to both Specialty Subcontractor and Field Shop Fabrication. Is a single labor factor for both categories correct, or should each labor category have its own?
- 🇧🇷 O LRC tem um fator/taxa USD por Location+Period, sem distinção por tipo de labor. Aplicamos o mesmo par às duas categorias (Specialty Subcontractor e Field Shop Fabrication). Um único fator de labor para ambas está correto, ou cada categoria deveria ter o seu?

#### Q3 - Material code with no MFC factor
**Current behavior:** if a line's material code has no MFC factor for the selected Location/Period, the cost is left unchanged (factor = 1.0) and a warning is shown; the line is never dropped.

- 🇬🇧 When a material code has no MFC match for the chosen Location/Period, we keep the original cost (factor 1.0) and flag it. Is "leave unchanged + warn" the right business behavior, or should we instead: block the run, use a default/fallback factor, exclude those lines, or route them to manual review?
- 🇧🇷 Quando um código de material não tem fator MFC para a Location/Period escolhida, mantemos o custo original (fator 1.0) e sinalizamos. "Manter inalterado + avisar" é o comportamento correto, ou deveríamos: bloquear a execução, usar um fator padrão, excluir essas linhas, ou enviá-las para revisão manual?

#### Q4 - QUANTITY usage / nature of databook costs
**Current behavior:** QUANTITY is loaded but not used in any formula - the re-estimation operates directly on the databook `DB_*` cost/hour values, treated as line totals.

- 🇬🇧 Our formulas apply factors directly to the databook costs/hours and don't use QUANTITY. Are the `DB_*` values already line totals (quantity-inclusive)? If they're per-unit, should the engine multiply by QUANTITY anywhere?
- 🇧🇷 Nossas fórmulas aplicam os fatores diretamente sobre os custos/horas do databook e não usam QUANTITY. Os valores `DB_*` já são totais por linha (já incluem a quantidade)? Se forem por unidade, o engine deveria multiplicar por QUANTITY em algum ponto?

### B. Scope & data / Escopo e dados

#### Q5 - Definition of "latest snapshot"
**Current behavior:** "latest snapshot" = the most advanced stage gate per project, ranked SCREEN < GATE1 < … < GATE5 (not by calendar date). Always auto-selected.

- 🇬🇧 We pick each project's most advanced gate as the "latest snapshot" (SCREEN < GATE1 < … < GATE5), not the most recent by date. Is that ordering correct? Should users be able to choose a specific snapshot/gate instead of always the latest?
- 🇧🇷 Pegamos o gate mais avançado de cada projeto como "latest snapshot" (SCREEN < GATE1 < … < GATE5), não o mais recente por data. Essa ordenação está correta? O usuário deveria poder escolher um snapshot/gate específico em vez de sempre o mais recente?

#### Q6 - Multiple ADRs/splits per project
**Current behavior:** a project (PLANVIEW_ID) at its latest gate may contain multiple ADR estimates/splits; we currently include all item rows at that snapshot.

- 🇬🇧 A PlanView project can have multiple ADR estimates/splits at the same gate. Today we include every item at the latest snapshot. Should we instead select a single ADR/split (e.g., the primary one), or is aggregating all items the intended behavior?
- 🇧🇷 Um projeto PlanView pode ter múltiplos ADRs/splits no mesmo gate. Hoje incluímos todos os itens do snapshot mais recente. Deveríamos selecionar um único ADR/split (ex.: o principal), ou agregar todos os itens é o comportamento desejado?

#### Q7 - Offered (Location, Period) pairs
**Current behavior:** the dropdowns only offer (Location, Period) pairs present in **both** MFC and LRC references (the intersection), guaranteeing a valid labor lookup.

- 🇬🇧 We only let users pick Location/Period combinations that exist in both MFC and LRC. A combo with labor (LRC) but only partial material (MFC) coverage is hidden entirely. Is that acceptable, or should such combos be selectable (with the missing-material warning)?
- 🇧🇷 Só deixamos o usuário escolher combinações de Location/Period presentes tanto no MFC quanto no LRC. Uma combinação com labor (LRC) mas cobertura parcial de material (MFC) fica totalmente oculta. Isso é aceitável, ou tais combinações deveriam ser selecionáveis (com o aviso de material faltante)?

#### Q8 - EMMA files with inverted names
**Current behavior:** the real `MFC.xlsx` / `LRC.xlsx` exports were observed with their contents swapped (the file named MFC held the labor columns). The loader routes each file by its columns, not its filename.

- 🇬🇧 The two EMMA exports came with contents crossed (the file named "MFC" contained labor columns and vice-versa). We currently classify each workbook by its columns to stay correct either way. Can you confirm the authoritative mapping (which file holds material vs labor), and will the eventual Snowflake tables follow the documented naming?
- 🇧🇷 Os dois exports do EMMA vieram com o conteúdo trocado (o arquivo chamado "MFC" continha colunas de labor e vice-versa). Hoje classificamos cada planilha pelas colunas para ficar correto de qualquer jeito. Vocês confirmam o mapeamento oficial (qual arquivo é material e qual é labor), e as futuras tabelas no Snowflake seguirão a nomenclatura documentada?

### C. Output & reporting / Saída e relatório

#### Q9 - Time Period format / granularity
**Current behavior:** period is treated as a label (e.g., year + semester like `2024-H1`); one period per run.

- 🇬🇧 What is the canonical Time Period format and granularity (year + semester? quarter? month)? Do users ever need to compare multiple periods side by side in one run, or is one period per estimation enough?
- 🇧🇷 Qual é o formato e a granularidade canônicos do Time Period (ano + semestre? trimestre? mês)? Os usuários precisam comparar vários períodos lado a lado numa mesma execução, ou um período por estimativa basta?

#### Q10 - Rounding, precision & currency
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
