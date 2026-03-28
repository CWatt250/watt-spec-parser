"""Markdown table parser for pymupdf4llm-extracted content.

Takes markdown text produced by pymupdf4llm.to_markdown() and parses all
markdown tables (lines starting with '|') into list-of-dicts format
compatible with pipe_parser and duct_parser.

Also cleans <br> artifacts introduced by pymupdf4llm:
  - "sys-<br>tems"  → "systems"   (hyphen + br = word continuation)
  - "water<br>supply" → "water supply"  (no hyphen = space)
  - "1-1/2<br>"     → "1-1/2"    (trailing br = strip)
"""

from __future__ import annotations

import re


# ── <br> and markdown artifact cleanup ────────────────────────────────────────

# "word-<br>continuation" — hyphen immediately before <br>
_BR_HYPHEN_RE = re.compile(r"-\s*<br\s*/?>\s*", re.IGNORECASE)
# bare "<br>" with no hyphen — replace with space
_BR_RE = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)
# **bold** markdown
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
# *italic* markdown (single star)
_ITALIC_RE = re.compile(r"\*(.+?)\*")
# trailing/leading whitespace in cells after split


def clean_br(text: str) -> str:
    """Strip <br> artifacts and repair broken words."""
    # hyphen-continuation first (order matters)
    text = _BR_HYPHEN_RE.sub("", text)
    # remaining <br> → space
    text = _BR_RE.sub(" ", text)
    return text


def clean_cell(text: str) -> str:
    """Clean a single table cell: <br>, bold/italic markdown, extra whitespace."""
    text = clean_br(text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_markdown(text: str) -> str:
    """Global <br> cleanup on a full markdown string before table parsing."""
    return clean_br(text)


# ── table detection ────────────────────────────────────────────────────────────

def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _is_separator_line(line: str) -> bool:
    """Markdown separator row: | --- | :---: | etc."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    inner = stripped.strip("|")
    cells = [c.strip() for c in inner.split("|")]
    return all(re.match(r"^:?-+:?$", c) for c in cells if c)


# ── table parser ───────────────────────────────────────────────────────────────

def _parse_table_block(lines: list[str]) -> list[list[str]]:
    """Parse a block of consecutive '|'-prefixed lines into a list of cell rows."""
    rows: list[list[str]] = []
    for line in lines:
        if _is_separator_line(line):
            continue
        stripped = line.strip().strip("|")
        cells = [clean_cell(c) for c in stripped.split("|")]
        if any(c for c in cells):
            rows.append(cells)
    return rows


def _extract_table_blocks(text: str) -> list[list[str]]:
    """Return each contiguous group of table lines as a list-of-line-lists."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if _is_table_line(line):
            current.append(line)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


# ── context extraction ─────────────────────────────────────────────────────────

def _context_above(text: str, table_start_pos: int, chars: int = 400) -> str:
    """Return up to *chars* of text immediately before the table start position."""
    start = max(0, table_start_pos - chars)
    return text[start:table_start_pos]


# ── public API ─────────────────────────────────────────────────────────────────

def parse_markdown_tables(md_text: str) -> list[dict]:
    """Parse all markdown tables from *md_text* into table dicts.

    Each dict matches the format expected by pipe_parser / duct_parser:
        {
            "page_num": 0,         # not available from md, set to 0
            "table_index": N,
            "rows": [[cell, ...], ...],
            "page_text": "",       # not populated
            "pre_table_text": str, # text above the table block
        }

    Args:
        md_text: Full markdown string from pymupdf4llm (already br-cleaned).

    Returns:
        List of table dicts.
    """
    # clean br artifacts first
    md_text = clean_markdown(md_text)

    results: list[dict] = []
    lines = md_text.splitlines(keepends=True)

    t_idx = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _is_table_line(line):
            i += 1
            continue

        # collect contiguous table lines
        block_lines: list[str] = []
        block_start_char = sum(len(l) for l in lines[:i])
        j = i
        while j < len(lines) and _is_table_line(lines[j]):
            block_lines.append(lines[j])
            j += 1

        rows = _parse_table_block(block_lines)
        if rows and any(any(c for c in row) for row in rows):
            pre_text = _context_above(md_text, block_start_char)
            results.append(
                {
                    "page_num": 0,
                    "table_index": t_idx,
                    "rows": rows,
                    "page_text": "",
                    "pre_table_text": pre_text,
                }
            )
            t_idx += 1

        i = j

    return results
