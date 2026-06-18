# `data/` - local EMMA reference workbooks

Drop the EMMA factor workbooks here and run with `EMMA_SOURCE=excel` (see
`.env.example`). The `.xlsx` files themselves are gitignored - only this README
is tracked.

```
data/
  MFC.xlsx   # one EMMA workbook
  LRC.xlsx   # the other EMMA workbook
```

## How the files are read

The loader (`src/emma_excel.py`) routes each workbook by its **columns, not its
filename**, because the file naming has been observed crossed relative to the
spec. Each workbook is classified as:

- **Material** - has a per-commodity `code` column (+ `description`,
  `factorValue`). Used to scale Base Material and Vendor Shop Fabrication costs
  per ADR line code.
- **Labor** - has `factorMultiplier` + `totalUSDRate` and no `code`. Applied to
  both labor categories (Specialty Subcontractor, Field Shop Fabrication) to
  convert hours into cost.

Headers are matched case/space/underscore-insensitively and an optional
`MFC_` / `LRC_` prefix is stripped, so both the doc's prefixed headers and the
plain exported headers load cleanly. Rows with a blank/NaN factor (or blank USD
rate, for labor) are dropped on load.

ADR data is independent of this - it still comes from `DATA_SOURCE`
(Snowflake or mock).
