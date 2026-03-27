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

PIPE_INSULATION_COLUMNS = [
    "Service",
    "Pipe_Size_Range",
    "Thickness",
    "Insulation_Type",
    "Jacket_Required",
    "Notes",
    "PDF_File",
    "Page_Num",
]

DUCT_INSULATION_COLUMNS = [
    "System",
    "Thickness",
    "R_Value",
    "Finish",
    "Exposed",
    "Concealed",
    "Outdoor",
    "Insulation_Type",
    "Notes",
    "PDF_File",
    "Page_Num",
]

JACKET_RULES_COLUMNS = [
    "Jacket_Type",
    "Condition",
    "Service",
    "Rule",
    "Notes",
    "PDF_File",
    "Page_Num",
]

MASTER_COLUMNS = [
    "Row_Type",
    "PDF_File",
    "Page_Num",
    "Service_Or_System",
    "Pipe_Size_Range",
    "Thickness",
    "R_Value",
    "Insulation_Type",
    "Jacket_Required",
    "Finish",
    "Condition",
    "Notes",
]


def _pipe_to_master(row: dict) -> dict:
    return {
        "Row_Type": "PIPE",
        "PDF_File": row.get("PDF_File", ""),
        "Page_Num": row.get("Page_Num", ""),
        "Service_Or_System": row.get("Service", ""),
        "Pipe_Size_Range": row.get("Pipe_Size_Range", ""),
        "Thickness": row.get("Thickness", ""),
        "R_Value": "",
        "Insulation_Type": row.get("Insulation_Type", ""),
        "Jacket_Required": row.get("Jacket_Required", ""),
        "Finish": "",
        "Condition": "",
        "Notes": row.get("Notes", ""),
    }


def _duct_to_master(row: dict) -> dict:
    conditions = []
    if row.get("Exposed") == "Yes":
        conditions.append("Exposed")
    if row.get("Concealed") == "Yes":
        conditions.append("Concealed")
    if row.get("Outdoor") == "Yes":
        conditions.append("Outdoor")
    return {
        "Row_Type": "DUCT",
        "PDF_File": row.get("PDF_File", ""),
        "Page_Num": row.get("Page_Num", ""),
        "Service_Or_System": row.get("System", ""),
        "Pipe_Size_Range": "",
        "Thickness": row.get("Thickness", ""),
        "R_Value": row.get("R_Value", ""),
        "Insulation_Type": row.get("Insulation_Type", ""),
        "Jacket_Required": "",
        "Finish": row.get("Finish", ""),
        "Condition": ", ".join(conditions),
        "Notes": row.get("Notes", ""),
    }


def _jacket_to_master(row: dict) -> dict:
    return {
        "Row_Type": "JACKET",
        "PDF_File": row.get("PDF_File", ""),
        "Page_Num": row.get("Page_Num", ""),
        "Service_Or_System": row.get("Service", ""),
        "Pipe_Size_Range": "",
        "Thickness": "",
        "R_Value": "",
        "Insulation_Type": "",
        "Jacket_Required": row.get("Jacket_Type", ""),
        "Finish": "",
        "Condition": row.get("Condition", ""),
        "Notes": row.get("Rule", ""),
    }


def export_full_xlsx(
    pipe_rows: list[dict],
    duct_rows: list[dict],
    jacket_rows: list[dict],
    sections: list[SourceSection],
    out_dir: str,
    filename: str = "Insulation Schedule.xlsx",
) -> str:
    """Export all extraction results to a multi-sheet Excel workbook.

    Sheets:
        Pipe_Insulation  - structured pipe insulation rows
        Duct_Insulation  - structured duct insulation rows
        Jacket_Rules     - jacket/covering requirement rules
        MASTER           - all rows unified with Row_Type discriminator
        Source_Sections  - debug sheet with CSI section detection results
    """
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    # Build DataFrames
    df_pipe = pd.DataFrame(pipe_rows, columns=PIPE_INSULATION_COLUMNS) if pipe_rows else pd.DataFrame(columns=PIPE_INSULATION_COLUMNS)
    df_duct = pd.DataFrame(duct_rows, columns=DUCT_INSULATION_COLUMNS) if duct_rows else pd.DataFrame(columns=DUCT_INSULATION_COLUMNS)
    df_jacket = pd.DataFrame(jacket_rows, columns=JACKET_RULES_COLUMNS) if jacket_rows else pd.DataFrame(columns=JACKET_RULES_COLUMNS)

    master_rows = (
        [_pipe_to_master(r) for r in pipe_rows]
        + [_duct_to_master(r) for r in duct_rows]
        + [_jacket_to_master(r) for r in jacket_rows]
    )
    df_master = pd.DataFrame(master_rows, columns=MASTER_COLUMNS) if master_rows else pd.DataFrame(columns=MASTER_COLUMNS)

    # Source Sections debug sheet
    section_rows = []
    for s in sections:
        section_rows.append(
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
    df_sections = pd.DataFrame(section_rows, columns=SOURCE_SECTIONS_COLUMNS) if section_rows else pd.DataFrame(columns=SOURCE_SECTIONS_COLUMNS)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_pipe.to_excel(writer, sheet_name="Pipe_Insulation", index=False)
        df_duct.to_excel(writer, sheet_name="Duct_Insulation", index=False)
        df_jacket.to_excel(writer, sheet_name="Jacket_Rules", index=False)
        df_master.to_excel(writer, sheet_name="MASTER", index=False)
        df_sections.to_excel(writer, sheet_name="Source_Sections", index=False)

    return out_path


def export_source_sections_xlsx(sections: list[SourceSection], out_dir: str) -> str:
    """Legacy single-sheet export kept for backward compatibility with phase1 pipeline."""
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
