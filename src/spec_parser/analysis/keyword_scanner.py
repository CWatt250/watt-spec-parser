from __future__ import annotations

from dataclasses import dataclass

from spec_parser.models.types import PageText, SourceSection


@dataclass(frozen=True)
class KeywordHit:
    keyword: str
    section: str
    page: int
    source_text: str


def scan_keywords(
    *,
    keywords: list[str],
    pages: list[PageText],
    sections: list[SourceSection],
    context_chars: int = 120,
) -> list[KeywordHit]:
    """Scan for user-provided keywords and return hits.

    Conservative implementation:
    - case-insensitive substring match
    - uses section page ranges to limit search
    - returns short context window around the first match per page
    """
    if not keywords:
        return []

    kw_norm = [k.strip() for k in keywords if k and k.strip()]
    if not kw_norm:
        return []

    page_map = {p.page_num: p.text or "" for p in pages}

    hits: list[KeywordHit] = []
    for s in sections:
        sec_id = (s.normalized_section_number or s.section_number or s.section_title or "unknown").strip()
        for pn in range(s.start_page, s.end_page + 1):
            text = page_map.get(pn, "")
            up = text.upper()

            for kw in kw_norm:
                k_up = kw.upper()
                idx = up.find(k_up)
                if idx == -1:
                    continue

                start = max(0, idx - context_chars)
                end = min(len(text), idx + len(kw) + context_chars)
                snippet = text[start:end].replace("\n", " ")

                hits.append(
                    KeywordHit(
                        keyword=kw,
                        section=sec_id,
                        page=pn,
                        source_text=snippet.strip(),
                    )
                )
                # Limit to first match per keyword per page for now
                break

    return hits
