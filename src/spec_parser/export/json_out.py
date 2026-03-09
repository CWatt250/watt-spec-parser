from __future__ import annotations

import json
import os
from dataclasses import asdict

from spec_parser.models.types import SourceSection


def export_source_sections_json(sections: list[SourceSection], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "source_sections.json")

    # Ensure stable keys are always present (even if values are null/empty)
    payload = []
    for s in sections:
        d = asdict(s)
        payload.append(
            {
                "project_file": d.get("project_file"),
                "section_number": d.get("section_number"),
                "normalized_section_number": d.get("normalized_section_number"),
                "title": d.get("section_title"),
                "category": d.get("category"),
                "start_page": d.get("start_page"),
                "end_page": d.get("end_page"),
                "detection_method": d.get("detection_method"),
                "confidence": d.get("confidence"),
                "raw_header_text": d.get("raw_header_text"),
                "parse_notes": d.get("parse_notes"),
                # Keep any extra fields for forward-compat
                "relevance": d.get("relevance"),
                "source_text_excerpt": d.get("source_text_excerpt"),
            }
        )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return out_path
