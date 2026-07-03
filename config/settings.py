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
    # Data source
    data_source: str = os.getenv("DATA_SOURCE", "mock").lower()

    # EMMA reference source (MFC/LRC). Independent of ``data_source`` so ADR can
    # come from Snowflake while the EMMA factors are read from local Excel files
    # (the interim setup until MFC/LRC tables land in Snowflake). Defaults to
    # ``data_source`` when unset. Options: "mock" | "excel" | "snowflake".
    emma_source: str = os.getenv("EMMA_SOURCE", os.getenv("DATA_SOURCE", "mock")).lower()
    # Directory holding MFC.xlsx / LRC.xlsx when ``emma_source == "excel"``.
    emma_dir: str = os.getenv("EMMA_DIR", "data")

    # Snowflake. Connection details have NO real defaults - they must be
    # supplied via .env (see .env.example). Empty values mean "not configured";
    # snowflake_client only connects when DATA_SOURCE=snowflake, and it already
    # omits an empty warehouse. Do NOT hardcode a real account / warehouse /
    # database / schema here (it would ship an internal identifier in the repo).
    sf_account: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
    sf_user: str = os.getenv("SNOWFLAKE_USER", "")
    sf_authenticator: str = os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser")
    sf_warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "")
    sf_database: str = os.getenv("SNOWFLAKE_DATABASE", "")
    sf_schema: str = os.getenv("SNOWFLAKE_SCHEMA", "")
    sf_role: str = os.getenv("SNOWFLAKE_ROLE", "")

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
