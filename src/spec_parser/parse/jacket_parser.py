"""Jacket / covering rules extractor.

Scans raw spec text (not tables) for explicit statements about jacket/covering
requirements. Returns structured rows: Rule, Condition, Jacket_Type, Notes.

Strategy:
  1. Split text into sentences/clauses.
  2. For each clause that mentions a jacket keyword, extract:
     - jacket type (aluminum, PVC, canvas, ASP, all-service, polymeric, …)
     - condition context (indoor, outdoor, exposed, concealed, exterior, interior,
       underground, refrigerant, etc.)
     - the service/system mentioned nearby
  3. Return deduplicated list of rules.
"""

from __future__ import annotations

import re

# Jacket/covering type patterns
_JACKET_TYPES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"aluminum\s+jacket(?:ing)?", re.I), "ALUMINUM JACKET"),
    (re.compile(r"stainless\s+steel\s+jacket(?:ing)?", re.I), "STAINLESS STEEL JACKET"),
    (re.compile(r"pvc\s+jacket(?:ing)?", re.I), "PVC JACKET"),
    (re.compile(r"canvas\s+jacket(?:ing)?", re.I), "CANVAS JACKET"),
    (re.compile(r"all[- ]service\s+jacket(?:ing)?", re.I), "ALL-SERVICE JACKET"),
    (re.compile(r"asp\s+jacket(?:ing)?", re.I), "ASP JACKET"),
    (re.compile(r"polymeric\s+(?:flexible\s+)?jacket(?:ing)?", re.I), "POLYMERIC JACKET"),
    (re.compile(r"non[- ]metallic\s+polymeric\s+(?:flexible\s+)?jacket(?:ing)?", re.I), "NON-METALLIC POLYMERIC JACKET"),
    (re.compile(r"integral\s+(?:non[- ]metallic\s+)?(?:polymeric\s+)?(?:flexible\s+)?jacket(?:ing)?", re.I), "INTEGRAL JACKET"),
    (re.compile(r"vapor\s+retardant\s+jacket(?:ing)?", re.I), "VAPOR RETARDANT JACKET"),
    (re.compile(r"zeston\s+\d+", re.I), "ZESTON JACKETING"),
    (re.compile(r"jacketing\s+and\s+fitting\s+covers", re.I), "JACKETING/FITTING COVERS"),
    # Generic fallback — must come last
    (re.compile(r"\bjacket(?:ing)?\b", re.I), "JACKET (GENERIC)"),
]

# Condition keywords
_CONDITION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bexterior\b", re.I), "EXTERIOR"),
    (re.compile(r"\boutdoor\b", re.I), "OUTDOOR"),
    (re.compile(r"\bexposed\b", re.I), "EXPOSED"),
    (re.compile(r"\binterior\b", re.I), "INTERIOR"),
    (re.compile(r"\bindoor\b", re.I), "INDOOR"),
    (re.compile(r"\bconcealed\b", re.I), "CONCEALED"),
    (re.compile(r"\bunderground\b", re.I), "UNDERGROUND"),
    (re.compile(r"\bbelow\s*grade\b", re.I), "BELOW GRADE"),
    (re.compile(r"\brigid\s+piping\b", re.I), "RIGID PIPING"),
    (re.compile(r"\bflexible\s+piping\b", re.I), "FLEXIBLE PIPING"),
    (re.compile(r"\bmechanical\s+(?:equipment\s+)?room", re.I), "MECHANICAL ROOM"),
    (re.compile(r"\bfinished\s+space", re.I), "FINISHED SPACE"),
]

# Service/system proximity patterns
_SERVICE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"refrigerant\s+pip(?:ing|e)", re.I), "REFRIGERANT"),
    (re.compile(r"chilled\s+water", re.I), "CHILLED WATER"),
    (re.compile(r"heating\s+(?:hot\s+)?water", re.I), "HEATING WATER"),
    (re.compile(r"domestic\s+hot\s+water", re.I), "DOMESTIC HOT WATER"),
    (re.compile(r"condenser\s+water", re.I), "CONDENSER WATER"),
    (re.compile(r"steam\b", re.I), "STEAM"),
    (re.compile(r"condensate\b", re.I), "CONDENSATE"),
    (re.compile(r"\bequipment\b", re.I), "EQUIPMENT"),
    (re.compile(r"\bductwork?\b|\bduct\b", re.I), "DUCTWORK"),
]

# Sentence/clause splitter — split on period-newline, semicolons, bullet markers
_SENT_SPLIT_RE = re.compile(r"(?:\.\s*\n|\n(?=\d+\.|\s*[a-zA-Z]\.\s)|\.\s{2,}|;\s*)")

# Repeating page header patterns to strip before processing
_PAGE_HEADER_RE = re.compile(
    r"(?:AWS\s+DATA\s+CENTER[^\n]*\n?"
    r"|PRIMARY\s+SPECIFICATION[^\n]*\n?"
    r"|\d{4}[-\u2013]\d{2}[-\u2013]\d{2}\s*\n?)",
    re.I,
)

_CLEANUP = str.maketrans(
    {
        "\u00ad": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00bd": "1/2",
        "\u00bc": "1/4",
        "\u00be": "3/4",
    }
)


def _clean(s: str) -> str:
    return " ".join(s.translate(_CLEANUP).split())


def _detect_jacket_type(text: str) -> str:
    for pattern, label in _JACKET_TYPES[:-1]:  # Skip generic fallback initially
        if pattern.search(text):
            return label
    if _JACKET_TYPES[-1][0].search(text):
        return _JACKET_TYPES[-1][1]
    return ""


def _detect_conditions(text: str) -> list[str]:
    return [label for pattern, label in _CONDITION_PATTERNS if pattern.search(text)]


def _detect_service(text: str) -> str:
    for pattern, label in _SERVICE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def extract_jacket_rules(
    page_texts: list[str],
    pdf_file: str = "",
) -> list[dict]:
    """Scan raw page texts for jacket/covering requirements.

    Args:
        page_texts: List of raw text strings, one per page.
        pdf_file: Source PDF filename for tagging output rows.

    Returns:
        List of dicts: Rule, Condition, Jacket_Type, Service, Notes, PDF_File.
        Duplicates (same Jacket_Type + Condition + Service) are removed.
    """
    results: list[dict] = []
    seen: set[tuple] = set()

    for page_num, text in enumerate(page_texts, start=1):
        # Strip repeating page headers/footers before clause extraction
        text = _PAGE_HEADER_RE.sub(" ", text)
        cleaned = _clean(text)
        clauses = _SENT_SPLIT_RE.split(cleaned)

        for clause in clauses:
            clause = clause.strip()
            if not clause or len(clause) < 10:
                continue

            jacket_type = _detect_jacket_type(clause)
            if not jacket_type:
                continue

            conditions = _detect_conditions(clause)
            condition_str = ", ".join(conditions) if conditions else "GENERAL"
            service = _detect_service(clause)

            dedup_key = (jacket_type, condition_str, service)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            results.append(
                {
                    "Rule": clause[:300],
                    "Condition": condition_str,
                    "Jacket_Type": jacket_type,
                    "Service": service,
                    "Notes": "",
                    "PDF_File": pdf_file,
                    "Page_Num": page_num,
                }
            )

    return results
