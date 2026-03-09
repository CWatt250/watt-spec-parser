from __future__ import annotations

from dataclasses import replace

from spec_parser.models.types import SourceSection


# Lightweight mapping (Phase 1/2): normalized section number -> category label
SECTION_CATEGORY_MAP: dict[str, str] = {
    "23 07 19": "HVAC_PIPING_INSULATION",
    "23 07 13": "DUCT_INSULATION",
    "22 07 19": "PLUMBING_PIPING_INSULATION",
}


def classify_sections(sections: list[SourceSection]) -> list[SourceSection]:
    """Attach a conservative category label to SourceSection.category.

    Phase 2 uses this for relevance marking + scope filtering.
    """
    out: list[SourceSection] = []
    for s in sections:
        n = (s.normalized_section_number or "").strip()
        cat = SECTION_CATEGORY_MAP.get(n)
        out.append(replace(s, category=cat or s.category))
    return out
