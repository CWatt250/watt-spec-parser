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
    include_page_text: bool = False,
) -> list[dict]:
    """Extract tables from a PDF.

    Args:
        pdf_path: Path to the PDF file.
        page_numbers: 1-based page numbers to extract from. None = all pages.
        include_page_text: If True, include raw page text in each result dict
                           under the key ``page_text`` — useful for inferring
                           material type from surrounding headings.

    Returns:
        List of dicts: {page_num, table_index, rows: [[cell_str, ...]]}
        and optionally page_text.
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
            page_text = page.extract_text() or "" if include_page_text else ""
            found_tables = page.find_tables()
            raw_tables = page.extract_tables()
            for t_idx, raw_table in enumerate(raw_tables or []):
                # Normalize: replace None with "", strip whitespace
                rows = [
                    [
                        (cell or "").replace("\n", " ").strip()
                        for cell in row
                    ]
                    for row in raw_table
                ]
                # Skip empty tables
                if not any(any(c for c in row) for row in rows):
                    continue
                entry: dict = {
                    "page_num": page_num,
                    "table_index": t_idx,
                    "rows": rows,
                }
                if include_page_text:
                    # Extract text ABOVE this specific table using its bbox
                    # so parsers can infer material from the nearest heading.
                    above_text = page_text  # fallback: full page
                    if t_idx < len(found_tables):
                        tbl_bbox = found_tables[t_idx].bbox  # (x0, top, x1, bottom)
                        tbl_top = tbl_bbox[1]
                        try:
                            cropped = page.crop((0, 0, page.width, tbl_top))
                            above_text = cropped.extract_text() or ""
                        except Exception:
                            above_text = page_text
                    entry["page_text"] = above_text
                results.append(entry)

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
