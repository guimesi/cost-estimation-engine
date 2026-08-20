"""Load EMMA reference frames (MFC / LRC) from local Excel files.

Interim source until the MFC/LRC tables land in Unity Catalog: drop the two EMMA
workbooks in ``SETTINGS.emma_dir`` (default ``data/``) and run with
``EMMA_SOURCE=excel``. ADR can still come from Databricks at the same time.

**Routing is by column structure, not by filename.** The business doc and the
real-world exports disagree on which workbook is named ``MFC.xlsx`` vs
``LRC.xlsx`` (the physical files were observed with their columns crossed), so
relying on the filename is unsafe. Instead each workbook is classified by what
it contains:

- a per-commodity factor (a ``code`` column) -> the **Material** frame (MFC),
  matched per ADR line code;
- a labor multiplier plus a USD rate (``totalUSDRate``, no code) -> the
  **Labor** frame (LRC), applied to both labor categories.

This matches the engine math (material scales an existing cost per code; labor
converts hours via ``multiplier x USD rate``) regardless of how the files are
named. Headers are normalized (case/space/underscore-insensitive, optional
``MFC_``/``LRC_`` prefix stripped) so either naming convention loads cleanly.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from config.schema import (
    LRC_FACTOR_MULTIPLIER,
    LRC_LOCATION,
    LRC_LOCATION_CODE,
    LRC_PERIOD,
    LRC_TOTAL_USD_RATE,
    MFC_CODE,
    MFC_DESCRIPTION,
    MFC_FACTOR_VALUE,
    MFC_LOCATION,
    MFC_LOCATION_CODE,
    MFC_PERIOD,
)
from config.settings import SETTINGS


def _norm(col: str) -> str:
    """Normalize a header: lowercase, strip non-alphanumerics and MFC/LRC prefix."""
    s = re.sub(r"[^a-z0-9]", "", str(col).lower())
    for prefix in ("mfc", "lrc"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s


def _pick(norms: Dict[str, str], *candidates: str) -> str:
    """Return the original column name for the first matching normalized key."""
    for cand in candidates:
        if cand in norms:
            return norms[cand]
    raise ValueError(
        f"EMMA workbook is missing an expected column (looked for {candidates!r}); "
        f"available columns: {sorted(norms.values())}"
    )


def _classify(df: pd.DataFrame) -> str:
    """Return 'material' or 'labor' based on the workbook's column structure."""
    norms = {_norm(c): c for c in df.columns}
    if "code" in norms:
        return "material"
    if "totalusdrate" in norms or "factormultiplier" in norms:
        return "labor"
    raise ValueError(
        "Cannot classify EMMA workbook as material or labor; expected either a "
        f"'code' column (material) or 'totalUSDRate'/'factorMultiplier' (labor). "
        f"Columns: {sorted(df.columns)}"
    )


def _to_material(df: pd.DataFrame) -> pd.DataFrame:
    """Map a material workbook onto canonical MFC_* columns; drop NaN factors."""
    norms = {_norm(c): c for c in df.columns}
    out = pd.DataFrame(
        {
            MFC_LOCATION: df[_pick(norms, "location", "locationname")],
            MFC_LOCATION_CODE: df[_pick(norms, "locationcode")],
            MFC_CODE: df[_pick(norms, "code")].astype(str).str.strip(),
            MFC_DESCRIPTION: df[_pick(norms, "description")]
            if "description" in norms
            else "",
            MFC_FACTOR_VALUE: pd.to_numeric(
                df[_pick(norms, "factorvalue", "factormultiplier")], errors="coerce"
            ),
            MFC_PERIOD: df[
                _pick(norms, "costupdatereportingperiodname", "reportingperiodname", "period")
            ].astype(str).str.strip(),
        }
    )
    # A NaN factor (blank cell) can't scale a cost; drop it so the engine treats
    # the code as missing -> factor 1.0 + warning, rather than propagating NaN.
    return out.dropna(subset=[MFC_FACTOR_VALUE]).reset_index(drop=True)


def _to_labor(df: pd.DataFrame) -> pd.DataFrame:
    """Map a labor workbook onto canonical LRC_* columns; drop NaN factor/rate."""
    norms = {_norm(c): c for c in df.columns}
    out = pd.DataFrame(
        {
            LRC_LOCATION: df[_pick(norms, "location", "locationname")],
            LRC_LOCATION_CODE: df[_pick(norms, "locationcode")],
            LRC_FACTOR_MULTIPLIER: pd.to_numeric(
                df[_pick(norms, "factormultiplier", "factorvalue")], errors="coerce"
            ),
            LRC_TOTAL_USD_RATE: pd.to_numeric(
                df[_pick(norms, "totalusdrate", "usdrate")], errors="coerce"
            ),
            LRC_PERIOD: df[
                _pick(norms, "costupdatereportingperiodname", "reportingperiodname", "period")
            ].astype(str).str.strip(),
        }
    )
    # A NaN multiplier or USD rate yields NaN costs and would still surface as a
    # pickable (location, period); drop those rows so the UI only offers usable
    # selections.
    return out.dropna(subset=[LRC_FACTOR_MULTIPLIER, LRC_TOTAL_USD_RATE]).reset_index(
        drop=True
    )


def _excel_paths() -> List[Path]:
    """Return the EMMA workbooks in ``emma_dir`` (ignoring Excel lock files)."""
    directory = Path(SETTINGS.emma_dir)
    if not directory.is_dir():
        raise FileNotFoundError(
            f"EMMA_SOURCE=excel but EMMA directory '{directory}' does not exist. "
            "Create it and drop MFC.xlsx / LRC.xlsx inside (or set EMMA_DIR)."
        )
    paths = sorted(
        p for p in directory.glob("*.xlsx") if not p.name.startswith("~$")
    )
    if not paths:
        raise FileNotFoundError(
            f"No .xlsx files found in EMMA directory '{directory}'."
        )
    return paths


@lru_cache(maxsize=1)
def _load_pair() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Read every workbook in ``emma_dir`` and return ``(material, labor)`` frames.

    Cached for the process lifetime: the workbooks are read once and reused, the
    same way mock frames are built once at import.
    """
    material: pd.DataFrame | None = None
    labor: pd.DataFrame | None = None
    for path in _excel_paths():
        raw = pd.read_excel(path)
        kind = _classify(raw)
        if kind == "material":
            if material is not None:
                raise ValueError(
                    "Found two material-shaped EMMA workbooks; expected exactly one."
                )
            material = _to_material(raw)
        else:
            if labor is not None:
                raise ValueError(
                    "Found two labor-shaped EMMA workbooks; expected exactly one."
                )
            labor = _to_labor(raw)
    if material is None or labor is None:
        missing = "material (per-code)" if material is None else "labor (multiplier + USD rate)"
        raise ValueError(
            f"Missing the {missing} EMMA workbook in '{SETTINGS.emma_dir}'. "
            "Expected one material-shaped and one labor-shaped file."
        )
    return material, labor


def load_excel_mfc() -> pd.DataFrame:
    """Material (MFC) reference frame loaded from Excel, canonical columns."""
    return _load_pair()[0]


def load_excel_lrc() -> pd.DataFrame:
    """Labor (LRC) reference frame loaded from Excel, canonical columns."""
    return _load_pair()[1]
