-- =============================================================================
-- Unity Catalog grants for the Cost Estimation Engine app (Databricks Apps)
-- =============================================================================
-- Run once per environment, as a metastore/catalog admin, AFTER the app has
-- been created (creating the app provisions its service principal).
--
-- Replace <APP_SERVICE_PRINCIPAL> with the app's service principal
-- application-id (shown on the app page under "App resources" / identity;
-- backticks required around it).
--
-- Least privilege: the app is READ-ONLY - it needs SELECT on the 4 ADR tables
-- (+ the MFC/LRC reference tables once they land) and nothing else. The SQL
-- Warehouse the app uses is attached as an app *resource* with CAN_USE
-- permission - that grant lives in the app configuration, not here.

-- Make the namespace reachable.
GRANT USE CATALOG ON CATALOG entai_sandbox_catalog TO `<APP_SERVICE_PRINCIPAL>`;
GRANT USE SCHEMA  ON SCHEMA  entai_sandbox_catalog.data_quality_scorecards TO `<APP_SERVICE_PRINCIPAL>`;

-- Read every application table (ADR + EMMA reference). A schema-level SELECT
-- keeps this future-proof as reference tables land; tighten to per-table
-- grants (ADR_DIM_ESTIMATEITEMRECORD, ADR_DIM_ESTIMATEDESIGNDETAILS,
-- ADR_FACT_ESTIMATECOSTRESULTS, ADR_FACT_ESTIMATEQTYRESULTS, MFC, LRC) if the
-- schema also hosts tables the app must not see.
GRANT SELECT ON SCHEMA entai_sandbox_catalog.data_quality_scorecards TO `<APP_SERVICE_PRINCIPAL>`;
