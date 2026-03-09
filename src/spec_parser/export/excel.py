from __future__ import annotations

import os
from dataclasses import asdict

import pandas as pd

from spec_parser.models.types import SourceSection


SOURCE_SECTIONS_COLUMNS = [
    "Project File",
    "Raw Header Text",
    "Section Number",
    "Normalized Section Number",
    "Section Title",
    "Category",
    "Start Page",
    "End Page",
    "Detection Method",
    "Confidence",
    "Relevance Level",
    "Parse Notes",
]


def export_source_sections_xlsx(sections: list[SourceSection], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Source Sections.xlsx")

    rows = []
    for s in sections:
        rows.append(
            {
                "Project File": s.project_file,
                "Raw Header Text": s.raw_header_text or "",
                "Section Number": s.section_number or "",
                "Normalized Section Number": s.normalized_section_number or "",
                "Section Title": s.section_title or "",
                "Category": s.category or "",
                "Start Page": s.start_page,
                "End Page": s.end_page,
                "Detection Method": s.detection_method or "",
                "Confidence": s.confidence,
                "Relevance Level": s.relevance,
                "Parse Notes": s.parse_notes,
            }
        )

    df = pd.DataFrame(rows, columns=SOURCE_SECTIONS_COLUMNS)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Source Sections", index=False)

    return out_path
