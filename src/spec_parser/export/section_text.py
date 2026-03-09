from __future__ import annotations

import os

from spec_parser.models.types import PageText, SourceSection


def _safe_section_filename(section: SourceSection) -> str:
    n = (section.normalized_section_number or section.section_number or "unknown").strip()
    n = n.replace(" ", "_").replace(".", "_")
    return f"section_{n}.txt"


def export_section_text(
    *,
    pages: list[PageText],
    sections: list[SourceSection],
    out_dir: str,
) -> str:
    """Export full text for each detected section.

    Creates: <out_dir>/section_text/section_23_07_19.txt etc.

    Conservative behavior:
    - Uses page ranges only (start_page/end_page)
    - Does not attempt to infer intra-page boundaries yet
    """

    section_dir = os.path.join(out_dir, "section_text")
    os.makedirs(section_dir, exist_ok=True)

    page_map = {p.page_num: p.text or "" for p in pages}

    for s in sections:
        fn = _safe_section_filename(s)
        path = os.path.join(section_dir, fn)

        texts = []
        for pn in range(s.start_page, s.end_page + 1):
            texts.append(f"\n\n===== PAGE {pn} =====\n")
            texts.append(page_map.get(pn, ""))

        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(texts).strip() + "\n")

    return section_dir
