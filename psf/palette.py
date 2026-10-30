"""Author-defined organization colors with a stable legacy default.

Colors are build-time artwork data, not an unsupported scripted-GUI property.
The same resolver supplies chart frames, bookmark snapshots and identity badges.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping


def parse_color(value: object) -> tuple[int, int, int]:
    """Accept a six-digit hex color or three integral RGB channels; never clip."""
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    if (isinstance(value, (list, tuple)) and len(value) == 3
            and all(not isinstance(channel, bool) and isinstance(channel, (int, float))
                    and 0 <= channel <= 255 and int(channel) == channel
                    for channel in value)):
        return tuple(int(channel) for channel in value)
    raise ValueError("Organization color must be #RRGGBB or three integer RGB channels from 0 to 255")


def color(organization: Mapping | str) -> tuple[int, int, int]:
    """Resolve one identity color; old manifests retain their exact previous RGB."""
    if isinstance(organization, Mapping):
        if "color" in organization:
            return parse_color(organization["color"])
        identifier = organization["id"]
    else:
        identifier = organization
    digest = hashlib.sha256(identifier.encode()).digest()
    return tuple(86 + byte % 140 for byte in digest[:3])
