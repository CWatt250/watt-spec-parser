from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Normalize extracted PDF text for deterministic parsing.

    Phase 1 goals:
    - reduce whitespace noise
    - fix common hyphenated line breaks

    Keep it conservative: don't rewrite semantics, just formatting.
    """
    if not text:
        return ""

    # Fix hyphenated line wraps: "insula-\n tion" -> "insulation"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ newlines to 2 (keep some structure)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Trim trailing spaces per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    return text.strip()
