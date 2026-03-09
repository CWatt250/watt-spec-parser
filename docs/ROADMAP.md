# Roadmap

## Phase 1 — Runtime proof + Source Sections
- Confirm Python runtime works on Windows
- Run on real spec PDFs
- Validate extraction quality + conservative CSI section detection
- Export:
  - Source Sections.xlsx
  - source_sections.json
  - raw/normalized previews
  - warnings.txt
  - run_summary.txt
  - section_text/ outputs

## Phase 2 — Scope mode filter
- Add scope modes and relevance marking
- Filter which detected sections are considered relevant downstream

## Phase 3 — Pipe insulation extraction
- Deterministic extraction for piping insulation requirements

## Phase 4 — Duct insulation extraction
- Deterministic extraction for duct insulation requirements

## Phase 5 — Equipment references + keyword hits + scope gaps
- Equipment inclusion/exclusion detection
- Include/exclude keyword hits
- Scope gap flags / review flags

## Phase 6 — Insulation summary
- Generate summary sheet (system/material/typical thickness/etc.)
