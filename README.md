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
