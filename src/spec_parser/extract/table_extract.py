"""Table extraction from PDFs using pdfplumber.

Pulls structured table data from schedule pages (typically pages 13-15 in
HVAC insulation specs). Returns raw cell data for downstream parsers.
"""

from __future__ import annotations

from typing import Optional

import pdfplumber


def extract_tables_from_pdf(
    pdf_path: str,
    page_numbers: Optional[list[int]] = None,
) -> list[dict]:
    """Extract tables from a PDF.

    Args:
        pdf_path: Path to the PDF file.
        page_numbers: 1-based page numbers to extract from. None = all pages.

    Returns:
        List of dicts: {page_num, table_index, rows: [[cell_str, ...]]}
        Cells are strings (None replaced with "").
    """
    results: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        targets = page_numbers if page_numbers else list(range(1, total + 1))

        for page_num in targets:
            if page_num < 1 or page_num > total:
                continue
            page = pdf.pages[page_num - 1]
            table_objects = page.find_tables()
            raw_tables = page.extract_tables()
            full_page_text = page.extract_text() or ""

            for t_idx, (raw_table, tbl_obj) in enumerate(
                zip(raw_tables or [], table_objects or [])
            ):
                # Normalize cells
                rows = [
                    [
                        (cell or "").replace("\n", " ").strip()
                        for cell in row
                    ]
                    for row in raw_table
                ]
                if not any(any(c for c in row) for row in rows):
                    continue

                # Extract text above the table (up to 200 pts above bbox top)
                bbox = tbl_obj.bbox  # (x0, top, x1, bottom)
                above_top = max(0, bbox[1] - 200)
                context_region = page.within_bbox((0, above_top, page.width, bbox[1]))
                pre_table_text = (context_region.extract_text() or "").strip()

                results.append(
                    {
                        "page_num": page_num,
                        "table_index": t_idx,
                        "rows": rows,
                        "page_text": full_page_text,
                        "pre_table_text": pre_table_text,
                    }
                )

    return results


def extract_schedule_tables(pdf_path: str) -> list[dict]:
    """Extract tables from the schedule section pages (13-15) of an insulation spec.

    Falls back to scanning all pages if none found on pages 13-15.
    """
    schedule_pages = [13, 14, 15]
    tables = extract_tables_from_pdf(pdf_path, page_numbers=schedule_pages)

    if not tables:
        # Broader scan: pages 10-16
        tables = extract_tables_from_pdf(pdf_path, page_numbers=list(range(10, 17)))

    if not tables:
        # Last resort: all pages
        tables = extract_tables_from_pdf(pdf_path)

    return tables
