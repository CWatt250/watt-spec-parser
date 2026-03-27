"""Full extraction pipeline with multi-file support and MASTER sheet accumulation.

Runs table extraction + parsing (pipe, duct, jacket) on one or more PDFs.
Each row is tagged with PDF_File. Accumulates into MASTER lists.

Usage:
    from spec_parser.pipeline_full import run_full_pipeline, run_directory

    # Single file
    result = run_full_pipeline("path/to/spec.pdf")

    # Directory of PDFs
    result = run_directory("path/to/specs/")
"""

from __future__ import annotations

import os
from pathlib import Path

from spec_parser.extract.pdf_text import extract_pages
from spec_parser.extract.table_extract import extract_tables_from_pdf
from spec_parser.parse.pipe_parser import parse_pipe_tables
from spec_parser.parse.duct_parser import parse_duct_tables
from spec_parser.parse.jacket_parser import extract_jacket_rules


def run_full_pipeline(pdf_path: str) -> dict:
    """Run full extraction on a single PDF.

    Returns a dict with keys:
        pipe_rows   - list of pipe insulation dicts
        duct_rows   - list of duct insulation dicts
        jacket_rows - list of jacket rule dicts
        pdf_file    - basename of the PDF
        page_count  - total pages extracted
        warnings    - list of warning strings
    """
    pdf_file = os.path.basename(pdf_path)
    warnings: list[str] = []

    # 1. Extract raw pages for jacket text scanning
    pages = extract_pages(pdf_path)
    page_count = len(pages)

    if page_count == 0:
        warnings.append(f"{pdf_file}: No pages extracted")
        return {
            "pipe_rows": [],
            "duct_rows": [],
            "jacket_rows": [],
            "pdf_file": pdf_file,
            "page_count": 0,
            "warnings": warnings,
        }

    avg_chars = sum(len(p.text or "") for p in pages) / max(1, page_count)
    if avg_chars < 100:
        warnings.append(f"{pdf_file}: Very low text density ({avg_chars:.0f} chars/page) — may be scanned")

    # 2. Table extraction — scan all pages but focus on likely schedule pages
    # Try pages 10-20 first; fall back to all pages if nothing found.
    schedule_pages = list(range(10, min(page_count + 1, 21)))
    tables = extract_tables_from_pdf(pdf_path, page_numbers=schedule_pages, include_page_text=True)

    if not tables:
        tables = extract_tables_from_pdf(pdf_path, include_page_text=True)

    if not tables:
        warnings.append(f"{pdf_file}: No tables found")

    # 3. Parse tables
    pipe_rows = parse_pipe_tables(tables, pdf_file=pdf_file)
    duct_rows = parse_duct_tables(tables, pdf_file=pdf_file)

    if not pipe_rows:
        warnings.append(f"{pdf_file}: No pipe insulation rows extracted")
    if not duct_rows:
        warnings.append(f"{pdf_file}: No duct insulation rows extracted")

    # 4. Jacket rules from raw text
    page_texts = [p.text or "" for p in pages]
    jacket_rows = extract_jacket_rules(page_texts, pdf_file=pdf_file)

    return {
        "pipe_rows": pipe_rows,
        "duct_rows": duct_rows,
        "jacket_rows": jacket_rows,
        "pdf_file": pdf_file,
        "page_count": page_count,
        "warnings": warnings,
    }


def run_directory(
    directory: str,
    recursive: bool = False,
    glob_pattern: str = "*.pdf",
) -> dict:
    """Run full extraction on all PDFs in a directory.

    Returns a dict with accumulated MASTER lists:
        master_pipe    - all pipe rows across all PDFs
        master_duct    - all duct rows across all PDFs
        master_jacket  - all jacket rows across all PDFs
        per_file       - list of per-file result dicts
        all_warnings   - flattened list of all warnings
    """
    base = Path(directory)
    if recursive:
        pdf_paths = sorted(base.rglob(glob_pattern))
    else:
        pdf_paths = sorted(base.glob(glob_pattern))

    master_pipe: list[dict] = []
    master_duct: list[dict] = []
    master_jacket: list[dict] = []
    per_file: list[dict] = []
    all_warnings: list[str] = []

    for pdf_path in pdf_paths:
        result = run_full_pipeline(str(pdf_path))
        master_pipe.extend(result["pipe_rows"])
        master_duct.extend(result["duct_rows"])
        master_jacket.extend(result["jacket_rows"])
        per_file.append(result)
        all_warnings.extend(result["warnings"])

    return {
        "master_pipe": master_pipe,
        "master_duct": master_duct,
        "master_jacket": master_jacket,
        "per_file": per_file,
        "all_warnings": all_warnings,
    }
