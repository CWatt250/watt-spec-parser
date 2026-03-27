"""Duct insulation schedule parser.

Maps raw table rows from the ductwork insulation schedule tables to
structured DuctInsulationRow dicts.

Target schema:
  System          - e.g. "Supply/Return Air Ducts", "Outside Air Ducts", "Duct Liner"
  Exposed         - thickness for exposed/interior location (inches string)
  Concealed       - thickness for concealed location (inches string)
  Outdoor         - thickness for outdoor/exterior location (inches string)
  Insulation_Type - e.g. "Flexible Fiberglass Blanket", "Elastomeric Foam Duct Liner"
  Finish          - jacket/facing, e.g. "FSK/PSK"
  Notes           - remarks
  PDF_File        - source filename tag
"""

from __future__ import annotations

import re
import unicodedata

from spec_parser.normalize.alias_norm import normalize_duct_row


# ── helpers ──────────────────────────────────────────────────────────────────

_SOFT_HYPHEN = "\u00ad"
_FRAC_MAP = {
    "\u00bd": "1/2",
    "\u00bc": "1/4",
    "\u00be": "3/4",
    "\u2153": "1/3",
    "\u2154": "2/3",
}


def _clean(text: str) -> str:
    for char, replacement in _FRAC_MAP.items():
        text = text.replace(char, replacement)
    text = text.replace(_SOFT_HYPHEN, "-")
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u00c2\u00e2\u0080\u0093\u0094]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_header_row(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return any(kw in joined for kw in ("thickness", "finish", "remarks", "application"))


def _looks_like_duct_table(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    joined = " ".join(" ".join(r) for r in rows[:3]).lower()
    # Must mention ductwork/duct and NOT pipe size
    return (
        ("duct" in joined or "air" in joined)
        and "pipe size" not in joined
    )


# ── location classifier ───────────────────────────────────────────────────────

def _classify_location(text: str) -> tuple[str, str, str]:
    """Return (exposed, concealed, outdoor) thickness hints from application text."""
    t = text.lower()
    exposed = concealed = outdoor = ""
    if "outside air" in t or "outdoor" in t or "exterior" in t:
        outdoor = "see notes"
    if "supply" in t or "return" in t:
        exposed = "see schedule"
        concealed = "see schedule"
    return exposed, concealed, outdoor


# ── row parser ────────────────────────────────────────────────────────────────

def _parse_duct_table(
    rows: list[list[str]],
    insulation_type: str,
) -> list[dict]:
    out: list[dict] = []
    current_application = ""

    for row in rows:
        if not row or all(c == "" for c in row):
            continue
        if _is_header_row(row):
            continue

        cells = [_clean(c) for c in row]
        while len(cells) < 4:
            cells.append("")

        # Table layout: [application, thickness, finish, remarks]
        # First column may be blank (continuation of previous application)
        col_app = cells[0]
        col_thick = cells[1]
        col_finish = cells[2]
        col_notes = cells[3]

        if col_app:
            current_application = col_app

        if not col_thick and not current_application:
            continue

        app_lower = current_application.lower()
        notes_lower = col_notes.lower()

        # Determine where this thickness applies based on application text
        if any(kw in app_lower for kw in ("outside air", "outsideair", "outdoor", "exterior")):
            exposed = ""
            concealed = ""
            outdoor = col_thick
        else:
            exposed = col_thick
            concealed = col_thick
            outdoor = ""

        out.append(
            {
                "System": current_application,
                "Exposed": exposed,
                "Concealed": concealed,
                "Outdoor": outdoor,
                "Insulation_Type": insulation_type,
                "Finish": col_finish,
                "Notes": col_notes,
                "PDF_File": "",
            }
        )

    return out


# ── public API ────────────────────────────────────────────────────────────────

def parse_duct_insulation(
    tables: list[dict],
    pdf_file: str = "",
) -> list[dict]:
    """Parse duct insulation rows from extracted table data.

    Args:
        tables: Output of table_extract.extract_schedule_tables.
        pdf_file: Source filename tag.

    Returns:
        List of DuctInsulationRow dicts.
    """
    rows_out: list[dict] = []

    for tbl in tables:
        raw_rows = tbl.get("rows", [])
        if not raw_rows or not _looks_like_duct_table(raw_rows):
            continue

        # Resolve insulation type from context above the table
        context = (tbl.get("pre_table_text") or tbl.get("page_text") or "") + \
                  " ".join(" ".join(r) for r in raw_rows[:2])
        c = context.lower()

        if "elastomeric" in c or "liner" in c:
            ins_type = "Elastomeric Foam Duct Liner"
        elif "fiberglass" in c or "blanket" in c or "wrap" in c:
            ins_type = "Flexible Fiberglass Blanket"
        else:
            ins_type = "Unknown"

        parsed = _parse_duct_table(raw_rows, ins_type)
        for r in parsed:
            r["PDF_File"] = pdf_file
            rows_out.append(normalize_duct_row(r))

    return rows_out
