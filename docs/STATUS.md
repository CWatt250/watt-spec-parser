# Spec Parser — Current Status

Last updated: 2026-03-09

## Where this lives
- Repo root: `C:\Users\WattB\.openclaw\workspace\estimator-toolkit`
- Engine: `C:\Users\WattB\.openclaw\workspace\estimator-toolkit\spec_parser`

## Current state
- **Python runtime blocked** (not installed/working), so Phase 1 has **not been executed** yet.
- All Phase 1 components + debugging outputs are scaffolded and wired.

## What’s implemented (non-runtime)
- Document model: `spec_parser/src/spec_parser/models/document_model.py`
- Config dictionaries:
  - `spec_parser/src/spec_parser/config/service_dictionary.py`
  - `spec_parser/src/spec_parser/config/material_dictionary.py`
- Rule pack placeholders:
  - `spec_parser/rules/pipe_rules.yaml`
  - `spec_parser/rules/duct_rules.yaml`
  - `spec_parser/rules/equipment_rules.yaml`
- CSI section detection (conservative): `spec_parser/src/spec_parser/detect/csi_sections.py`
- Section classification (lightweight): `spec_parser/src/spec_parser/detect/section_classifier.py`
- Keyword scanner module (not yet wired): `spec_parser/src/spec_parser/analysis/keyword_scanner.py`
- Export schemas: `spec_parser/src/spec_parser/export/schemas.py`
- Run summary export: `spec_parser/src/spec_parser/export/run_summary.py`
- Section text export: `spec_parser/src/spec_parser/export/section_text.py`
- Pipeline wiring: `spec_parser/src/spec_parser/pipeline.py`

## Expected Phase 1 artifacts (once Python works)
Written to the chosen output folder (e.g. `spec_parser/artifacts/phase1_phx74_230700/`):
- `Source Sections.xlsx`
- `source_sections.json`
- `raw_text_preview.txt`
- `normalized_text_preview.txt`
- `warnings.txt`
- `run_summary.txt`
- `section_text/section_*.txt`

## Next step (first proof run)
```bat
cd C:\Users\WattB\.openclaw\workspace\estimator-toolkit\spec_parser
python -m spec_parser.cli.main --in "C:\Users\WattB\.openclaw\workspace\estimator-toolkit\samples\PHX 74\230700.pdf" --out "C:\Users\WattB\.openclaw\workspace\estimator-toolkit\spec_parser\artifacts\phase1_phx74_230700"
```
