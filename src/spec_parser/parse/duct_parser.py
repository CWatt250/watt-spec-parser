"""Duct insulation schedule parser.

Extracts structured rows from pdfplumber table dicts for ductwork insulation schedules.
Expects tables produced by spec_parser.extract.table_extract.extract_tables_from_pdf.

Output rows contain:
    System            - duct system description (supply, return, outside air, etc.)
    Thickness         - insulation thickness string (e.g. "1-1/2", "1")
    R_Value           - R-value if embedded in thickness string (e.g. "R-4")
    Finish            - facing/finish (FSK, PSK, liner, etc.)
    Exposed           - "Yes" if exposed location applies
    Concealed         - "Yes" if concealed location applies
    Outdoor           - "Yes" if outdoor/exterior applies
    Insulation_Type   - material inferred from table context
    Notes             - Remarks text
    PDF_File          - set by caller
    Page_Num          - source page
"""

from __future__ import annotations

import re

# Keywords that signal a duct table (distinguish from pipe tables)
_DUCT_HEADER_KEYWORDS = {"thickness", "finish", "remarks"}
_PIPE_KEYWORDS = {"pipe size", "pipe diameter", "pipe sz"}

# R-value pattern inside thickness strings like "1-1/2 (R-4)"
_R_VALUE_RE = re.compile(r"R[- ]?(\d+(?:\.\d+)?)", re.IGNORECASE)

# Material patterns (same approach as pipe_parser)
_MATERIAL_PATTERNS = [
    (re.compile(r"duct\s+liner|liner", re.I), "DUCT LINER"),
    (re.compile(r"elastomeric|closed[- ]?cell|armaflex", re.I), "ELASTOMERIC"),
    (re.compile(r"mineral\s+wool|rock\s?wool", re.I), "MINERAL WOOL"),
    (re.compile(r"rigid\s+fiberglass|rigid\s+board", re.I), "RIGID FIBERGLASS"),
    (re.compile(r"flexible\s+fiberglass|fiberglass\s+blanket|blanket", re.I), "FLEXIBLE FIBERGLASS"),
    (re.compile(r"fiberglass|glass\s+fiber|fiber\s+glass", re.I), "FIBERGLASS"),
]

# Location keywords (allow for pdfplumber word concatenation)
_EXPOSED_RE = re.compile(r"\bexpos(ed|ure)\b", re.I)
_CONCEALED_RE = re.compile(r"\bconceal(ed)?\b", re.I)
_OUTDOOR_RE = re.compile(r"outdoor|exterior|outside[- ]?air", re.I)

# Equipment patterns — regex to handle pdfplumber's word concatenation
_EQUIPMENT_PATTERNS = [
    re.compile(r"heat\s*exchanger", re.I),
    re.compile(r"expansion\s*tank", re.I),
    re.compile(r"air\s*separator", re.I),
    re.compile(r"storage\s*tank", re.I),
    re.compile(r"pump\s*bod", re.I),
]


def _is_equipment_table(rows: list[list[str]]) -> bool:
    content = " ".join(c for row in rows for c in row)
    return sum(1 for p in _EQUIPMENT_PATTERNS if p.search(content)) >= 2

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
    return s.translate(_CLEANUP).strip()


def _is_duct_table(rows: list[list[str]]) -> bool:
    """True if header row looks like a duct table (no pipe-size column)."""
    if not rows:
        return False
    header_text = " ".join(rows[0]).lower()
    # Must have thickness but NOT pipe-size markers
    has_thickness = "thickness" in header_text or "finish" in header_text
    has_pipe_markers = any(kw in header_text for kw in _PIPE_KEYWORDS)
    return has_thickness and not has_pipe_markers


def _infer_material(rows: list[list[str]], context_hint: str = "") -> str:
    full_text = context_hint + " " + " ".join(c for row in rows for c in row)
    for pattern, canonical in _MATERIAL_PATTERNS:
        if pattern.search(full_text):
            return canonical
    return "UNKNOWN"


def _parse_r_value(thickness: str) -> tuple[str, str]:
    """Return (thickness_clean, r_value) from strings like '1-1/2 (R-4)'."""
    m = _R_VALUE_RE.search(thickness)
    r_value = f"R-{m.group(1)}" if m else ""
    thickness_clean = _R_VALUE_RE.sub("", thickness).replace("(", "").replace(")", "").strip().strip("-").strip()
    return thickness_clean, r_value


def parse_duct_tables(
    tables: list[dict],
    pdf_file: str = "",
    context_hint: str = "",
) -> list[dict]:
    """Parse duct insulation schedule tables into structured rows.

    Args:
        tables: List of table dicts from extract_tables_from_pdf.
        pdf_file: Source PDF filename for tagging output rows.
        context_hint: Optional extra text to help infer insulation material.

    Returns:
        List of dicts with keys: System, Thickness, R_Value, Finish,
        Exposed, Concealed, Outdoor, Insulation_Type, Notes, PDF_File, Page_Num.
    """
    results: list[dict] = []

    for tbl in tables:
        rows = tbl.get("rows", [])
        page_num = tbl.get("page_num", 0)

        if not _is_duct_table(rows):
            continue
        if _is_equipment_table(rows):
            continue

        page_context = tbl.get("page_text", "") or ""
        material = _infer_material(rows, context_hint + " " + page_context)

        header = [c.lower() for c in rows[0]]

        def _col(*keywords: str) -> int:
            for k in keywords:
                for i, h in enumerate(header):
                    if k in h:
                        return i
            return -1

        sys_col = 0
        thick_col = _col("thickness", "thick")
        finish_col = _col("finish", "facing", "jacket")
        rem_col = _col("remark", "note", "comment")

        if thick_col == -1:
            continue

        current_system = ""
        for row in rows[1:]:
            if len(row) <= thick_col:
                continue

            raw_sys = _clean(row[sys_col]) if sys_col < len(row) else ""
            if raw_sys:
                current_system = raw_sys

            if not current_system:
                continue

            thickness_raw = _clean(row[thick_col])
            finish = _clean(row[finish_col]) if (finish_col != -1 and finish_col < len(row)) else ""
            notes = _clean(row[rem_col]) if (rem_col != -1 and rem_col < len(row)) else ""

            if not thickness_raw:
                continue

            thickness, r_value = _parse_r_value(thickness_raw)
            combined = current_system + " " + notes

            results.append(
                {
                    "System": current_system,
                    "Thickness": thickness,
                    "R_Value": r_value,
                    "Finish": finish,
                    "Exposed": "Yes" if _EXPOSED_RE.search(combined) else "",
                    "Concealed": "Yes" if _CONCEALED_RE.search(combined) else "",
                    "Outdoor": "Yes" if _OUTDOOR_RE.search(combined) else "",
                    "Insulation_Type": material,
                    "Notes": notes,
                    "PDF_File": pdf_file,
                    "Page_Num": page_num,
                }
            )

    return results
