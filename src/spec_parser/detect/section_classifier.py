from __future__ import annotations

from dataclasses import replace

from spec_parser.models.types import SourceSection


import re

# Conservative mapping: normalized section number -> category label
SECTION_CATEGORY_MAP: dict[str, str] = {
    "23 07 19": "HVAC_PIPING_INSULATION",
    "23 07 13": "DUCT_INSULATION",
    "22 07 19": "PLUMBING_PIPING_INSULATION",
    "22 07 00": "PLUMBING_INSULATION",
    "23 07 00": "MECHANICAL_INSULATION",
    "23 05 53": "HVAC_PIPING_IDENTIFICATION",
    "22 05 53": "PLUMBING_PIPING_IDENTIFICATION",
}

# Firestopping related patterns (very conservative)
FIRESTOPPING_SECTION_RE = re.compile(r"^07\s?84\s?\d{2}$")


def classify_sections(sections: list[SourceSection]) -> list[SourceSection]:
    """Attach a conservative category label to SourceSection.category.

    Rules:
    - Prefer explicit normalized section number mapping
    - Detect a small set of firestopping-related sections via strict pattern
    """
    out: list[SourceSection] = []
    for s in sections:
        n = (s.normalized_section_number or "").strip()
        cat = SECTION_CATEGORY_MAP.get(n)
        if not cat and n and FIRESTOPPING_SECTION_RE.match(n):
            cat = "FIRESTOPPING_RELATED"
        out.append(replace(s, category=cat or s.category))
    return out
