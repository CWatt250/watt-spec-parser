"""Excel output schemas (column ordering per sheet).

Column names must match the dict keys produced by the parsers.
"""

from __future__ import annotations


# ── Source Sections ───────────────────────────────────────────────────────────

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


# ── Pipe Insulation ───────────────────────────────────────────────────────────

PIPE_INSULATION_COLUMNS = [
    "PDF_File",
    "Service",
    "Pipe_Size_Range",
    "Thickness",
    "Insulation_Type",
    "Jacket_Required",
    "Notes",
]


# ── Duct Insulation ───────────────────────────────────────────────────────────

DUCT_INSULATION_COLUMNS = [
    "PDF_File",
    "System",
    "Exposed",
    "Concealed",
    "Outdoor",
    "Insulation_Type",
    "Finish",
    "Notes",
]


# ── Jacket Rules ──────────────────────────────────────────────────────────────

JACKET_RULES_COLUMNS = [
    "PDF_File",
    "Location",
    "Application",
    "Jacket_Type",
    "Jacket_Material",
    "Rule_Text",
    "Confidence",
]


# ── MASTER (union of all parse rows) ─────────────────────────────────────────

MASTER_COLUMNS = [
    "PDF_File",
    "Sheet",          # source sheet name ("Pipe_Insulation" | "Duct_Insulation" | "Jacket_Rules")
    "Service",
    "System",
    "Pipe_Size_Range",
    "Thickness",
    "Insulation_Type",
    "Jacket_Required",
    "Location",
    "Jacket_Type",
    "Jacket_Material",
    "Notes",
]
