from __future__ import annotations

import re
from typing import Optional

from spec_parser.models.types import PageText, SourceSection


# Very conservative CSI-like patterns:
# - 6-digit with optional dot: 22 07 19, 220719, 22.07.19
# - often followed by a title line
# Strong header patterns only (Phase 1):
# Examples:
# - 230719 HVAC PIPING INSULATION
# - 23 07 19 HVAC PIPING INSULATION
# - 23.07.19 HVAC PIPING INSULATION
# - SECTION 23 07 19
# - SECTION 230719 - HVAC PIPING INSULATION
#
# Keep conservative: require CSI num; title optional when prefixed by SECTION.
SECTION_RE = re.compile(
    r"(?im)^\s*(?:SECTION\s+)?(?P<num>(?:\d{6}|\d{2}\s\d{2}\s\d{2}|\d{2}\.\d{2}\.\d{2}))\s*(?:[-–—]\s*)?(?P<title>[A-Z0-9][A-Z0-9\s\-/,&]{3,100})?\s*$"
)


def normalize_section_number(raw: str) -> str:
    raw = raw.strip()
    if re.fullmatch(r"\d{6}", raw):
        return f"{raw[0:2]} {raw[2:4]} {raw[4:6]}"
    raw = raw.replace(".", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw


def detect_source_sections(project_file: str, pages: list[PageText]) -> list[SourceSection]:
    """Detect candidate CSI sections and return SourceSection rows.

    Conservative Phase 1:
    - strong regex only
    - estimate page ranges by next detected header
    - retain raw header text + confidence + method

    If no sections detected, return a single unknown section covering the whole doc.
    """
    hits: list[dict] = []

    for p in pages:
        for m in SECTION_RE.finditer(p.text or ""):
            raw_num = (m.group("num") or "").strip()
            raw_title = ((m.group("title") or "").strip() or None)

            # If the line starts with SECTION and no title, keep it but lower confidence.
            line = (m.group(0) or "").strip()
            is_section_prefix = line.upper().startswith("SECTION")

            raw_header = (f"{raw_num} {raw_title or ''}").strip() if raw_num else line

            hits.append(
                {
                    "page_num": p.page_num,
                    "section_number": raw_num,
                    "normalized_section_number": normalize_section_number(raw_num) if raw_num else None,
                    "title": (raw_title or ""),
                    "raw_header_text": line,
                    "method": "exact_header_regex",
                    "confidence": 0.9 if raw_title else (0.7 if is_section_prefix else 0.6),
                    "notes": "Exact header match" if raw_title else "Low confidence title",
                }
            )

    hits.sort(key=lambda x: x["page_num"])

    if not hits:
        end_page = pages[-1].page_num if pages else 1
        return [
            SourceSection(
                project_file=project_file,
                raw_header_text=None,
                section_number=None,
                normalized_section_number=None,
                section_title=None,
                category=None,
                start_page=1,
                end_page=end_page,
                detection_method=None,
                confidence=0.0,
                relevance="unknown",
                parse_notes="No strong CSI section headers detected. Manual review required.",
                source_text_excerpt=None,
            )
        ]

    last_page = pages[-1].page_num if pages else hits[-1]["page_num"]

    sections: list[SourceSection] = []
    for i, h in enumerate(hits):
        start_page = h["page_num"]
        next_start = hits[i + 1]["page_num"] if i + 1 < len(hits) else (last_page + 1)
        end_page = max(start_page, next_start - 1)

        sections.append(
            SourceSection(
                project_file=project_file,
                raw_header_text=h["raw_header_text"],
                section_number=h["section_number"],
                normalized_section_number=h["normalized_section_number"],
                section_title=h["title"],
                category=None,
                start_page=start_page,
                end_page=end_page,
                detection_method=h["method"],
                confidence=float(h["confidence"]),
                relevance="unknown",
                parse_notes=h.get("notes", "Exact header match"),
                source_text_excerpt=None,
            )
        )

    return sections
