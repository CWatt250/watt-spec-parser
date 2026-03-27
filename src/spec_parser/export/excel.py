from __future__ import annotations

import os
from dataclasses import asdict

import pandas as pd

from spec_parser.models.types import SourceSection
from spec_parser.export.schemas import (
    SOURCE_SECTIONS_COLUMNS,
    PIPE_INSULATION_COLUMNS,
    DUCT_INSULATION_COLUMNS,
    JACKET_RULES_COLUMNS,
    MASTER_COLUMNS,
)


# ── Source Sections (Phase 1 output) ─────────────────────────────────────────

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


# ── Full insulation export (all 4 sheets) ────────────────────────────────────

def _df_from_rows(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    """Build a DataFrame from dicts, ensuring all target columns are present."""
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns]


def _build_master(
    pipe_rows: list[dict],
    duct_rows: list[dict],
    jacket_rows: list[dict],
) -> pd.DataFrame:
    """Union pipe, duct, and jacket rows into a single MASTER sheet."""
    master_rows: list[dict] = []

    for r in pipe_rows:
        master_rows.append(
            {
                "PDF_File": r.get("PDF_File", ""),
                "Sheet": "Pipe_Insulation",
                "Service": r.get("Service", ""),
                "System": "",
                "Pipe_Size_Range": r.get("Pipe_Size_Range", ""),
                "Thickness": r.get("Thickness", ""),
                "Insulation_Type": r.get("Insulation_Type", ""),
                "Jacket_Required": r.get("Jacket_Required", ""),
                "Location": "",
                "Jacket_Type": "",
                "Jacket_Material": "",
                "Notes": r.get("Notes", ""),
            }
        )

    for r in duct_rows:
        thick = r.get("Exposed") or r.get("Outdoor") or r.get("Concealed") or ""
        master_rows.append(
            {
                "PDF_File": r.get("PDF_File", ""),
                "Sheet": "Duct_Insulation",
                "Service": "",
                "System": r.get("System", ""),
                "Pipe_Size_Range": "",
                "Thickness": thick,
                "Insulation_Type": r.get("Insulation_Type", ""),
                "Jacket_Required": r.get("Finish", ""),
                "Location": "",
                "Jacket_Type": "",
                "Jacket_Material": "",
                "Notes": r.get("Notes", ""),
            }
        )

    for r in jacket_rows:
        master_rows.append(
            {
                "PDF_File": r.get("PDF_File", ""),
                "Sheet": "Jacket_Rules",
                "Service": "",
                "System": "",
                "Pipe_Size_Range": "",
                "Thickness": "",
                "Insulation_Type": "",
                "Jacket_Required": r.get("Jacket_Type", ""),
                "Location": r.get("Location", ""),
                "Jacket_Type": r.get("Jacket_Type", ""),
                "Jacket_Material": r.get("Jacket_Material", ""),
                "Notes": r.get("Rule_Text", ""),
            }
        )

    if not master_rows:
        return pd.DataFrame(columns=MASTER_COLUMNS)
    return _df_from_rows(master_rows, MASTER_COLUMNS)


def export_insulation_xlsx(
    sections: list[SourceSection],
    pipe_rows: list[dict],
    duct_rows: list[dict],
    jacket_rows: list[dict],
    out_dir: str,
    filename: str = "Insulation Report.xlsx",
) -> str:
    """Write all 4 sheets (Pipe_Insulation, Duct_Insulation, Jacket_Rules, MASTER)
    plus Source_Sections into a single Excel workbook.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    df_sections = _df_from_rows(
        [
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
            for s in sections
        ],
        SOURCE_SECTIONS_COLUMNS,
    )
    df_pipe = _df_from_rows(pipe_rows, PIPE_INSULATION_COLUMNS)
    df_duct = _df_from_rows(duct_rows, DUCT_INSULATION_COLUMNS)
    df_jacket = _df_from_rows(jacket_rows, JACKET_RULES_COLUMNS)
    df_master = _build_master(pipe_rows, duct_rows, jacket_rows)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_sections.to_excel(writer, sheet_name="Source_Sections", index=False)
        df_pipe.to_excel(writer, sheet_name="Pipe_Insulation", index=False)
        df_duct.to_excel(writer, sheet_name="Duct_Insulation", index=False)
        df_jacket.to_excel(writer, sheet_name="Jacket_Rules", index=False)
        df_master.to_excel(writer, sheet_name="MASTER", index=False)

        # Auto-fit column widths
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value is not None),
                    default=8,
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    return out_path
