"""Service and material name normalization using alias maps + rapidfuzz fallback.

Resolution order:
  1. Exact match (case-insensitive) in the reverse alias map.
  2. rapidfuzz partial_ratio fuzzy match on aliases (threshold 80).
  3. Return the original string unchanged if no match found.
"""

from __future__ import annotations

import re

from spec_parser.config.service_dictionary import SERVICE_ALIAS_MAP, SERVICE_ALIASES
from spec_parser.config.material_dictionary import MATERIAL_ALIAS_MAP, MATERIAL_ALIASES

try:
    from rapidfuzz import fuzz, process as rf_process
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

_FUZZY_THRESHOLD = 80


def _build_alias_list(alias_dict: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return list of (alias_upper, canonical) for fuzzy matching."""
    items: list[tuple[str, str]] = []
    for canonical, aliases in alias_dict.items():
        for alias in aliases:
            items.append((alias.strip().upper(), canonical))
    return items


_SERVICE_ALIAS_LIST = _build_alias_list(SERVICE_ALIASES)
_MATERIAL_ALIAS_LIST = _build_alias_list(MATERIAL_ALIASES)


def _compress(s: str) -> str:
    """Lowercase and strip spaces/hyphens for substring matching of concatenated text."""
    return re.sub(r"[\s\-]", "", s.lower())


def _normalize(
    raw: str,
    exact_map: dict[str, str],
    alias_list: list[tuple[str, str]],
) -> str:
    """Normalize a raw string to its canonical form."""
    if not raw or not raw.strip():
        return raw

    key = raw.strip().upper()

    # 1. Exact match (case-insensitive)
    if key in exact_map:
        return exact_map[key]

    # 2. Compressed substring match — handles pdfplumber word-concatenation.
    #    Only match aliases >= 5 chars to avoid false positives.
    raw_compressed = _compress(raw)
    best_alias_len = 0
    best_canonical = ""
    for alias, canonical in alias_list:
        if len(alias) < 5:
            continue
        alias_compressed = _compress(alias)
        if alias_compressed in raw_compressed and len(alias) > best_alias_len:
            best_alias_len = len(alias)
            best_canonical = canonical
    if best_canonical:
        return best_canonical

    if not _HAS_RAPIDFUZZ:
        return raw

    # 3. Fuzzy match via rapidfuzz — fallback for near-miss text.
    fuzzy_candidates = [(a, c) for a, c in alias_list if len(a) >= 5]
    if not fuzzy_candidates:
        return raw

    alias_strings = [a for a, _ in fuzzy_candidates]
    match = rf_process.extractOne(
        key,
        alias_strings,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=_FUZZY_THRESHOLD,
    )
    if match:
        matched_alias = match[0]
        for alias, canonical in fuzzy_candidates:
            if alias == matched_alias:
                return canonical

    return raw


def normalize_service(raw: str) -> str:
    """Normalize a service/system name to its canonical form."""
    return _normalize(raw, SERVICE_ALIAS_MAP, _SERVICE_ALIAS_LIST)


def normalize_material(raw: str) -> str:
    """Normalize a material name to its canonical form."""
    return _normalize(raw, MATERIAL_ALIAS_MAP, _MATERIAL_ALIAS_LIST)
