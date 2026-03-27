"""Alias-based normalization for service and material names.

Two-stage lookup:
  1. Exact match (case-insensitive) against the reverse alias maps.
  2. Fuzzy match via rapidfuzz if no exact hit, using a configurable
     minimum score threshold.

Usage:
    from spec_parser.normalize.alias_norm import normalize_service, normalize_material

    normalize_service("CHW supply")    -> "CHILLED WATER"
    normalize_material("Armaflex")     -> "ELASTOMERIC"
"""

from __future__ import annotations

import re

from rapidfuzz import process as rf_process, fuzz

from spec_parser.config.service_dictionary import SERVICE_ALIAS_MAP
from spec_parser.config.material_dictionary import MATERIAL_ALIAS_MAP


# ── thresholds ────────────────────────────────────────────────────────────────

FUZZY_MIN_SCORE = 80  # 0-100; below this, return None (no confident match)
FUZZY_LIMIT = 1       # top-N candidates to consider


# ── helpers ───────────────────────────────────────────────────────────────────

_CLEAN_RE = re.compile(r"[^A-Z0-9\s]")


def _key(text: str) -> str:
    """Upper-case and strip non-alphanumeric for map lookup."""
    return _CLEAN_RE.sub("", text.strip().upper()).strip()


def _exact(text: str, alias_map: dict[str, str]) -> str | None:
    return alias_map.get(_key(text))


def _fuzzy(text: str, alias_map: dict[str, str], min_score: int = FUZZY_MIN_SCORE) -> str | None:
    """Fuzzy-match `text` against the alias map keys; return canonical if score >= min_score.

    Uses token_set_ratio so longer query strings still match short alias keys
    (e.g. "Chilled Water Supply and Return Systems" -> "CHILLED WATER SUPPLY").
    """
    query = _key(text)
    if not query:
        return None
    # rapidfuzz.process.extractOne returns (match, score, key) or None
    result = rf_process.extractOne(
        query,
        alias_map.keys(),
        scorer=fuzz.token_set_ratio,
        score_cutoff=min_score,
    )
    if result is None:
        return None
    matched_alias = result[0]
    return alias_map[matched_alias]


# ── public API ────────────────────────────────────────────────────────────────

def normalize_service(raw: str, fuzzy: bool = True, min_score: int = FUZZY_MIN_SCORE) -> str:
    """Normalize a raw service/system name to canonical form.

    Returns the canonical name (e.g. "CHILLED WATER") or the original
    stripped value if no match found.
    """
    if not raw or not raw.strip():
        return raw
    canonical = _exact(raw, SERVICE_ALIAS_MAP)
    if canonical is None and fuzzy:
        canonical = _fuzzy(raw, SERVICE_ALIAS_MAP, min_score=min_score)
    return canonical or raw.strip()


def normalize_material(raw: str, fuzzy: bool = True, min_score: int = FUZZY_MIN_SCORE) -> str:
    """Normalize a raw material/insulation type name to canonical form.

    Returns the canonical name (e.g. "ELASTOMERIC") or the original
    stripped value if no match found.
    """
    if not raw or not raw.strip():
        return raw
    canonical = _exact(raw, MATERIAL_ALIAS_MAP)
    if canonical is None and fuzzy:
        canonical = _fuzzy(raw, MATERIAL_ALIAS_MAP, min_score=min_score)
    return canonical or raw.strip()


def normalize_pipe_row(row: dict) -> dict:
    """Apply service and material normalization to a PipeInsulationRow dict in-place."""
    row = dict(row)
    row["Service"] = normalize_service(row.get("Service", ""))
    row["Insulation_Type"] = normalize_material(row.get("Insulation_Type", ""))
    return row


def normalize_duct_row(row: dict) -> dict:
    """Apply material normalization to a DuctInsulationRow dict in-place."""
    row = dict(row)
    row["Insulation_Type"] = normalize_material(row.get("Insulation_Type", ""))
    return row
