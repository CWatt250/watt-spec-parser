# CLAUDE.md — Watt Spec Parser

## Project Goal
Standalone offline mechanical insulation spec parser. Zero LLM calls, zero token usage, no API dependency. Runs on any machine at no cost. Parses construction specification PDFs and extracts pipe insulation, duct insulation, and jacket/covering requirements into structured Excel output.

## Tech Stack
- **PyMuPDF (fitz)** — primary PDF text extraction (fast, reliable)
- **pdfplumber** — table extraction ONLY (bordered schedule tables)
- **spaCy EntityRuler** — custom regex patterns for entity extraction (model: en_core_web_sm, already installed)
- **rapidfuzz** — fuzzy synonym matching for service/material normalization
- **pandas + openpyxl** — Excel output generation
- **customtkinter + tkinterdnd2** — desktop GUI with drag & drop

## Key Files
| File | Purpose |
|------|---------|
| `src/spec_parser/extract/pdf_text.py` | PyMuPDF text extraction from PDFs |
| `src/spec_parser/extract/table_extract.py` | pdfplumber table extraction (bordered tables only) |
| `src/spec_parser/detect/csi_sections.py` | CSI section header detection + deduplication |
| `src/spec_parser/detect/section_classifier.py` | Section type classification |
| `src/spec_parser/parse/pipe_parser.py` | Table-based pipe insulation row extraction |
| `src/spec_parser/parse/duct_parser.py` | Duct insulation schedule parsing |
| `src/spec_parser/parse/jacket_parser.py` | Jacket/covering requirements extraction from prose |
| `src/spec_parser/parse/text_fallback_parser.py` | Text-based fallback for specs without bordered tables (CSI outline format, numbered lists) |
| `src/spec_parser/config/service_dictionary.py` | Service name alias maps (canonical names) |
| `src/spec_parser/config/material_dictionary.py` | Material/insulation type alias maps |
| `src/spec_parser/normalize/alias_norm.py` | 3-step normalization: exact → substring → rapidfuzz |
| `src/spec_parser/normalize/text_norm.py` | Text normalization utilities |
| `src/spec_parser/analysis/keyword_scanner.py` | Keyword scanning/analysis |
| `src/spec_parser/models/document_model.py` | Document data model |
| `src/spec_parser/models/types.py` | Shared type definitions |
| `src/spec_parser/export/excel.py` | Excel output with 5 sheets |
| `src/spec_parser/export/schemas.py` | Column definitions for target sheets |
| `src/spec_parser/pipeline.py` | Single-file pipeline orchestration |
| `src/spec_parser/cli/main.py` | CLI entry point |
| `src/spec_parser/gui/app.py` | customtkinter desktop GUI with drag & drop, real-time parsing |

## Target Output Format
Excel file with 4 target sheets + 1 debug sheet:
1. **Pipe_Insulation** — Service, Pipe Size Range, Thickness, Insulation Type, Jacket Required, Notes/Location
2. **Duct_Insulation** — System, Exposed, Concealed, Outdoor, Notes
3. **Jacket_Rules** — Rule, Condition, Jacket Type, Notes
4. **MASTER** — All rows combined with Row_Type and PDF_File columns
5. **Source_Sections** — Debug: detected CSI sections with page ranges

## Build Rules
- **NEVER run `python -m spacy download`** — it hangs. The en_core_web_sm model is already installed.
- Always use `--break-system-packages` flag with pip install
- Use 60s timeout max on bash commands running the parser
- Test ONE PDF at a time, never all 11 at once (causes timeouts)
- Commit to GitHub after every completed item
- PDFs are in `Spec Samples/` directory (gitignored, local only)
- Best test file: `Spec Samples/PDX154/230700.pdf` (16 pages, has tables)
- Text-only test: `Spec Samples/PHX73/230700.pdf` (CSI outline format)

## Known Issues Still To Fix
- **Alias mismatch:** "Condenser Water" fuzzy-matches to CONDENSATE instead of CONDENSER WATER
- **Alias mismatch:** "Exposed Sanitary" fuzzy-matches to DOMESTIC HOT WATER instead of SANITARY DRAINS
- **Hot/cold collapse:** UO2 spec "Service (Domestic) Water Piping (Hot/Cold)" collapses into single service instead of preserving hot/cold distinction
- **Word-wrap artifacts:** Some pdfplumber table cells still concatenate words without spaces on certain PDFs

## Sample Specs
| Folder | Files | Format |
|--------|-------|--------|
| PDX154 | 220700.pdf, 230700.pdf | Bordered tables |
| PHX73 | 220700.pdf, 230700.pdf | CSI outline (text) |
| PHX83 | 22_07_00.pdf, 23_07_00.pdf | CSI outline (text) |
| UO2.MO | 22-07-00.pdf, 230700.pdf | Hierarchical text |
| IDABWellsHS | Vol 1, Vol 2 | Full spec books (large) |
