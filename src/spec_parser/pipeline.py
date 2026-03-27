from __future__ import annotations

import os

from spec_parser.extract.pdf_text import extract_pages
from spec_parser.extract.table_extract import extract_schedule_tables, extract_tables_from_pdf
from spec_parser.normalize.text_norm import normalize_text
from spec_parser.detect.csi_sections import detect_source_sections
from spec_parser.detect.section_classifier import classify_sections
from spec_parser.parse.pipe_parser import parse_pipe_insulation
from spec_parser.parse.duct_parser import parse_duct_insulation
from spec_parser.parse.jacket_parser import parse_jacket_rules, parse_jacket_rules_from_pdf
from spec_parser.export.excel import export_source_sections_xlsx
from spec_parser.export.json_out import export_source_sections_json
from spec_parser.export.section_text import export_section_text
from spec_parser.export.run_summary import write_run_summary


# ── insulation-section page scoping ───────────────────────────────────────────

_INSULATION_CATEGORIES = frozenset(
    {
        "HVAC_PIPING_INSULATION",
        "DUCT_INSULATION",
        "PLUMBING_PIPING_INSULATION",
        "PLUMBING_INSULATION",
        "MECHANICAL_INSULATION",
    }
)


def _insulation_page_list(sections: list, total_pages: int) -> list[int] | None:
    """Compute the explicit page list to scan for insulation tables.

    For full spec books (at least one non-insulation CSI section is detected)
    we restrict scanning to the pages covered by insulation sections only.
    This prevents false-positive tables from pressure-test schedules, piping
    identification, etc. that live in completely different CSI sections.

    Returns None for pre-extracted insulation-only specs so the caller falls
    back to the default extract_schedule_tables() behaviour (pages 13-15 →
    10-16 → all pages).
    """
    non_insul = [
        s for s in sections if s.category and s.category not in _INSULATION_CATEGORIES
    ]
    # No non-insulation sections detected → pre-extracted spec → scan all pages
    if not non_insul:
        return None

    all_sorted = sorted(sections, key=lambda s: s.start_page)
    pages: set[int] = set()

    for sec in all_sorted:
        if sec.category not in _INSULATION_CATEGORIES:
            continue
        # Use the detected start/end page span for this section.
        # For running-header sections this accurately reflects the pages on
        # which that CSI number appears.  The table-level filter in pipe_parser
        # provides a second defence against false-positive tables that may sit
        # on the same pages as an insulation section (e.g. pressure test
        # schedules that share a page range with section 23 07 13 footers).
        pages.update(range(sec.start_page, min(sec.end_page, total_pages) + 1))

    return sorted(pages) if pages else None


def _write_text_preview(pages: list, out_path: str, *, normalized: bool) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for p in pages:
            f.write(f"\n\n===== PAGE {p.page_num} =====\n")
            f.write((p.text or "")[:8000])  # cap preview per page
            f.write("\n")


def _compute_warnings(pages: list) -> list[str]:
    warnings: list[str] = []
    if not pages:
        return ["No pages extracted"]

    empty_pages = sum(1 for p in pages if not (p.text or "").strip())
    if empty_pages / max(1, len(pages)) > 0.5:
        warnings.append(f"Low text density: {empty_pages}/{len(pages)} pages are empty")

    avg_chars = sum(len(p.text or "") for p in pages) / max(1, len(pages))
    if avg_chars < 200:
        warnings.append(f"Abnormally low extraction output: avg {avg_chars:.0f} chars/page")

    return warnings


def run_phase1(pdf_path: str, out_dir: str) -> dict[str, str]:
    """Phase 1 prototype pipeline.

    Input: one PDF
    Output:
    - Source Sections.xlsx
    - source_sections.json
    - raw_text_preview.txt
    - normalized_text_preview.txt
    - warnings.txt
    """
    project_file = os.path.basename(pdf_path)

    pages_raw = extract_pages(pdf_path)
    warnings = _compute_warnings(pages_raw)

    raw_preview = os.path.join(out_dir, "raw_text_preview.txt")
    _write_text_preview(pages_raw, raw_preview, normalized=False)

    pages_norm = [
        type(p)(page_num=p.page_num, text=normalize_text(p.text))  # PageText is frozen dataclass
        for p in pages_raw
    ]

    norm_preview = os.path.join(out_dir, "normalized_text_preview.txt")
    _write_text_preview(pages_norm, norm_preview, normalized=True)

    sections = detect_source_sections(project_file=project_file, pages=pages_norm)
    sections = classify_sections(sections)

    # Warnings based on detection
    if len(sections) <= 3:
        warnings.append(f"Extremely low number of detected sections: {len(sections)}")

    # Additional heuristics
    empty_pages = sum(1 for p in pages_raw if not (p.text or "").strip())
    if empty_pages >= max(10, int(len(pages_raw) * 0.6)):
        warnings.append(f"Unusually large number of pages with no text: {empty_pages}/{len(pages_raw)}")

    avg_chars = (sum(len(p.text or "") for p in pages_raw) / max(1, len(pages_raw)))
    if avg_chars < 200:
        warnings.append(f"Very low average characters per page (possible scanned PDF): {avg_chars:.0f}")

    warn_path = os.path.join(out_dir, "warnings.txt")
    with open(warn_path, "w", encoding="utf-8") as f:
        for w in warnings:
            f.write(w + "\n")

    # Export main artifacts
    xlsx_path = export_source_sections_xlsx(sections, out_dir)
    json_path = export_source_sections_json(sections, out_dir)

    # Export full text for each detected section (debug)
    section_text_dir = export_section_text(pages=pages_norm, sections=sections, out_dir=out_dir)

    # Export run summary
    run_summary_path = write_run_summary(
        pdf_path=pdf_path,
        pages_raw=pages_raw,
        sections=sections,
        warnings=warnings,
        out_dir=out_dir,
    )

    return {
        "xlsx": xlsx_path,
        "json": json_path,
        "raw_preview": raw_preview,
        "normalized_preview": norm_preview,
        "warnings": warn_path,
        "section_text_dir": section_text_dir,
        "run_summary": run_summary_path,
    }


def run_single(pdf_path: str, out_dir: str) -> dict:
    """Full pipeline for one PDF: sections + insulation schedules + jacket rules.

    Returns a dict with all source-section and parsed rows, plus file paths.
    """
    project_file = os.path.basename(pdf_path)

    pages_raw = extract_pages(pdf_path)
    warnings = _compute_warnings(pages_raw)

    pages_norm = [
        type(p)(page_num=p.page_num, text=normalize_text(p.text))
        for p in pages_raw
    ]

    sections = detect_source_sections(project_file=project_file, pages=pages_norm)
    sections = classify_sections(sections)

    # Scope table extraction and jacket scanning to insulation-section pages.
    # For full spec books (multiple CSI sections detected) we only read pages
    # inside the insulation sections, eliminating false-positive tables from
    # pressure-test schedules or other unrelated sections.
    # For pre-extracted specs the helper returns None and we use the normal
    # page-13-15 → 10-16 → all-pages fallback.
    insul_pages = _insulation_page_list(sections, len(pages_raw))
    if insul_pages:
        tables = extract_tables_from_pdf(pdf_path, page_numbers=insul_pages)
    else:
        tables = extract_schedule_tables(pdf_path)

    pipe_rows = parse_pipe_insulation(tables, pdf_file=project_file)
    duct_rows = parse_duct_insulation(tables, pdf_file=project_file)

    # Jacket rules: scope to insulation-section pages when known
    if insul_pages:
        insul_page_set = set(insul_pages)
        insul_texts = [p.text for p in pages_raw if p.page_num in insul_page_set]
        jacket_rows = parse_jacket_rules(insul_texts, pdf_file=project_file)
    else:
        jacket_rows = parse_jacket_rules_from_pdf(pdf_path, pdf_file=project_file)

    return {
        "project_file": project_file,
        "sections": sections,
        "pipe_rows": pipe_rows,
        "duct_rows": duct_rows,
        "jacket_rows": jacket_rows,
        "warnings": warnings,
        "pages_raw": pages_raw,
        "pages_norm": pages_norm,
    }


def run_multi(
    pdf_paths: list[str],
    out_dir: str,
) -> dict:
    """Run the full pipeline over multiple PDFs and aggregate into a MASTER dataset.

    Each row is tagged with PDF_File.
    Returns aggregated data and writes the combined Excel to out_dir.
    """
    all_sections = []
    all_pipe: list[dict] = []
    all_duct: list[dict] = []
    all_jacket: list[dict] = []
    all_warnings: list[str] = []

    for pdf_path in pdf_paths:
        result = run_single(pdf_path, out_dir)
        all_sections.extend(result["sections"])
        all_pipe.extend(result["pipe_rows"])
        all_duct.extend(result["duct_rows"])
        all_jacket.extend(result["jacket_rows"])
        for w in result["warnings"]:
            all_warnings.append(f"{result['project_file']}: {w}")

    return {
        "sections": all_sections,
        "pipe_rows": all_pipe,
        "duct_rows": all_duct,
        "jacket_rows": all_jacket,
        "warnings": all_warnings,
    }
