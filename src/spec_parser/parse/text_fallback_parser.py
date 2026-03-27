"""Text-based fallback parser for insulation specs without ruled tables.

Handles the two common plain-text insulation schedule formats found in specs
that pdfplumber cannot extract as tables (no visible ruling lines):

Format A — CSI numbered-list (Microsoft/PHX73/PHX83 pattern):
    3.13  INDOOR PIPING INSULATION SCHEDULE
    A.  Domestic Cold Water:
        1.  NPS 1 and Smaller:  Insulation shall be the following:
            a.  Mineral-Fiber, Preformed Pipe Insulation, Type I:  1 inch thick.
        2.  NPS 1-1/4 and Larger:  ...
            a.  Mineral-Fiber ...:  1-1/2 inch thick.

Format B — Paragraph thickness table (UO2 pattern):
    1.  Service (Domestic) Water Piping:
        a.  Hot, 140F and under:  (conductivity: ...)
            1)  Sizes smaller than 1-1/2":  1"
            2)  Sizes 1-1/2" and larger:  1-1/2"
        b.  Cold, 40F to 60F:
            1)  Sizes smaller than 1-1/2":  1/2"
"""

from __future__ import annotations

import re
import unicodedata

from spec_parser.normalize.alias_norm import normalize_pipe_row


# ── unicode fraction normalization (mirrors pipe_parser._clean) ────────────────

_FRAC_MAP = {
    "\u00bd": "1/2", "\u00bc": "1/4", "\u00be": "3/4",
    "\u2153": "1/3", "\u2154": "2/3",
    "\u215b": "1/8", "\u215c": "3/8", "\u215d": "5/8", "\u215e": "7/8",
}
_SOFT_HYPHEN = "\u00ad"


def _clean(text: str) -> str:
    for ch, rep in _FRAC_MAP.items():
        text = text.replace(ch, rep)
    text = text.replace(_SOFT_HYPHEN, "-")
    # Normalize curly/typographic quotes to ASCII before NFKD
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # '' single
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # "" double (inch mark)
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u00c2\u00e2\u0080\u0093\u0094]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_thickness(raw: str) -> str:
    """Normalize a raw thickness token to a standard form, e.g. '1-1/2"'."""
    t = _clean(raw).strip().rstrip('"\'')
    # Fix run-together mixed number (e.g. "11/2" → "1-1/2")
    t = re.sub(r"(?<!\d)(\d)(1/[2-9])(?!\d)", r"\1-\2", t)
    if t and not t.endswith('"'):
        t += '"'
    return t


# ── bullet-line joiner ────────────────────────────────────────────────────────

_BULLET_PREFIX_RE = re.compile(
    r"^(?:[A-Z]\.|[a-z]\."          # uppercase or lowercase letter bullet
    r"|\d+\."                         # number bullet
    r"|\d+\))\s*$"                    # number-paren bullet
)


def _join_bullet_lines(raw_lines: list[str]) -> list[str]:
    """Join fitz-split bullet prefixes with their following content line.

    fitz often extracts "A." and "Domestic Cold Water:" on separate lines.
    Re-join them into "A.  Domestic Cold Water:" so the state-machine regex
    patterns can match the full line.
    """
    out: list[str] = []
    pending = ""
    for raw in raw_lines:
        line = _clean(raw.strip())
        if not line:
            if not pending:
                out.append("")
            continue
        if _BULLET_PREFIX_RE.match(line):
            # Flush any accumulated prefix first (orphan bullet)
            if pending:
                out.append(pending)
            pending = line
        elif pending:
            out.append(pending + "  " + line)
            pending = ""
        else:
            out.append(line)
    if pending:
        out.append(pending)
    return out


# ── schedule section detector ──────────────────────────────────────────────────

_SCHEDULE_HEADER_RE = re.compile(
    r"(?:INDOOR|OUTDOOR|PIPING|PIPE)\s+INSULATION\s+SCHEDULE"
    r"|INSULATION\s+THICKNESS(?:\s+AND\s+CONDUCTIVITY)?",
    re.IGNORECASE,
)

_NEXT_SECTION_RE = re.compile(
    r"^\s*\d+\.\d+\s+[A-Z]",  # e.g. "3.15  ANOTHER SECTION HEADER"
)

# ── format-A (CSI numbered-list) ──────────────────────────────────────────────

# "A.  Domestic Cold Water:"  or  "A. Domestic Hot Water:"
_SVC_LINE_RE = re.compile(r"^([A-Z])\.\s{1,4}(.+?):\s*$")

# "1.  NPS 1 and Smaller:..."  or  "1.  All Pipe Sizes:..."
_SIZE_LINE_RE = re.compile(
    r"^\d+\.\s{1,4}"
    r"(?P<size>(?:NPS\s+[\d\-/]+[\w\s]*|All\s+Pipe\s+Sizes?))",
    re.IGNORECASE,
)

# "a.  Mineral-Fiber ...:  1 inch thick."  or  "a.  Flexible Elastomeric:  1/2 inch thick."
_THICK_A_RE = re.compile(
    r"^[a-z]\.\s{1,4}(?P<type>.+?):\s+"
    r"(?P<thick>[\d\-/½¾¼⅜⅝⅞]+)\s+inch(?:es?)?\s+thick",
    re.IGNORECASE,
)

# ── format-B (UO2 paragraph style) ────────────────────────────────────────────

# "1.  Service (Domestic) Water Piping:"  — catches main service labels
# Optional trailing colon to handle lines without one
_SVC_B_RE = re.compile(
    r"^\d+\.\s{1,4}(.+?(?:[Ww]ater|[Hh]eating|[Cc]hilled|[Rr]efrigera|[Cc]ondensate|[Ss]torm)[^:]{0,40}):?\s*$"
)

# "a.  Hot, 140F and under:"  — sub-service qualifier
_SUBSVC_RE = re.compile(r"^[a-z]\.\s{1,4}(.+?)(?:\s*\([^)]*\))?\s*:\s*$")

# "1)  Sizes smaller than 1-1/2":  1""  or  "2)  Sizes 1-1/2" and larger:  1-1/2""
# Handles both:
#   "1)  Sizes smaller than 1-1/2": 1""  (inch mark after size and after thick)
#   "1)  Sizes smaller than 1-1/2: 1"    (no inch mark in size)
# After _clean the inch mark is ASCII 0x22.
_SIZE_THICK_B_RE = re.compile(
    r'^\d+\)\s{1,4}(?:Sizes?\s+)?(?P<size>[^:]+?)"\s*:\s+(?P<thick>[\d\-/]+)"?\s*$'
    r'|^\d+\)\s{1,4}(?:Sizes?\s+)?(?P<size2>[^:]+?):\s+(?P<thick2>[\d\-/]+)"?\s*$',
    re.IGNORECASE,
)


# ── public API ────────────────────────────────────────────────────────────────

def parse_text_pipe_insulation(
    page_texts: list[str],
    pdf_file: str = "",
) -> list[dict]:
    """Extract pipe insulation rows from plain text using regex state machine.

    Tries Format A (CSI numbered-list) first.  If that yields fewer than 2 rows
    also tries Format B (UO2 paragraph style) and returns whichever is richer.

    Args:
        page_texts: Per-page text strings (from PyMuPDF / fitz).
        pdf_file:   Source filename tag.

    Returns:
        List of PipeInsulationRow dicts (normalised).
    """
    # Join pages preserving line structure; unicode/fraction cleanup happens
    # per-line inside the parsers to avoid collapsing newlines with _clean().
    full_text = "\n".join(page_texts)
    rows_a = _parse_format_a(full_text, pdf_file)
    rows_b = _parse_format_b(full_text, pdf_file)
    rows = rows_a if len(rows_a) >= len(rows_b) else rows_b
    return [normalize_pipe_row(r) for r in rows]


# ── format-A parser ───────────────────────────────────────────────────────────

def _parse_format_a(text: str, pdf_file: str) -> list[dict]:
    rows: list[dict] = []
    in_schedule = False
    current_service = ""
    current_size = ""

    for stripped in _join_bullet_lines(text.splitlines()):
        if not stripped:
            continue

        # Detect schedule section start
        if _SCHEDULE_HEADER_RE.search(stripped):
            in_schedule = True
            current_service = ""
            current_size = ""
            continue

        # Detect end of schedule (next numbered section that is not a schedule)
        if in_schedule and _NEXT_SECTION_RE.match(stripped):
            if not _SCHEDULE_HEADER_RE.search(stripped):
                in_schedule = False
                current_service = ""
                current_size = ""
            continue

        if not in_schedule:
            continue

        # Service label line
        m = _SVC_LINE_RE.match(stripped)
        if m:
            current_service = m.group(2).strip()
            current_size = ""
            continue

        # Pipe-size line
        m = _SIZE_LINE_RE.match(stripped)
        if m:
            current_size = m.group("size").strip()
            continue

        # Thickness line
        m = _THICK_A_RE.match(stripped)
        if m and current_service and current_size:
            ins_type = m.group("type").strip()
            thickness = _norm_thickness(m.group("thick"))
            rows.append({
                "Service": current_service,
                "Pipe_Size_Range": current_size,
                "Thickness": thickness,
                "Insulation_Type": ins_type,
                "Jacket_Required": "",
                "Notes": "",
                "PDF_File": pdf_file,
            })

    return rows


# ── format-B parser ───────────────────────────────────────────────────────────

def _parse_format_b(text: str, pdf_file: str) -> list[dict]:
    rows: list[dict] = []
    in_thickness_section = False
    current_service = ""
    current_sub = ""

    for stripped in _join_bullet_lines(text.splitlines()):
        if not stripped:
            continue

        # Trigger: "Insulation thickness and conductivity" or similar
        if re.search(r"Insulation\s+thickness", stripped, re.IGNORECASE):
            in_thickness_section = True
            continue

        # End trigger: back to next numbered section like "D. Application:"
        if in_thickness_section and re.match(r"^[A-Z]\.\s+Application", stripped):
            in_thickness_section = False
            continue

        if not in_thickness_section:
            continue

        # Main service line: "1. Service (Domestic) Water Piping:"
        m = _SVC_B_RE.match(stripped)
        if m:
            current_service = m.group(1).strip()
            current_sub = ""
            continue

        # Sub-service line: "a. Hot, 140F and under:"
        m = _SUBSVC_RE.match(stripped)
        if m and current_service:
            current_sub = m.group(1).strip()
            continue

        # Size + thickness line: "1) Sizes smaller than 1-1/2": 1""
        m = _SIZE_THICK_B_RE.match(stripped)
        if m and current_service:
            size_desc = _clean(m.group("size") or m.group("size2") or "")
            thickness = _norm_thickness(m.group("thick") or m.group("thick2") or "")
            svc = current_service
            if current_sub:
                svc = f"{current_service} ({current_sub})"
            rows.append({
                "Service": svc,
                "Pipe_Size_Range": size_desc,
                "Thickness": thickness,
                "Insulation_Type": "Mineral Fiber / Elastomeric (see spec)",
                "Jacket_Required": "",
                "Notes": "",
                "PDF_File": pdf_file,
            })

    return rows
