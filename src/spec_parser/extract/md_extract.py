"""pymupdf4llm-based markdown extraction for PDF files.

Provides per-page and chunked extraction to avoid hangs on large PDFs.
Each pymupdf4llm call is wrapped in a 60-second timeout; if it hangs,
falls back to raw fitz text extraction.
<br> artifacts from pymupdf4llm are cleaned before returning.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from spec_parser.extract.md_table_parser import clean_markdown


# ── internal helpers ──────────────────────────────────────────────────────────

def _chunk_ranges(total: int, chunk_size: int) -> list[list[int]]:
    """Split page indices 0..total-1 into chunks of *chunk_size*."""
    chunks: list[list[int]] = []
    for start in range(0, total, chunk_size):
        chunks.append(list(range(start, min(start + chunk_size, total))))
    return chunks


def _fitz_fallback(pdf_path: str, pages: list[int] | None = None) -> str:
    """Fallback: raw fitz text extraction when pymupdf4llm hangs or errors."""
    import fitz
    doc = fitz.open(str(pdf_path))
    texts: list[str] = []
    for i in range(len(doc)):
        if pages is not None and i not in pages:
            continue
        texts.append(doc[i].get_text())
    doc.close()
    return "\n\n".join(texts)


def _to_markdown_with_timeout(pdf_path: str, pages: list[int], timeout: int = 60) -> str:
    """Call pymupdf4llm.to_markdown with a hard timeout.

    Returns cleaned markdown on success, or falls back to raw fitz text if
    the call exceeds *timeout* seconds or raises an exception.
    """
    import pymupdf4llm
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(pymupdf4llm.to_markdown, str(pdf_path), pages=pages)
            md = future.result(timeout=timeout)
            return clean_markdown(md)
    except (FuturesTimeout, Exception) as e:
        print(f"[WARN] pymupdf4llm timed out/failed (pages={pages}): {e}. Falling back to fitz.")
        return _fitz_fallback(pdf_path, pages)


# ── public API ────────────────────────────────────────────────────────────────

def extract_markdown(pdf_path: str, pages: list[int] | None = None, timeout: int = 60) -> str:
    """Extract full markdown string from *pdf_path*.

    For large PDFs (>20 pages) the extraction is done in chunks of 5 pages
    to avoid hangs, then joined with page-break markers. Each chunk is
    wrapped in a *timeout*-second deadline; hangs fall back to raw fitz text.

    Args:
        pdf_path: Path to the PDF.
        pages:    0-based page indices to extract. None = all pages.
        timeout:  Per-call timeout in seconds (default 60).

    Returns:
        Cleaned markdown string with <br> artifacts removed.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
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
        return _to_markdown_with_timeout(pdf_path, target_pages, timeout=timeout)

    # Large PDFs — extract in chunks to avoid hangs
    CHUNK = 5
    parts: list[str] = []
    for chunk in _chunk_ranges(len(target_pages), CHUNK):
        chunk_pages = [target_pages[i] for i in chunk]
        parts.append(_to_markdown_with_timeout(pdf_path, chunk_pages, timeout=timeout))

    return "\n\n".join(parts)


def extract_markdown_pages(pdf_path: str, timeout: int = 60) -> list[str]:
    """Extract per-page markdown strings from *pdf_path*.

    Returns a list where index i = cleaned markdown for page i+1 (1-based).
    Uses single-page extraction to maximize reliability. Each page call is
    wrapped in a *timeout*-second deadline; hangs fall back to raw fitz text.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    doc.close()

    pages_md: list[str] = []
    for i in range(total):
        pages_md.append(_to_markdown_with_timeout(pdf_path, [i], timeout=timeout))

    return pages_md
