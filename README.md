# Estimator Toolkit — Spec Parser (Rules-Based)

**Runtime constraint:** no AI dependency at runtime.

## v0.1 Target (Phase 1)
Given **one spec PDF**, produce:
- `Source Sections.xlsx`
- `source_sections.json`

Pipeline:
1) extract machine-readable text
2) normalize
3) detect CSI sections
4) classify (lightweight for now)
5) export

## Run (planned)
```bash
python -m spec_parser.cli.main --in <spec.pdf> --out <output_dir>
```

## Output (Phase 1)
Workbook: **Source Sections.xlsx**
- Project File
- Section Number
- Section Title
- Category
- Start Page
- End Page
- Relevance Level
- Parse Notes

Plus JSON with the same records.
