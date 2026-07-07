-- Demonstration queries for the open business questions (run in Snowflake).
--
-- Set your database/schema in the session context, e.g.:
--     USE DATABASE <your_db>; USE SCHEMA <your_schema>;
-- or qualify each table as <your_db>.<your_schema>.<table>.
--
-- TRY_TO_DOUBLE is used on the DB_*_COST columns because some databook costs
-- arrive as strings ("0", "9.47"); it returns NULL for non-numeric values.
--
-- NOTE (business Q11, 2026-07-07): the engine's REAL original costs are the
-- columns WITHOUT the DB_ prefix (SPEC_S_C_COST, ...); DB_* are databook
-- reference values. The Q6 queries below keep DB_* on purpose - they reproduce
-- the historical duplicate counts (5064 / 4627) computed with those columns.

-- =====================================================================
-- Q6  Multiple EXECUTION_SPLITs per project (double-counting check)
--     Example project: PLANVIEW 1101168, latest gate GATE2.
-- =====================================================================

-- A) The distinct splits and how many items each has.
SELECT EXECUTION_SPLIT, COUNT(*) AS items
FROM ADR_DIM_ESTIMATEITEMRECORD
WHERE PLANVIEW_ID = 1101168
  AND SNAPSHOT = 'GATE2'
GROUP BY EXECUTION_SPLIT
ORDER BY items DESC;

-- B) The same item (WBS + name + cost) appearing in more than one split:
--    the proof of double-counting. Joins each item to its databook cost, then
--    keeps identities whose identical cost shows up in >1 split. $0 demo items
--    are excluded (they do not inflate the total).
WITH item_cost AS (
    SELECT
        i.EXECUTION_SPLIT,
        i.COMPLETE_WBC,
        i.ITEM_NAME,
        ROUND(
            COALESCE(TRY_TO_DOUBLE(c.DB_SPEC_S_C_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_FIELD_SHOP_FAB_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_FIELD_LABOR_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_BASE_MATERIAL_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_VENDOR_SHOP_FAB_COST), 0)
        , 2) AS total_cost
    FROM ADR_DIM_ESTIMATEITEMRECORD i
    JOIN ADR_FACT_ESTIMATECOSTRESULTS c ON c.ROW_ID = i.ROW_ID
    WHERE i.PLANVIEW_ID = 1101168
      AND i.SNAPSHOT = 'GATE2'
)
SELECT
    COMPLETE_WBC,
    ITEM_NAME,
    total_cost,
    COUNT(DISTINCT EXECUTION_SPLIT)          AS splits,
    LISTAGG(DISTINCT EXECUTION_SPLIT, ' | ') AS split_names
FROM item_cost
GROUP BY COMPLETE_WBC, ITEM_NAME, total_cost
HAVING COUNT(DISTINCT EXECUTION_SPLIT) > 1
   AND total_cost > 0
ORDER BY total_cost DESC
LIMIT 50;

-- C) The aggregate counts (reproduces the diagnostic script's 5064 / 4627).
WITH item_cost AS (
    SELECT
        i.EXECUTION_SPLIT, i.COMPLETE_WBC, i.ITEM_NAME,
        ROUND(
            COALESCE(TRY_TO_DOUBLE(c.DB_SPEC_S_C_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_FIELD_SHOP_FAB_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_FIELD_LABOR_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_BASE_MATERIAL_COST), 0)
          + COALESCE(TRY_TO_DOUBLE(c.DB_VENDOR_SHOP_FAB_COST), 0)
        , 2) AS total_cost
    FROM ADR_DIM_ESTIMATEITEMRECORD i
    JOIN ADR_FACT_ESTIMATECOSTRESULTS c ON c.ROW_ID = i.ROW_ID
    WHERE i.PLANVIEW_ID = 1101168 AND i.SNAPSHOT = 'GATE2'
),
dup AS (   -- identities (WBS + name) present in more than one split
    SELECT COMPLETE_WBC, ITEM_NAME
    FROM item_cost
    GROUP BY COMPLETE_WBC, ITEM_NAME
    HAVING COUNT(DISTINCT EXECUTION_SPLIT) > 1
),
same_cost AS (   -- of those, identities whose cost recurs across >1 split
    SELECT COMPLETE_WBC, ITEM_NAME
    FROM item_cost
    GROUP BY COMPLETE_WBC, ITEM_NAME, total_cost
    HAVING COUNT(DISTINCT EXECUTION_SPLIT) > 1
)
SELECT
    (SELECT COUNT(*) FROM dup)                                        AS duplicated_identities,
    (SELECT COUNT(DISTINCT COMPLETE_WBC || ITEM_NAME) FROM same_cost) AS same_cost_identities;

-- =====================================================================
-- Q7  (Location, Period) pairs with labor (LRC) but no material (MFC).
--     Only works if EMMA lives in Snowflake as tables MFC and LRC
--     (adjust the table names to your environment). If EMMA comes from
--     the Excel workbooks, demonstrate with scripts/inspect_labor_only.py.
-- =====================================================================
SELECT DISTINCT
    l.LRC_LOCATION,
    l.LRC_LOCATIONCODE,
    l.LRC_COSTUPDATEREPORTINGPERIOD_NAME AS period
FROM LRC l
WHERE NOT EXISTS (
    SELECT 1 FROM MFC m
    WHERE m.MFC_LOCATIONCODE = l.LRC_LOCATIONCODE
      AND m.MFC_COSTUPDATEREPORTINGPERIOD_NAME = l.LRC_COSTUPDATEREPORTINGPERIOD_NAME
)
ORDER BY 1, 3;
