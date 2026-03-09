from __future__ import annotations

import os
from datetime import datetime

from spec_parser.models.types import PageText, SourceSection


def write_run_summary(
    *,
    pdf_path: str,
    pages_raw: list[PageText],
    sections: list[SourceSection],
    warnings: list[str],
    out_dir: str,
) -> str:
    """Write a human-readable run summary report.

    Phase 1+: Used to debug extraction quality and section detection.

    Output: run_summary.txt in out_dir.
    """

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "run_summary.txt")

    total_pages = len(pages_raw)
    pages_with_text = sum(1 for p in pages_raw if (p.text or "").strip())
    avg_chars = (sum(len(p.text or "") for p in pages_raw) / total_pages) if total_pages else 0

    # Insulation-ish detection (very lightweight): looks for known insulation sections
    insulation = []
    for s in sections:
        n = (s.normalized_section_number or "").strip()
        t = (s.section_title or "").strip()
        if n in {"23 07 19", "23 07 13", "22 07 19"}:
            insulation.append((n, t))
        elif "INSULATION" in (t or "").upper():
            insulation.append((n or (s.section_number or ""), t))

    # Section range metrics (pages)
    lengths = [(max(1, (s.end_page - s.start_page + 1))) for s in sections]
    longest = max(lengths) if lengths else 0
    shortest = min(lengths) if lengths else 0
    avg_len = (sum(lengths) / len(lengths)) if lengths else 0

    total_categorized = sum(1 for s in sections if (s.category or "").strip())
    uncategorized = len(sections) - total_categorized

    insulation_related_count = sum(
        1
        for s in sections
        if (s.category or "").upper().find("INSULATION") >= 0
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"TIMESTAMP: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"FILE: {pdf_path}\n")
        f.write(f"TOTAL PAGES: {total_pages}\n")
        f.write(f"PAGES WITH EXTRACTED TEXT: {pages_with_text}\n")
        f.write(f"AVERAGE CHARACTERS PER PAGE: {avg_chars:.0f}\n")

        f.write("\nSECTION DETECTION\n")
        f.write(f"SECTIONS FOUND: {len(sections)}\n")
        f.write(f"LONGEST DETECTED SECTION (PAGES): {longest}\n")
        f.write(f"SHORTEST DETECTED SECTION (PAGES): {shortest}\n")
        f.write(f"AVERAGE SECTION LENGTH (PAGES): {avg_len:.2f}\n")
        f.write(f"TOTAL CATEGORIZED SECTIONS: {total_categorized}\n")
        f.write(f"UNCATEGORIZED SECTIONS (COUNT): {uncategorized}\n")
        f.write(f"INSULATION-RELATED SECTIONS (COUNT): {insulation_related_count}\n")

        f.write("\nINSULATION SECTIONS DETECTED\n")
        if insulation:
            for n, t in insulation[:50]:
                f.write((f"- {n} {t}").rstrip() + "\n")
        else:
            f.write("- (none detected by lightweight heuristic)\n")

        f.write("\nWARNINGS\n")
        if warnings:
            for w in warnings:
                f.write(f"- {w}\n")
        else:
            f.write("- (none)\n")

    return out_path
