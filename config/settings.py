"""
Global application settings loaded from environment variables.

Mirrors the env-driven ``Settings`` dataclass used by the Data Quality app
so both projects share one configuration shape (and the same ``.env``
conventions). Add Cost-Estimation-Engine-specific knobs here as the domain
spec lands.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    # Data source. Options: "mock" | "databricks".
    data_source: str = os.getenv("DATA_SOURCE", "mock").lower()

    # EMMA reference source (MFC/LRC). Independent of ``data_source`` so ADR can
    # come from Databricks while the EMMA factors are read from local Excel
    # files (the interim setup until MFC/LRC tables land in Unity Catalog).
    # Defaults to ``data_source`` when unset. Options: "mock" | "excel" |
    # "databricks".
    emma_source: str = os.getenv("EMMA_SOURCE", os.getenv("DATA_SOURCE", "mock")).lower()
    # Directory holding MFC.xlsx / LRC.xlsx when ``emma_source == "excel"``.
    emma_dir: str = os.getenv("EMMA_DIR", "data")

    # Databricks. The Unity Catalog namespace holding the migrated ADR (and,
    # once landed, MFC/LRC) tables - table names are identical to their
    # Snowflake originals. Identity (host + credentials) is NOT configured
    # here: it is resolved by ``databricks.sdk.core.Config``, which picks up
    # the app service principal (DATABRICKS_CLIENT_ID/SECRET) inside
    # Databricks Apps and DATABRICKS_HOST + DATABRICKS_TOKEN (or a
    # ~/.databrickscfg profile) locally. No browser-based auth anywhere -
    # the app must run headless.
    dbx_catalog: str = os.getenv("DATABRICKS_CATALOG", "entai_sandbox_catalog")
    dbx_schema: str = os.getenv("DATABRICKS_SCHEMA", "data_quality_scorecards")
    # SQL Warehouse: a full HTTP path wins; otherwise the path is derived from
    # the warehouse id (which Databricks Apps injects when a sql-warehouse
    # resource is attached to the app).
    dbx_http_path: str = os.getenv("DATABRICKS_SQL_HTTP_PATH", "")
    dbx_warehouse_id: str = os.getenv("DATABRICKS_WAREHOUSE_ID", "")

    @property
    def is_mock(self) -> bool:
        return self.data_source == "mock"

    @property
    def emma_is_mock(self) -> bool:
        return self.emma_source == "mock"

    @property
    def emma_is_excel(self) -> bool:
        return self.emma_source == "excel"


SETTINGS = Settings()
