"""Jacket rules extractor.

Scans prose text for jacket (cladding/cover) requirements for piping and
ductwork. Context-aware: extracts indoor, outdoor, and concealed rules
separately based on surrounding section language.

Target schema:
  Location        - "Indoor", "Outdoor - Rigid", "Outdoor - Flexible",
                    "Exterior Duct", "Mechanical Room", "Underground", etc.
  Application     - "Pipe" | "Duct" | "Equipment"
  Jacket_Type     - e.g. "PVC", "Aluminum", "Stainless Steel", "NPJ"
  Jacket_Material - more specific material description
  Rule_Text       - verbatim sentence(s) from spec
  Confidence      - 0.0–1.0
  PDF_File        - source filename tag
"""

from __future__ import annotations

import re


# ── pattern library ───────────────────────────────────────────────────────────

# Each entry: (location_label, application, jacket_type, pattern)
_PIPE_JACKET_PATTERNS: list[tuple[str, str, str, re.Pattern]] = [
    (
        "Mechanical Room / Finished Space",
        "Pipe",
        "PVC",
        re.compile(
            r"pipe\s+exposed\s+in\s+mechanical\s+equipment\s+rooms?|"
            r"in\s+mechanical\s+equipment\s+rooms?\s+or\s+in\s+finished\s+spaces?[^.]*"
            r"(?:pvc|zeston|aluminum|stainless)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Indoor - Mechanical Room",
        "Pipe",
        "PVC",
        re.compile(
            r"For\s+Interior\s+Applications[\s\S]{0,60}?Mechanical\s+Rooms?",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor - Rigid Pipe",
        "Pipe",
        "Aluminum",
        re.compile(
            r"For\s+Exterior\s+Applications[\s\S]{0,20}?Rigid\s+Pip",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor - Flexible Pipe",
        "Pipe",
        "NPJ",
        re.compile(
            r"(?:Factory\s+)?Applied\s+Jackets[\s\S]{0,30}?Flexible\s+Pip",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor",
        "Pipe",
        "Aluminum or Stainless Steel",
        re.compile(
            r"For\s+exterior\s+applications?:?\s*Provide\s+weather\s+protection",
            re.IGNORECASE,
        ),
    ),
    (
        "Underground",
        "Pipe",
        "Per Manufacturer",
        re.compile(
            r"for\s+underground\s+installations?",
            re.IGNORECASE,
        ),
    ),
    # ── expanded patterns ─────────────────────────────────────────────────────
    (
        "Indoor - Standard",
        "Pipe",
        "ASJ",
        re.compile(
            r"all[\s-]*service\s+jacket|(?<!\w)ASJ(?!\w)",
            re.IGNORECASE,
        ),
    ),
    (
        "Indoor - Exposed",
        "Pipe",
        "PVC",
        re.compile(
            r"(?:install|provide|apply)\s+(?:a\s+)?(?:fitted\s+)?PVC\s+(?:cover|jacket|lap|sleeve)",
            re.IGNORECASE,
        ),
    ),
    (
        "Indoor - Exposed",
        "Pipe",
        "Canvas / Glass Cloth",
        re.compile(
            r"canvas\s+jacket|glass[\s-]cloth\s+jacket|fiberglass\s+cloth\s+jacket"
            r"|lagging\s+cloth",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor",
        "Pipe",
        "Aluminum Jacket",
        re.compile(
            r"install\s+aluminum\s+jacket|aluminum\s+jacket\s+with\s+all\s+joints"
            r"|apply\s+(?:a\s+)?(?:corrugated\s+)?aluminum\s+jacket",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor",
        "Pipe",
        "Weather Barrier",
        re.compile(
            r"weather[\s-]+(?:barrier|protection)\s+jacket"
            r"|weatherproof\s+jacket"
            r"|weather[\s-]+resistant\s+(?:jacket|finish|coating)",
            re.IGNORECASE,
        ),
    ),
    (
        "Cold Service - Indoor",
        "Pipe",
        "Vapor Barrier",
        re.compile(
            r"vapor[\s-]+(?:barrier|retarder)\s+(?:jacket|mastic|wrap|membrane)"
            r"|VB\s+jacket"
            r"|install\s+vapor\s+barriers?\s+on\s+insulated\s+pipe",
            re.IGNORECASE,
        ),
    ),
    (
        "General",
        "Pipe",
        "Mastic / Protective Coating",
        re.compile(
            r"apply\s+(?:two\s+coats?\s+of\s+)?(?:insulation\s+manufacturer.s\s+)?"
            r"recommended\s+protective\s+(?:coating|mastic)"
            r"|elastomeric\s+mastic|breather\s+mastic"
            r"|vapor[\s-]+barrier\s+mastic",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor",
        "Pipe",
        "Metal Jacket",
        re.compile(
            r"finish\s+exposed\s+surfaces\s+with\s+a\s+metal\s+jacket"
            r"|metal\s+jacket\s+is\s+indicated",
            re.IGNORECASE,
        ),
    ),
    (
        "Outdoor",
        "Pipe",
        "Field-Applied Jacket",
        re.compile(
            r"field[\s-]+applied\s+jacket\s+schedule"
            r"|outdoor[,\s]+field[\s-]+applied\s+(?:vapor\s+barrier\s+and\s+)?jacket",
            re.IGNORECASE,
        ),
    ),
]

_DUCT_JACKET_PATTERNS: list[tuple[str, str, str, re.Pattern]] = [
    (
        "Outdoor - Duct",
        "Duct",
        "Stainless Steel",
        re.compile(
            r"stainless\s+steel\s+jacket[^.]*(?:duct|exterior)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Outdoor - Duct",
        "Duct",
        "Aluminum",
        re.compile(
            r"aluminum\s+jacket[^.]*(?:duct|exterior)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Exterior - Duct",
        "Duct",
        "Weather-Proof Jacket",
        re.compile(
            r"for\s+exterior\s+(?:vapor\s+)?duct\s+applications?[^.]*weather(?:proof|-proof)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Exterior - Duct",
        "Duct",
        "Weather-Proof Jacket",
        re.compile(
            r"for\s+exterior\s+applications?[^.]*provide\s+insulation\s+with\s+a\s+weather\s+protection\s+jacket",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    # ── expanded duct patterns ────────────────────────────────────────────────
    (
        "Indoor - Duct",
        "Duct",
        "FSK / ASJ",
        re.compile(
            r"(?:FSK|foil[\s-]+scrim[\s-]+kraft|all[\s-]+service\s+jacket)[^.]{0,60}(?:duct|facing)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Outdoor - Duct",
        "Duct",
        "Aluminum Jacket (ALJ)",
        re.compile(
            r"Type\s+ALJ\s+jacket|aluminum\s+jacket[^.]{0,40}duct",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Outdoor - Duct",
        "Duct",
        "UV-Resistant Finish",
        re.compile(
            r"UV[\s-]+resistant\s+(?:paint|finish|coating)[^.]{0,40}(?:duct|exterior|outside)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
]

_ALL_PATTERNS = _PIPE_JACKET_PATTERNS + _DUCT_JACKET_PATTERNS


# ── sentence extractor ────────────────────────────────────────────────────────

def _extract_sentences(text: str, match: re.Match, context_chars: int = 300) -> str:
    """Return the sentence(s) surrounding a regex match."""
    start = max(0, match.start() - 50)
    end = min(len(text), match.end() + context_chars)
    snippet = text[start:end]
    # Trim to complete sentences
    lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
    return " ".join(lines[:5])


# ── public API ────────────────────────────────────────────────────────────────

def parse_jacket_rules(
    page_texts: list[str],
    pdf_file: str = "",
) -> list[dict]:
    """Scan prose text for jacket requirements.

    Args:
        page_texts: List of per-page text strings (already extracted).
        pdf_file: Source filename tag.

    Returns:
        List of JacketRule dicts.
    """
    full_text = "\n".join(page_texts)
    seen: set[tuple[str, str, str]] = set()
    rows_out: list[dict] = []

    for location, application, jacket_type, pattern in _ALL_PATTERNS:
        for m in pattern.finditer(full_text):
            key = (location, application, jacket_type)
            if key in seen:
                continue
            seen.add(key)

            rule_text = _extract_sentences(full_text, m)

            # Resolve jacket material detail
            snippet = full_text[m.start(): m.end() + 200].lower()
            if "pvc" in snippet or "zeston" in snippet:
                material = "PVC Plastic (e.g. Zeston 2000)"
            elif "stainless steel" in snippet:
                material = "Type 304 Stainless Steel, 0.010\" min"
            elif "aluminum" in snippet:
                material = 'Aluminum, 0.016" min'
            elif "npj" in snippet or "non-metallic polymeric" in snippet or "k-flex titan" in snippet:
                material = "Non-Metallic Polymeric Flexible (K-Flex Titan)"
            else:
                material = jacket_type

            rows_out.append(
                {
                    "Location": location,
                    "Application": application,
                    "Jacket_Type": jacket_type,
                    "Jacket_Material": material,
                    "Rule_Text": rule_text[:400],
                    "Confidence": 0.85,
                    "PDF_File": pdf_file,
                }
            )

    return rows_out


def parse_jacket_rules_from_pdf(
    pdf_path: str,
    pdf_file: str = "",
) -> list[dict]:
    """Convenience wrapper: open PDF with PyMuPDF (fitz) and extract jacket rules.

    Uses fitz rather than pdfplumber because fitz preserves word spacing and
    dash characters correctly in this class of PDFs.
    """
    import fitz

    page_texts: list[str] = []
    doc = fitz.open(pdf_path)
    for i in range(doc.page_count):
        page_texts.append(doc.load_page(i).get_text("text") or "")

    return parse_jacket_rules(page_texts, pdf_file=pdf_file or pdf_path)
