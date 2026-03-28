"""Text-based fallback parser for insulation specs without ruled tables.

Handles three common plain-text insulation schedule formats found in specs
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

Format C — CSI outline lettered-schedule (PHX73/MasterSpec HVAC pattern):
    3.13  PIPING INSULATION SCHEDULE, GENERAL
    D.  INDOOR PIPING INSULATION SCHEDULE
        1.  Non-Potable Water, Chilled Water, Condenser Water...:
            a.  Cellular Glass:  1-1/2 inches thick.
            b.  Mineral-Fiber, Preformed Pipe Insulation, Type I:  1-1/2 inch thick.
        2.  Refrigerant Piping:
            a.  Flexible Elastomeric:  1 inches thick.
    E.  OUTDOOR, ABOVEGROUND PIPING INSULATION SCHEDULE
        1.  Non-Potable Water, Chilled Water...:
            a.  Cellular Glass:  2 inches thick.
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
_SVC_LINE_RE = re.compile(r"^([A-Z])\.[ \t]+(.+?):\s*$")

# "1.  NPS 1 and Smaller:..."  or  "1.  All Pipe Sizes:..."
_SIZE_LINE_RE = re.compile(
    r"^\d+\.[ \t]+"
    r"(?P<size>(?:NPS\s+[\d\-/]+[\w\s]*|All\s+Pipe\s+Sizes?))",
    re.IGNORECASE,
)

# "a.  Mineral-Fiber ...:  1 inch thick."  or  "a.  Flexible Elastomeric:  1/2 inch thick."
# Accepts both colon and semicolon as separator (some specs use semicolons)
_THICK_A_RE = re.compile(
    r"^[a-z]\.[ \t]+(?P<type>.+?)[;:][ \t]+"
    r"(?P<thick>[\d\-/½¾¼⅜⅝⅞]+)\s+inch(?:es?)?\s+thick",
    re.IGNORECASE,
)

# ── format-B (UO2 paragraph style) ────────────────────────────────────────────

# "1.  Service (Domestic) Water Piping:"  — catches main service labels
# Optional trailing colon to handle lines without one
_SVC_B_RE = re.compile(
    r"^\d+\.[ \t]+(.+?(?:[Ww]ater|[Hh]eating|[Cc]hilled|[Rr]efrigera|[Cc]ondensate|[Ss]torm)[^:]{0,40}):?\s*$"
)

# "a.  Hot, 140F and under:"  — sub-service qualifier
_SUBSVC_RE = re.compile(r"^[a-z]\.[ \t]+(.+?)(?:\s*\([^)]*\))?\s*:\s*$")

# "1)  Sizes smaller than 1-1/2":  1""  or  "2)  Sizes 1-1/2" and larger:  1-1/2""
# Handles both:
#   "1)  Sizes smaller than 1-1/2": 1""  (inch mark after size and after thick)
#   "1)  Sizes smaller than 1-1/2: 1"    (no inch mark in size)
# After _clean the inch mark is ASCII 0x22.
_SIZE_THICK_B_RE = re.compile(
    r'^\d+\)[ \t]+(?:Sizes?\s+)?(?P<size>[^:]+?)"\s*:\s+(?P<thick>[\d\-/]+)"?\s*$'
    r'|^\d+\)[ \t]+(?:Sizes?\s+)?(?P<size2>[^:]+?):\s+(?P<thick2>[\d\-/]+)"?\s*$',
    re.IGNORECASE,
)

# ── format-C (PHX73-style lettered schedule headers) ──────────────────────────

# "D.  INDOOR PIPING INSULATION SCHEDULE"
# "E.  OUTDOOR, ABOVEGROUND PIPING INSULATION SCHEDULE"
# "F.  OUTDOOR, UNDERGROUND PIPING INSULATION SCHEDULE"
# Also handles headers without an explicit location keyword.
_SCHED_C_HEADER_RE = re.compile(
    r"^[A-Z]\.[ \t]+"
    r"(?P<loc>INDOOR|OUTDOOR(?:[,\s]+\w+)*|UNDERGROUND|EXPOSED)?"
    r"[^:]*(?:PIPING\s+)?INSULATION\s+SCHEDULE",
    re.IGNORECASE,
)

# End of section: "3.14" alone or "3.14  TITLE"
_NEXT_SECTION_C_RE = re.compile(
    r"^\s*\d+\.\d+(?:\s+[A-Z]|\s*$)",
)

# ── jacket outline schedule patterns ──────────────────────────────────────────

_JACKET_SCHED_HDR_RE = re.compile(r"FIELD[-\s]APPLIED JACKET SCHEDULE\b", re.IGNORECASE)

# "A.  Indoor, Field-Applied Jacket Schedule"
_JACKET_LOC_RE = re.compile(
    r"^[A-Z]\.\s{1,4}(?P<loc>Indoor|Outdoor)",
    re.IGNORECASE,
)

# "a.  PVC:  20 mils thick."  or  "b.  Aluminum, Corrugated:  0.020 inch thick"
_JACKET_THICK_RE = re.compile(
    r"^[a-z]\.\s{1,4}(?P<type>.+?):\s+"
    r"(?P<thick>[\d\.]+)\s+(?:mils?\s+thick|inch(?:es?)?\s+thick)",
    re.IGNORECASE,
)


# ── Hot/Cold row expander ─────────────────────────────────────────────────────

_HOT_COLD_RE = re.compile(
    r"\b(?:hot\s*[/&and]+\s*cold|cold\s*[/&and]+\s*hot)\b",
    re.IGNORECASE,
)


def _expand_hot_cold(row: dict) -> list[dict]:
    """If service name contains 'hot/cold' or 'hot and cold', return two rows.

    One row normalised to DOMESTIC HOT WATER, one to DOMESTIC COLD WATER.
    Otherwise return the original row unchanged (as a single-element list).
    """
    svc = row.get("Service", "")
    if not _HOT_COLD_RE.search(svc):
        return [row]
    hot = dict(row)
    cold = dict(row)
    hot["Service"] = "DOMESTIC HOT WATER"
    cold["Service"] = "DOMESTIC COLD WATER"
    return [hot, cold]


# ── public API ────────────────────────────────────────────────────────────────

def parse_text_pipe_insulation(
    page_texts: list[str],
    pdf_file: str = "",
) -> list[dict]:
    """Extract pipe insulation rows from plain text using regex state machine.

    Tries Format A (CSI numbered-list), Format B (UO2 paragraph style), and
    Format C (PHX73-style lettered schedule headers).  Returns the format that
    yields the most rows.

    Args:
        page_texts: Per-page text strings (from PyMuPDF / fitz).
        pdf_file:   Source filename tag.

    Returns:
        List of PipeInsulationRow dicts (normalised).
    """
    full_text = "\n".join(page_texts)
    rows_a = _parse_format_a(full_text, pdf_file)
    rows_b = _parse_format_b(full_text, pdf_file)
    rows_c = _parse_format_c(full_text, pdf_file)
    best = max([rows_a, rows_b, rows_c], key=len)
    result: list[dict] = []
    for r in best:
        # Expand Hot/Cold BEFORE normalization so the raw service name is visible
        for expanded in _expand_hot_cold(r):
            result.append(normalize_pipe_row(expanded))
    return result


def parse_pipe_insulation_text(page_texts, pdf_file: str = "") -> list[dict]:
    """Alias for parse_text_pipe_insulation; accepts list[str] or list[PageText]."""
    texts = [p.text if hasattr(p, "text") else p for p in page_texts]
    return parse_text_pipe_insulation(texts, pdf_file=pdf_file)


def parse_outline_jacket_schedule(
    page_texts: list[str],
    pdf_file: str = "",
) -> list[dict]:
    """Parse CSI outline-style field-applied jacket schedules (section 3.14 pattern).

    3.14  FIELD-APPLIED JACKET SCHEDULE
    A.  Indoor, Field-Applied Jacket Schedule
        3.  Piping, Non-potable water piping and Refrigerant
            a.  PVC:  20 mils thick.
            b.  Aluminum, Corrugated:  0.020 inch thick

    Returns JacketRule dicts (same schema as jacket_parser.parse_jacket_rules).
    """
    full_text = "\n".join(page_texts)
    rows: list[dict] = []
    in_jacket = False
    current_location = ""
    current_service = ""

    for stripped in _join_bullet_lines(full_text.splitlines()):
        if not stripped:
            continue

        # End of jacket schedule on new CSI section number
        if in_jacket and _NEXT_SECTION_C_RE.match(stripped):
            in_jacket = False
            continue

        # Jacket schedule start (guard prevents re-triggering on sub-items)
        if not in_jacket and _JACKET_SCHED_HDR_RE.search(stripped):
            in_jacket = True
            current_location = current_service = ""
            continue

        if not in_jacket:
            continue

        # Location header: "A.  Indoor, Field-Applied Jacket Schedule"
        m = _JACKET_LOC_RE.match(stripped)
        if m:
            loc = m.group("loc").strip()
            current_location = "Indoor" if loc.lower().startswith("indoor") else "Outdoor"
            current_service = ""
            continue

        # Numbered item: "3.  Piping, Non-potable water piping and Refrigerant"
        # Instructional items (1, 2) have no lettered sub-bullets → never produce output
        m = re.match(r"^\d+\.[ \t]+(.+)", stripped)
        if m:
            current_service = m.group(1).rstrip(": \t")
            continue

        # Lettered jacket material: "a.  PVC:  20 mils thick."
        m = _JACKET_THICK_RE.match(stripped)
        if m:
            rows.append({
                "Location": current_location,
                "Application": "Pipe",
                "Jacket_Type": m.group("type").strip(),
                "Jacket_Material": m.group("type").strip(),
                "Rule_Text": stripped,
                "Confidence": 0.90,
                "PDF_File": pdf_file,
            })

    return rows


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


# ── format-C parser ───────────────────────────────────────────────────────────

def _parse_format_c(text: str, pdf_file: str) -> list[dict]:
    """Parse Format C: PHX73 / MasterSpec HVAC outline-style schedules.

    D.  INDOOR PIPING INSULATION SCHEDULE
        1.  Non-Potable Water, Chilled Water...:
            a.  Cellular Glass:  1-1/2 inches thick.
    E.  OUTDOOR, ABOVEGROUND PIPING INSULATION SCHEDULE
        1.  Non-Potable Water...:
            a.  Cellular Glass:  2 inches thick.

    Location (Indoor / Outdoor - Aboveground / Outdoor - Underground) is
    stored in the Notes field of each row.
    """
    rows: list[dict] = []
    in_schedule = False
    current_location = ""
    current_service = ""
    pending_service = False  # True when numbered service line wrapped to next line

    for stripped in _join_bullet_lines(text.splitlines()):
        if not stripped:
            continue

        # End on a new CSI section number ("3.14" alone or "3.15  TITLE")
        if in_schedule and _NEXT_SECTION_C_RE.match(stripped):
            in_schedule = False
            current_location = current_service = ""
            pending_service = False
            continue

        # Lettered schedule header with location context
        m = _SCHED_C_HEADER_RE.match(stripped)
        if m:
            in_schedule = True
            loc_raw = m.group("loc") or ""
            loc = loc_raw.upper()
            if "UNDERGROUND" in loc:
                current_location = "Outdoor - Underground"
            elif "ABOVE" in loc or ("OUTDOOR" in loc and "ABOVE" in stripped.upper()):
                current_location = "Outdoor - Aboveground"
            elif "OUTDOOR" in loc:
                current_location = "Outdoor"
            elif "INDOOR" in loc:
                current_location = "Indoor"
            else:
                # Infer from the full stripped line
                su = stripped.upper()
                if "UNDERGROUND" in su:
                    current_location = "Outdoor - Underground"
                elif "OUTDOOR" in su or "ABOVEGROUND" in su:
                    current_location = "Outdoor"
                else:
                    current_location = "Indoor"
            current_service = ""
            pending_service = False
            continue

        if not in_schedule:
            continue

        # Service continuation: fitz often wraps long service names across lines
        if pending_service:
            if not re.match(r"^[a-zA-Z]\.\s", stripped) and not re.match(r"^\d+\.\s", stripped):
                current_service = (current_service + " " + stripped).rstrip(": \t")
                if stripped.rstrip().endswith(":"):
                    pending_service = False
                continue
            pending_service = False

        # Numbered service line: "1.  Non-Potable Water, Chilled Water...:"
        m = re.match(r"^\d+\.[ \t]+(.+)", stripped)
        if m:
            svc_text = m.group(1).rstrip(": \t")
            current_service = svc_text
            # Mark pending if line didn't end with colon (name may wrap)
            pending_service = not stripped.rstrip().endswith(":")
            continue

        # Lettered material/thickness: "a.  Cellular Glass:  1-1/2 inches thick."
        m = _THICK_A_RE.match(stripped)
        if m and current_service:
            rows.append({
                "Service": current_service,
                "Pipe_Size_Range": "All",
                "Thickness": _norm_thickness(m.group("thick")),
                "Insulation_Type": m.group("type").strip(),
                "Jacket_Required": "",
                "Notes": current_location,
                "PDF_File": pdf_file,
            })

    return rows
