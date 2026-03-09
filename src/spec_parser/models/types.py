from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class PageText:
    page_num: int  # 1-based
    text: str


RelevanceLevel = Literal["high", "medium", "low", "unknown"]


@dataclass(frozen=True)
class SourceSection:
    project_file: str

    # Raw and normalized header detection
    raw_header_text: Optional[str]
    section_number: Optional[str]                # as detected
    normalized_section_number: Optional[str]     # normalized "23 07 19" style
    section_title: Optional[str]

    # Classification placeholders (Phase 2+)
    category: Optional[str]  # e.g., "Pipe Insulation", "Duct Insulation", "Equipment", "Other"

    # Location
    start_page: int
    end_page: int

    # Detection metadata
    detection_method: Optional[str]  # e.g., "exact_header_regex"
    confidence: float                # 0.0 - 1.0

    relevance: RelevanceLevel
    parse_notes: str

    # For auditability: optional excerpt to help spot-check without opening PDF
    source_text_excerpt: Optional[str] = None
