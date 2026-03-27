"""Pipe insulation schedule parser.

Normalization is applied automatically via alias_norm:
  - Service names are canonicalized (e.g. "CHW supply" -> "CHILLED WATER")
  - Insulation type names are canonicalized (e.g. "Armaflex" -> "ELASTOMERIC")


Maps raw table rows from the piping insulation schedule tables to
structured PipeInsulationRow dicts.

Target schema:
  Service           - e.g. "Chilled Water", "Heating Water", "Refrigerant"
  Pipe_Size_Range   - e.g. "Up to 1-1/2", "1-1/2 and over", "All Sizes"
  Thickness         - e.g. "1-1/2", "2", "3/4 min"
  Insulation_Type   - e.g. "Fiberglass", "Elastomeric Foam"
  Jacket_Required   - e.g. "Aluminum (exterior rigid)", "NPJ (exterior flexible)", ""
  Notes             - remarks/notes from the table
  PDF_File          - source filename (added by multi-file runner)
"""

from __future__ import annotations

import re
import unicodedata

from spec_parser.normalize.alias_norm import normalize_pipe_row


# ── helpers ──────────────────────────────────────────────────────────────────

_SOFT_HYPHEN = "\u00ad"
_FRAC_MAP = {
    "\u00bd": "1/2",
    "\u2153": "1/3",
    "\u2154": "2/3",
    "\u00bc": "1/4",
    "\u00be": "3/4",
    "\u2155": "1/5",
    "\u2156": "2/5",
    "\u2157": "3/5",
    "\u2158": "4/5",
    "\u2159": "1/6",
    "\u215a": "5/6",
    "\u2150": "1/7",
    "\u215b": "1/8",
    "\u215c": "3/8",
    "\u215d": "5/8",
    "\u215e": "7/8",
}


def _clean(text: str) -> str:
    """Normalize soft hyphens, unicode fractions, collapse whitespace."""
    for char, replacement in _FRAC_MAP.items():
        text = text.replace(char, replacement)
    text = text.replace(_SOFT_HYPHEN, "-")
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u00c2\u00e2\u0080\u0093\u0094]", "", text)  # common encoding artifacts
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_thickness(text: str) -> str:
    """Fix pdfplumber word-wrap artifacts in thickness and service cell text.

    pdfplumber frequently concatenates adjacent words without spaces, producing
    artefacts like "Upto11/2", "11/2andover", "Recir- culation".  This function
    normalises the most common patterns before they reach the alias normaliser.
    """
    # Repair hyphenated line-break artefacts: "Recir- culation" → "Recirculation"
    # Only collapse when the right side starts with a lowercase letter (not a
    # proper compound like "self-contained").
    text = re.sub(r"(\w)-\s+([a-z])", r"\1\2", text)

    # Fix "Upto" / "Upto2" → "Up to " — must run before mixed-number fix
    # so that "Upto11/2" → "Up to 11/2" → (next step) "Up to 1-1/2"
    text = re.sub(r"\bUpto\s*", "Up to ", text, flags=re.IGNORECASE)

    # Fix "Lessthan" → "Less than " (absorb any run-together space)
    text = re.sub(r"\bLessthan\s*", "Less than ", text, flags=re.IGNORECASE)

    # Fix "AllSizes" → "All Sizes"
    text = re.sub(r"\bAllSizes\b", "All Sizes", text, flags=re.IGNORECASE)

    # Fix "andover" / "andunder" / "andabove" / "andbelow" —
    # digit/non-word immediately followed by "and..." has no \b boundary,
    # so match the digit explicitly first, then catch remaining \b cases.
    for _pat, _rep in [
        (r"(\d)\s*andover\b",  r"\1 and over"),
        (r"(\d)\s*andunder\b", r"\1 and under"),
        (r"(\d)\s*andabove\b", r"\1 and above"),
        (r"(\d)\s*andbelow\b", r"\1 and below"),
    ]:
        text = re.sub(_pat, _rep, text, flags=re.IGNORECASE)
    for _pat, _rep in [
        (r"\bandover\b",  "and over"),
        (r"\bandunder\b", "and under"),
        (r"\bandabove\b", "and above"),
        (r"\bandbelow\b", "and below"),
    ]:
        text = re.sub(_pat, _rep, text, flags=re.IGNORECASE)

    # Fix space-separated mixed numbers: "1 1/2" → "1-1/2"
    text = re.sub(r"\b(\d)\s+(1/[2-9])\b", r"\1-\2", text)

    # Fix run-together mixed numbers: "11/2" → "1-1/2", "21/2" → "2-1/2"
    # No leading/trailing \b — after "Upto"→"Up to " the "1" now has a
    # space before it; after "andover" fixes the fraction may be at end of word.
    text = re.sub(r"(?<!\d)(\d)(1/[2-9])(?!\d)", r"\1-\2", text)

    return text


def _is_header_row(row: list[str]) -> bool:
    """True if row looks like a column header (contains known header words)."""
    joined = " ".join(row).lower()
    return any(kw in joined for kw in ("pipe size", "thickness", "remarks", "service"))


# ── table classifiers ─────────────────────────────────────────────────────────

_REJECT_TABLE_KEYWORDS = (
    "test pressure",
    "test medium",
    "hydrostatic",
    "pneumatic test",
    "pressure class",
    "design pressure",
)


def _looks_like_pipe_table(rows: list[list[str]]) -> bool:
    """True if this table looks like a piping insulation schedule.

    Rejects tables that are clearly non-insulation schedules (pressure-test
    tables, hydrostatic schedules, etc.) even when they appear on pages
    within an insulation section due to running headers.
    """
    if not rows:
        return False
    # Look across all header rows (first 4) for classification signals
    header_text = " ".join(" ".join(r) for r in rows[:4]).lower()
    for kw in _REJECT_TABLE_KEYWORDS:
        if kw in header_text:
            return False
    return "pipe size" in header_text or "piping" in header_text


# ── row parser ────────────────────────────────────────────────────────────────

def _parse_pipe_table(
    rows: list[list[str]],
    insulation_type: str,
) -> list[dict]:
    """Parse one raw pdfplumber table into PipeInsulationRow dicts.

    The schedule tables follow a pattern:
      Row 0 (optional): column headers
      Row N: [service_label, pipe_size, thickness, remarks/notes]

    Service labels may span multiple rows (first cell non-empty = new service).
    """
    out: list[dict] = []
    current_service = ""

    for row in rows:
        if not row or all(c == "" for c in row):
            continue
        if _is_header_row(row):
            continue

        cells = [_clean(c) for c in row]

        # Pad to 4 columns
        while len(cells) < 4:
            cells.append("")

        # columns: [service_or_blank, pipe_size, thickness, notes]
        # Some tables have 3 cols (no leading blank): [service, thickness, notes]
        # Detect by checking if col[1] looks like a pipe size
        if len(cells) >= 4:
            col_service = _clean_thickness(cells[0])
            col_size = _clean_thickness(cells[1])
            col_thick = _clean_thickness(cells[2])
            col_notes = cells[3]
        else:
            col_service = _clean_thickness(cells[0])
            col_size = ""
            col_thick = _clean_thickness(cells[1]) if len(cells) > 1 else ""
            col_notes = cells[2] if len(cells) > 2 else ""

        # A non-empty first column resets the current service
        if col_service:
            current_service = col_service

        # Skip rows with no useful data
        if not col_size and not col_thick:
            continue

        # Extract jacket info from notes
        jacket = _extract_jacket_hint(col_notes)

        out.append(
            {
                "Service": current_service,
                "Pipe_Size_Range": col_size,
                "Thickness": col_thick,
                "Insulation_Type": insulation_type,
                "Jacket_Required": jacket,
                "Notes": col_notes,
                "PDF_File": "",
            }
        )

    return out


def _extract_jacket_hint(notes: str) -> str:
    """Extract brief jacket requirement from notes text."""
    n = notes.lower()
    parts = []
    if "aluminum jacket" in n and "exterior" in n:
        parts.append("Aluminum (exterior rigid)")
    if "non-metallic polymeric" in n or "npj" in n or "flexible jacket" in n:
        parts.append("NPJ (exterior flexible)")
    if "pvc" in n and "jacket" in n:
        parts.append("PVC")
    if "stainless steel jacket" in n:
        parts.append("Stainless steel")
    return "; ".join(parts)


# ── public API ────────────────────────────────────────────────────────────────

def parse_pipe_insulation(
    tables: list[dict],
    pdf_file: str = "",
) -> list[dict]:
    """Parse pipe insulation rows from extracted table data.

    Args:
        tables: Output of table_extract.extract_tables_from_pdf / extract_schedule_tables.
        pdf_file: Source filename tag.

    Returns:
        List of PipeInsulationRow dicts.
    """
    rows_out: list[dict] = []

    for tbl in tables:
        raw_rows = tbl.get("rows", [])
        if not raw_rows:
            continue
        if not _looks_like_pipe_table(raw_rows):
            continue

        # Determine insulation type from text just above the table, then fall back to header
        context = (tbl.get("pre_table_text") or tbl.get("page_text") or "") + \
                  " ".join(" ".join(r) for r in raw_rows[:2])
        context_lower = context.lower()
        if "elastomeric" in context_lower or "closed cell" in context_lower:
            ins_type = "Elastomeric Foam (Closed Cell)"
        elif "fiberglass" in context_lower or "glass fiber" in context_lower or "fiber glass" in context_lower:
            ins_type = "Fiberglass"
        else:
            ins_type = "Unknown"

        parsed = _parse_pipe_table(raw_rows, ins_type)
        for r in parsed:
            r["PDF_File"] = pdf_file
            rows_out.append(normalize_pipe_row(r))

    return rows_out
