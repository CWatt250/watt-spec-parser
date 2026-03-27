"""Pipe insulation schedule parser.

Extracts structured rows from pdfplumber table dicts for piping insulation schedules.
Expects tables produced by spec_parser.extract.table_extract.extract_tables_from_pdf.

Output rows contain:
    Service           - normalized service/system name
    Pipe_Size_Range   - pipe size range string (e.g. "Up to 1\"", "1\" and over")
    Thickness         - insulation thickness string (e.g. "1", "1.5", "2")
    Insulation_Type   - material inferred from table context
    Jacket_Required   - jacket info extracted from Remarks column
    Notes             - remainder of Remarks text
    PDF_File          - set by caller
    Page_Num          - source page
"""

from __future__ import annotations

import re

from spec_parser.normalize.aliases import normalize_service, normalize_material

# Keywords that signal a table is a pipe insulation table
_PIPE_HEADER_KEYWORDS = {"pipe size", "pipe sz", "pipe diameter"}

# Keywords that signal an equipment table (skip these)
_EQUIPMENT_KEYWORDS = {"heat exchanger", "expansion tank", "air separator", "pump", "storage tank"}

# Jacket keywords to scan in remarks
_JACKET_RE = re.compile(
    r"(aluminum|pvc|stainless steel|canvas|asp|all[- ]service|polymeric|non[- ]metallic)"
    r"(?:\s+(?:jacket|jacketing|cover|covering|finish))?",
    re.IGNORECASE,
)

# Thickness clean-up: collapse non-breaking hyphens, smart quotes → plain
_CLEANUP = str.maketrans(
    {
        "\u00ad": "-",   # soft hyphen
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        "\u00bd": "1/2",
        "\u00bc": "1/4",
        "\u00be": "3/4",
    }
)

# Common material keyword patterns inside table header/title text
_MATERIAL_PATTERNS = [
    (re.compile(r"elastomeric|closed[- ]?cell|armaflex", re.I), "ELASTOMERIC"),
    (re.compile(r"mineral\s+wool|rock\s?wool", re.I), "MINERAL WOOL"),
    (re.compile(r"cellular\s+glass|foam\s+glass", re.I), "CELLULAR GLASS"),
    (re.compile(r"polyiso|polyisocyanurate", re.I), "POLYISO"),
    (re.compile(r"fiberglass|glass\s+fiber|fiber\s+glass", re.I), "FIBERGLASS"),
]


def _clean(s: str) -> str:
    return s.translate(_CLEANUP).strip()


def _is_pipe_table(rows: list[list[str]]) -> bool:
    """Check if header row contains 'Pipe Size' or similar."""
    if not rows:
        return False
    header = " ".join(rows[0]).lower()
    return any(kw in header for kw in _PIPE_HEADER_KEYWORDS)


def _is_equipment_table(rows: list[list[str]]) -> bool:
    """True if the table looks like an equipment (not pipe) table."""
    content = " ".join(c for row in rows for c in row).lower()
    return sum(1 for kw in _EQUIPMENT_KEYWORDS if kw in content) >= 2


def _infer_material(rows: list[list[str]], context_hint: str = "") -> str:
    """Infer insulation material from cell text + optional context hint."""
    full_text = context_hint + " " + " ".join(c for row in rows for c in row)
    for pattern, canonical in _MATERIAL_PATTERNS:
        if pattern.search(full_text):
            return canonical
    return "UNKNOWN"


def _extract_jacket(remarks: str) -> tuple[str, str]:
    """Return (jacket_required, notes) from a remarks string."""
    jacket_match = _JACKET_RE.search(remarks)
    if jacket_match:
        jacket = _clean(jacket_match.group(0)).upper()
        notes = _clean(remarks)
        return jacket, notes
    return "", _clean(remarks)


def parse_pipe_tables(
    tables: list[dict],
    pdf_file: str = "",
    context_hint: str = "",
) -> list[dict]:
    """Parse pipe insulation schedule tables into structured rows.

    Args:
        tables: List of table dicts from extract_tables_from_pdf.
        pdf_file: Source PDF filename for tagging output rows.
        context_hint: Optional text from surrounding spec sections to help
                      infer insulation material type.

    Returns:
        List of dicts with keys: Service, Pipe_Size_Range, Thickness,
        Insulation_Type, Jacket_Required, Notes, PDF_File, Page_Num.
    """
    results: list[dict] = []

    for tbl in tables:
        rows = tbl.get("rows", [])
        page_num = tbl.get("page_num", 0)

        if not _is_pipe_table(rows):
            continue
        if _is_equipment_table(rows):
            continue

        # Use page_text (from extract_tables_from_pdf with include_page_text=True)
        # as additional context for material inference when available.
        page_context = tbl.get("page_text", "") or ""
        material = _infer_material(rows, context_hint + " " + page_context)

        # Determine column indices from header row
        header = [c.lower() for c in rows[0]]

        def _col(*keywords: str) -> int:
            for k in keywords:
                for i, h in enumerate(header):
                    if k in h:
                        return i
            return -1

        svc_col = 0  # service is always the first column
        size_col = _col("pipe size", "size", "diameter")
        thick_col = _col("thickness", "thick")
        rem_col = _col("remark", "note", "comment")

        if size_col == -1 or thick_col == -1:
            continue  # can't parse without size + thickness

        current_service = ""
        for row in rows[1:]:
            if len(row) <= max(size_col, thick_col):
                continue

            raw_svc = _clean(row[svc_col]) if svc_col < len(row) else ""
            if raw_svc:
                current_service = raw_svc

            if not current_service:
                continue

            size = _clean(row[size_col])
            thickness = _clean(row[thick_col])
            remarks = _clean(row[rem_col]) if (rem_col != -1 and rem_col < len(row)) else ""

            if not size and not thickness:
                continue  # blank data row

            jacket, notes = _extract_jacket(remarks)

            results.append(
                {
                    "Service": normalize_service(current_service),
                    "Pipe_Size_Range": size,
                    "Thickness": thickness,
                    "Insulation_Type": normalize_material(material),
                    "Jacket_Required": jacket,
                    "Notes": notes,
                    "PDF_File": pdf_file,
                    "Page_Num": page_num,
                }
            )

    return results
