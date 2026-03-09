# Watt Spec Parser

Deterministic local parser for mechanical insulation specs (no AI runtime dependency).

## Current status
Architecture baseline is complete. **Runtime proof (Phase 1) is pending Python install/config on Windows.**

## Planned outputs
- Source Sections
- Pipe Insulation
- Duct Insulation
- Scope Gap Flags
- Insulation Summary

## Current pipeline
- PDF text extraction
- Text normalization
- CSI section detection (conservative)
- Section classification (conservative)
- Excel/JSON/debug exports (including section text + run summary)

## Sample Phase 1 command (runtime proof)
Python must be installed and on PATH before running.

```bat
cd C:\Users\WattB\.openclaw\workspace\estimator-toolkit\spec_parser
python -m spec_parser.cli.main --in "C:\Users\WattB\.openclaw\workspace\estimator-toolkit\samples\PHX 74\230700.pdf" --out "C:\Users\WattB\.openclaw\workspace\estimator-toolkit\spec_parser\artifacts\phase1_phx74_230700"
```
