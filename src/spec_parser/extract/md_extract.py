"""pymupdf4llm-based markdown extraction for PDF files.

Provides per-page and chunked extraction to avoid hangs on large PDFs.
<br> artifacts from pymupdf4llm are cleaned before returning.
"""

from __future__ import annotations

import re

from spec_parser.extract.md_table_parser import clean_markdown


# ── internal helpers ──────────────────────────────────────────────────────────

def _chunk_ranges(total: int, chunk_size: int) -> list[list[int]]:
    """Split page indices 0..total-1 into chunks of *chunk_size*."""
    chunks: list[list[int]] = []
    for start in range(0, total, chunk_size):
        chunks.append(list(range(start, min(start + chunk_size, total))))
    return chunks


# ── public API ────────────────────────────────────────────────────────────────

def extract_markdown(pdf_path: str, pages: list[int] | None = None) -> str:
    """Extract full markdown string from *pdf_path*.

    For large PDFs (>20 pages) the extraction is done in chunks of 5 pages
    to avoid hangs, then joined with page-break markers.

    Args:
        pdf_path: Path to the PDF.
        pages:    0-based page indices to extract. None = all pages.

    Returns:
        Cleaned markdown string with <br> artifacts removed.
    """
    import pymupdf4llm
    import fitz

    doc = fitz.open(pdf_path)
    total = doc.page_count
    doc.close()

    if pages is None:
        target_pages = list(range(total))
    else:
        target_pages = [p for p in pages if 0 <= p < total]

    if not target_pages:
        return ""

    # Small PDFs — extract in one shot
    if len(target_pages) <= 20:
        md = pymupdf4llm.to_markdown(pdf_path, pages=target_pages)
        return clean_markdown(md)

    # Large PDFs — extract in chunks to avoid hangs
    CHUNK = 5
    parts: list[str] = []
    for chunk in _chunk_ranges(len(target_pages), CHUNK):
        chunk_pages = [target_pages[i] for i in chunk]
        md_chunk = pymupdf4llm.to_markdown(pdf_path, pages=chunk_pages)
        parts.append(md_chunk)

    return clean_markdown("\n\n".join(parts))


def extract_markdown_pages(pdf_path: str) -> list[str]:
    """Extract per-page markdown strings from *pdf_path*.

    Returns a list where index i = cleaned markdown for page i+1 (1-based).
    Uses single-page extraction to maximize reliability.
    """
    import pymupdf4llm
    import fitz

    doc = fitz.open(pdf_path)
    total = doc.page_count
    doc.close()

    pages_md: list[str] = []
    for i in range(total):
        try:
            md = pymupdf4llm.to_markdown(pdf_path, pages=[i])
            pages_md.append(clean_markdown(md))
        except Exception:
            pages_md.append("")

    return pages_md
