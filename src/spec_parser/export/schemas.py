"""Excel output schemas (column sets).

These are used by the Excel exporter when we start emitting additional sheets.
Phase 1 only emits Source Sections, but defining schemas now prevents churn later.
"""

from __future__ import annotations


PIPE_INSULATION_COLUMNS = [
    "System",
    "Material",
    "Thickness",
    "Service",
    "Location",
    "Section",
    "Source Text",
    "Confidence",
]


DUCT_INSULATION_COLUMNS = [
    "Duct Type",
    "Material",
    "Thickness",
    "R Value",
    "Jacket",
    "Section",
    "Source Text",
]


SCOPE_GAP_FLAGS_COLUMNS = [
    "Category",
    "Trigger",
    "Section",
    "Source Text",
    "Confidence",
]


INSULATION_SUMMARY_COLUMNS = [
    "System",
    "Material",
    "Typical Thickness",
    "Notes",
    "Section",
    "Confidence",
]
