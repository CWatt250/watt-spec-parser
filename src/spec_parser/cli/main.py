from __future__ import annotations

import argparse

from spec_parser.pipeline import run_phase1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec-parser", description="Estimator Toolkit spec parser (rules-based)")
    p.add_argument("--in", dest="pdf_path", required=True, help="Input spec PDF path")
    p.add_argument("--out", dest="out_dir", required=True, help="Output directory")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    outputs = run_phase1(pdf_path=args.pdf_path, out_dir=args.out_dir)

    print("OK")
    print(f"File:  {args.pdf_path}")
    print(f"Excel: {outputs['xlsx']}")
    print(f"JSON:  {outputs['json']}")
    print(f"Raw:   {outputs['raw_preview']}")
    print(f"Norm:  {outputs['normalized_preview']}")
    print(f"Warn:  {outputs['warnings']}")
    print(f"Secs:  {outputs['section_text_dir']}")
    print(f"Sum:   {outputs['run_summary']}")


if __name__ == "__main__":
    main()
