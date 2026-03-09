from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Page:
    """A single extracted page.

    Notes:
    - `text` is normalized text by default (Phase 1 pipeline can also keep raw previews separately).
    - Keep this lightweight; any heavy analysis belongs in analysis_results.
    """

    page_num: int  # 1-based
    text: str


@dataclass(frozen=True)
class Section:
    """A detected spec section (CSI-ish)."""

    section_number: Optional[str]
    normalized_section_number: Optional[str]
    title: Optional[str]

    start_page: int
    end_page: int

    # Full section text (Phase 1: optional; Phase 2+ may populate)
    text: str = ""

    # Phase 2+ classification / traceability
    category: Optional[str] = None
    parse_notes: str = ""

    detection_method: Optional[str] = None
    confidence: float = 0.0

    # Raw header text as seen in the PDF
    raw_header_text: Optional[str] = None


@dataclass
class Document:
    """Central document model for the spec parser.

    All analysis modules should take a Document instance.

    Designed to be conservative + auditable:
    - preserve metadata and warnings
    - keep detection method + confidence
    - keep raw header text when available
    """

    file_name: str
    total_pages: int

    pages: list[Page] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    analysis_results: dict[str, Any] = field(default_factory=dict)

    # Phase 2+ convenience fields (avoid refactors later)
    detected_systems: list[str] = field(default_factory=list)
    keyword_hits: list[Any] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
