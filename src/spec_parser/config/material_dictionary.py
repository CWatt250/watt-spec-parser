"""Insulation material alias normalization.

Phase 2+ will use this to normalize material mentions in extracted rows.
"""

from __future__ import annotations


MATERIAL_ALIASES: dict[str, list[str]] = {
    "FIBERGLASS": [
        "FIBERGLASS",
        "FIBER GLASS",
        "GLASS FIBER",
        "GLASSFIBER",
        "FIBER GLASS PIPE INSULATION",
    ],
    "ELASTOMERIC": [
        "ELASTOMERIC",
        "ELASTOMER",
        "ARMAFLEX",
        "RUBBER INSULATION",
        "CLOSED-CELL ELASTOMERIC",
    ],
    "MINERAL WOOL": [
        "MINERAL WOOL",
        "ROCKWOOL",
        "STONE WOOL",
    ],
    "CELLULAR GLASS": [
        "CELLULAR GLASS",
        "FOAM GLASS",
        "FOAMGLASS",
        "PITTSBURGH CORNING FOAMGLAS",
    ],
    "POLYISO": [
        "POLYISO",
        "POLYISOCYANURATE",
        "POLYISOCYANURATE FOAM",
        "PIR",
    ],
    "PHENOLIC": [
        "PHENOLIC",
        "PHENOLIC FOAM",
    ],
}


def build_reverse_alias_map() -> dict[str, str]:
    rev: dict[str, str] = {}
    for canonical, aliases in MATERIAL_ALIASES.items():
        for a in aliases:
            rev[a.strip().upper()] = canonical
    return rev


MATERIAL_ALIAS_MAP = build_reverse_alias_map()
