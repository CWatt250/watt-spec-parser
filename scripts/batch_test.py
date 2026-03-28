"""Batch test: run every PDF in Spec Samples through the full pipeline.

Prints one summary line per PDF:
    SpecName/filename.pdf: X pipe, X duct, X jacket

Usage:
    python scripts/batch_test.py
    python scripts/batch_test.py "C:/path/to/Spec Samples"
"""
from __future__ import annotations

import os
import sys
import time

# Add src to path so imports work without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SPEC_SAMPLES_DEFAULT = r"C:\Users\WattB\.openclaw\workspace\watt-spec-parser\Spec Samples"


def run_pdf(pdf_path: str) -> tuple[int, int, int]:
    """Return (pipe_rows, duct_rows, jacket_rows) for one PDF."""
    from spec_parser.pipeline import run_single

    result = run_single(pdf_path, out_dir=os.path.join(os.path.dirname(pdf_path), "_batch_out"))
    return (
        len(result["pipe_rows"]),
        len(result["duct_rows"]),
        len(result["jacket_rows"]),
    )


def collect_pdfs(base_dir: str) -> list[str]:
    pdfs: list[str] = []
    for root, _dirs, files in os.walk(base_dir):
        for f in sorted(files):
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return pdfs


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else SPEC_SAMPLES_DEFAULT
    if not os.path.isdir(base):
        print(f"ERROR: Spec Samples directory not found: {base}", file=sys.stderr)
        sys.exit(1)

    pdfs = collect_pdfs(base)
    if not pdfs:
        print("No PDFs found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(pdfs)} PDFs in {base}\n")
    totals = [0, 0, 0]

    for pdf_path in pdfs:
        rel = os.path.relpath(pdf_path, base)
        label = rel.replace("\\", "/")
        t0 = time.time()
        try:
            pipe, duct, jacket = run_pdf(pdf_path)
            elapsed = time.time() - t0
            print(f"{label}: {pipe} pipe, {duct} duct, {jacket} jacket  ({elapsed:.1f}s)")
            totals[0] += pipe
            totals[1] += duct
            totals[2] += jacket
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"{label}: ERROR — {exc}  ({elapsed:.1f}s)")

    print(f"\nTOTALS: {totals[0]} pipe, {totals[1]} duct, {totals[2]} jacket")


if __name__ == "__main__":
    main()
