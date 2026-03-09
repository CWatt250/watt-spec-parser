from __future__ import annotations

import fitz  # PyMuPDF

from spec_parser.models.types import PageText


def extract_pages(pdf_path: str) -> list[PageText]:
    """Extract per-page text from a PDF using PyMuPDF.

    Conservative behavior:
    - never guesses; returns empty string for pages with no extractable text
    - keeps page boundaries for later section detection
    """
    doc = fitz.open(pdf_path)
    pages: list[PageText] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text("text") or ""
        pages.append(PageText(page_num=i + 1, text=text))
    return pages
