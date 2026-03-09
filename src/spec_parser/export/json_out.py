from __future__ import annotations

import json
import os
from dataclasses import asdict

from spec_parser.models.types import SourceSection


def export_source_sections_json(sections: list[SourceSection], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "source_sections.json")

    payload = [asdict(s) for s in sections]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return out_path
