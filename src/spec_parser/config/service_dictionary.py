"""Service/system alias normalization.

Phase 2+ will use this to normalize service names in extracted rows.

Rule: keep canonical keys stable; alias matching should be case-insensitive.
"""

from __future__ import annotations


# Canonical -> aliases
SERVICE_ALIASES: dict[str, list[str]] = {
    "CHILLED WATER": [
        "CHW",
        "CHILLED WATER",
        "CHILLED WATER SUPPLY",
        "CHILLED WATER RETURN",
        "CHWS",
        "CHWR",
    ],
    "HEATING HOT WATER": [
        "HHW",
        "HEATING HOT WATER",
        "HOT WATER HEATING",
        "HHWS",
        "HHWR",
    ],
    "DOMESTIC HOT WATER": [
        "DHW",
        "DOMESTIC HOT WATER",
        "HWS",
        "HOT WATER SUPPLY",
        "HWR",
        "HOT WATER RETURN",
    ],
    "CONDENSATE": [
        "CONDENSATE",
        "CONDENSATE DRAIN",
        "STEAM CONDENSATE",
        "CON",
    ],
    "CONDENSER WATER": [
        "CONDENSER WATER",
        "CONDENSER WATER SUPPLY",
        "CONDENSER WATER RETURN",
        "CWS",
        "CWR",
        "CONDENSER",
    ],
    "SANITARY DRAINS": [
        "SANITARY DRAINS",
        "SANITARY DRAIN",
        "SANITARY WASTE",
        "EXPOSED SANITARY",
        "SANITARY",
        "SANITARY PIPING",
    ],
    "STEAM": [
        "STEAM",
        "STM",
    ],
    "DOMESTIC COLD WATER": [
        "DCW",
        "COLD WATER",
        "CW",
        "DOMESTIC COLD WATER",
    ],
    "GLYCOL": [
        "GLYCOL",
        "GLYCOL WATER",
        "Glycol",
    ],
}


def build_reverse_alias_map() -> dict[str, str]:
    """Alias (upper) -> canonical."""
    rev: dict[str, str] = {}
    for canonical, aliases in SERVICE_ALIASES.items():
        for a in aliases:
            rev[a.strip().upper()] = canonical
    return rev


SERVICE_ALIAS_MAP = build_reverse_alias_map()
