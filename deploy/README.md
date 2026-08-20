# Deploying the Cost Estimation Engine to Databricks Apps

The app runs as a Databricks App: the platform builds a container from this
repo (installing `requirements.txt`), runs the `command` from [`app.yaml`](../app.yaml),
and authenticates as the app's **service principal** (OAuth M2M - no browser
auth, no credentials in the repo). Data is read from Unity Catalog through a
SQL Warehouse attached to the app as a resource.

## Prerequisite: the migrated tables

The app expects the ADR tables in Unity Catalog, with the SAME names as the
Snowflake originals:

```
entai_sandbox_catalog.data_quality_scorecards.ADR_DIM_ESTIMATEITEMRECORD
entai_sandbox_catalog.data_quality_scorecards.ADR_FACT_ESTIMATECOSTRESULTS
entai_sandbox_catalog.data_quality_scorecards.ADR_FACT_ESTIMATEQTYRESULTS
entai_sandbox_catalog.data_quality_scorecards.ADR_DIM_ESTIMATEDESIGNDETAILS   (not read today, EAV)
```

Catalog/schema are configurable (`DATABRICKS_CATALOG` / `DATABRICKS_SCHEMA`,
in `app.yaml` or `.env`); the values above are the in-code defaults.

EMMA factors (`EMMA_SOURCE` in `app.yaml`):

- `databricks` (default in `app.yaml`): expects `MFC` and `LRC` tables in the
  same namespace (case-insensitive - `mfc`/`lrc` work). Load them once from
  the two EMMA Excel exports as-is (e.g. via the Databricks UI "Create table"
  upload or a small notebook): the loader normalizes the headers (Excel-style
  `code`/`factorMultiplier` or prefixed `MFC_*`/`LRC_*`) and classifies each
  table by its COLUMNS, not its name - so the known doc-vs-data content
  inversion between the two files (business Q8) is handled automatically,
  exactly like the Excel path.
- `excel`: reads `data/*.xlsx` from the deployed source instead. Caveat:
  `data/*.xlsx` is **gitignored**, so a plain repo/sync deploy will not carry
  the workbooks - you would need to add them to the synced source explicitly.

## Deploy steps

1. **Create the app** (Compute -> Apps -> Create, or
   `databricks apps create cost-estimation-engine`). Creating it provisions
   the app's service principal.
2. **Attach the SQL Warehouse** as an app resource, permission *Can use*,
   resource key exactly `sql-warehouse` (a different key breaks the
   `DATABRICKS_WAREHOUSE_ID` mapping in `app.yaml`).
3. **Grant Unity Catalog access**: run
   [`databricks/01_grants.sql`](databricks/01_grants.sql) on any warehouse,
   replacing `<APP_SERVICE_PRINCIPAL>` with the id shown on the app page.
4. **Deploy the code** - either the dev loop

   ```bash
   databricks sync --watch . /Workspace/Users/<you>/cost-estimation-engine
   databricks apps deploy cost-estimation-engine \
     --source-code-path /Workspace/Users/<you>/cost-estimation-engine
   ```

   or connect the repo in the workspace UI and press Deploy. The platform
   installs `requirements.txt` and runs the `command` from `app.yaml`.
5. **Share**: app page -> Permissions -> *Can use* for the user groups.

## Environment matrix

| Context | Identity | Warehouse | Config |
|---|---|---|---|
| Databricks Apps | app service principal (injected `DATABRICKS_CLIENT_ID/SECRET`) | `sql-warehouse` app resource -> `DATABRICKS_WAREHOUSE_ID` | `app.yaml` |
| Local vs real data | `DATABRICKS_HOST` + `DATABRICKS_TOKEN` (PAT) or `~/.databrickscfg` | `DATABRICKS_WAREHOUSE_ID` or `DATABRICKS_SQL_HTTP_PATH` | `.env` |
| Local demo | none | none | `DATA_SOURCE=mock` (default) |

## Manual steps the repo cannot do

- Migrate/refresh the ADR tables into Unity Catalog (owned by the data
  pipeline).
- Load the `MFC` / `LRC` tables from the EMMA Excel exports (or switch
  `EMMA_SOURCE` while they don't exist).
- Create the app + attach the `sql-warehouse` resource.
- Run `databricks/01_grants.sql` with the real service principal id.
- Grant *Can use* on the app to end users.
