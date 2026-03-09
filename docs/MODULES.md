# Spec Parser — Module Map (v0.1 focus)

Goal: deterministic spec PDF parser (no AI runtime) that extracts **Source Sections** first.

## Package layout (proposed)

`spec_parser/src/spec_parser/`

### `cli/`
- `main.py`
  - CLI entry (argparse)
  - wires together: load → extract → normalize → section-detect → export

### `extract/`
- `pdf_text.py`
  - PyMuPDF extraction
  - returns per-page text + page metadata

### `normalize/`
- `text_norm.py`
  - whitespace normalization
  - hyphenation fixes (line-wrap)
  - common OCR cleanup helpers

### `detect/`
- `csi_sections.py`
  - CSI-ish section detection from normalized text
  - builds `SourceSection` records: section number/title, page range, raw text slice

### `models/`
- `types.py`
  - dataclasses for `PageText`, `SourceSection`, `ParseConfig`, etc.

### `export/`
- `excel.py`
  - writes `Source Sections.xlsx`
- `json_out.py`
  - writes JSON alongside Excel (same data)

### `pipeline.py`
- orchestrates Phase 1 pipeline end-to-end

## Phases

### Phase 1 (this build target)
- input one PDF
- extract machine-readable text
- normalize
- detect CSI sections
- export **Source Sections.xlsx** (+ JSON)

### Phase 2
- scope mode filtering
- pipe insulation extractor

### Phase 3
- duct insulation extractor

### Phase 4
- equipment extraction
- include/exclude keyword scan
- review flags

### Phase 5
- simple local UI (drag/drop)
