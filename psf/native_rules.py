"""Narrow, source-preserving adapters for generic native political bonuses."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .model import ManifestError

ASSETS = Path(__file__).resolve().parent / "assets" / "native_politics"
OPINIONS = "common/opinion_modifiers/00_opinion_modifiers.txt"
PEACE = "common/peace_conference/cost_modifiers/00_generic_peace.txt"
PARTY_OPINIONS = {"same_ruling_party", "similar_ruling_party", "different_party_types"}


def neutralize(text: str, relative: str) -> tuple[str, list[str]]:
    """Edit only generic ideology fields; retain unrelated source statements."""
    from .ui import gui_nodes

    root_name = "opinion_modifiers" if relative == OPINIONS else "peace_action_modifiers"
    roots = [node for node in gui_nodes(text) if node.parent is None and node.kind == root_name]
    if len(roots) != 1:
        raise ManifestError(f"Native politics adapter requires one {root_name} root: {relative}")
    changes: list[tuple[int, int, str]] = []
    changed = []
    for node in roots[0].children:
        if relative == OPINIONS:
            if node.kind not in PARTY_OPINIONS:
                continue
            if "value" not in node.properties:
                raise ManifestError(f"Missing original opinion value: {node.kind}")
            start, end, _ = node.properties["value"]
            # Preserve inline siblings and closing braces: adding a trailing
            # comment here would swallow the remainder of a valid one-line
            # source block.
            changes.append((start, end, "value = 0"))
        else:
            if node.properties.get("category", (None, None, None))[2] != "ideology":
                continue
            enables = [child for child in node.children if child.kind == "enable"]
            if len(enables) != 1 or "cost_multiplier" not in node.properties:
                raise ManifestError(f"Unexpected native ideological peace cost: {node.kind}")
            enabled = enables[0]
            changes.append((enabled.start, enabled.end, "enable = { always = no }"))
            start, end, _ = node.properties["cost_multiplier"]
            changes.append((start, end, "cost_multiplier = 1.0"))
        changed.append(node.kind)
    if relative == OPINIONS and set(changed) != PARTY_OPINIONS:
        raise ManifestError("Native opinion source is missing expected party relations")
    if relative == PEACE and not changed:
        raise ManifestError("Native peace source has no identifiable ideology cost definitions")
    for begin, end, value in sorted(changes, reverse=True):
        text = text[:begin] + value + text[end:]
    return text, changed


def write(output: Path, vanilla_root: str | Path | None = None) -> dict:
    root = Path(vanilla_root) if vanilla_root else ASSETS
    sources = {}
    for relative in (OPINIONS, PEACE):
        source = root / relative
        if not source.is_file():
            raise ManifestError(f"Strict native politics source is missing: {relative}")
        raw = source.read_bytes()
        converted, changed = neutralize(raw.decode("utf-8-sig"), relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(converted, encoding="utf-8", newline="\n")
        sources[relative] = {"source_sha256": hashlib.sha256(raw).hexdigest(),
                             "changed_definitions": changed}
    return {"files": list(sources), "sources": sources,
            "origin": "external_game_snapshot" if vanilla_root else "bundled/native_politics"}
