"""Verify generic political overrides before comparing unchanged-source errors."""
from __future__ import annotations

import json
from pathlib import Path

try:
    from .native_history import NativeHistory, digest, equal_line_map
except ImportError:
    from native_history import NativeHistory, digest, equal_line_map
from psf import native_rules

# Independent pins for the exact user-supplied source snapshot. Build metadata
# cannot bless an altered source by replacing its own expected hash.
PINS = {
    native_rules.OPINIONS: "024c8c8ea5359b7af0e7b8659a1ab4d95d70ddcae711496a2c1e45438c01dc99",
    native_rules.PEACE: "9d518edba257f6704acdc79bd79a182117871a6280514f1557fef5308422c2e8",
    native_rules.OCCUPATION: "b0e776a177eb7ceb186178d873cb6955fad5a9c56cd299292a62e00397f9c823",
}


def reconstruct(relative: str, raw: bytes, generated: bytes) -> NativeHistory:
    if relative not in PINS:
        raise ValueError(f"Unsupported native politics baseline path: {relative}")
    original = raw.decode("utf-8-sig")
    expected, changed = native_rules.neutralize(original, relative)
    if generated != expected.encode("utf-8"):
        raise ValueError(f"Native politics is not the exact source + adapter output: {relative}")
    # An unchanged-looking line inside a rewritten definition is not an
    # unchanged definition. Exclude those blocks conservatively, including
    # inline siblings sharing the line: a line-only diagnostic cannot identify
    # which column or ancestor produced the error. Sequence alignment alone
    # can otherwise match repeated values from another source block.
    from psf.ui import gui_nodes

    def rewritten_lines(text: str) -> set[int]:
        lines: set[int] = set()
        for node in gui_nodes(text):
            if node.kind in changed and (node.parent is None or node.parent.parent is None):
                first = text.count("\n", 0, node.start) + 1
                last = text.count("\n", 0, node.end - 1) + 1
                lines.update(range(first, last + 1))
        return lines

    before, after = rewritten_lines(original), rewritten_lines(expected)
    mapping = {new: old for new, old in equal_line_map(original, expected).items()
               if new not in after and old not in before}
    return NativeHistory(relative, digest(raw), original, original, generated,
                         mapping, equal_line_map(original, original))


def prepare(staged: Path, build_root: Path, vanilla: Path | None = None) -> dict[str, NativeHistory]:
    report = json.loads((build_root / "build-manifest.json").read_text(encoding="utf-8"))
    metadata = report.get("native_mechanics", {}).get("generic_adapters", {})
    if not metadata:
        return {}
    records = metadata.get("sources", {})
    if set(records) != set(PINS) or set(metadata.get("files", [])) != set(PINS):
        raise ValueError("Native politics inventory differs from its exact supported source paths")
    if metadata.get("origin") == "bundled/native_politics":
        source_root, expected_hashes = native_rules.ASSETS, PINS
    elif metadata.get("origin") == "external_game_snapshot" and vanilla:
        source_root = vanilla
        expected_hashes = {path: record["source_sha256"] for path, record in records.items()}
    else:
        raise ValueError("Native politics baseline needs the pinned bundle or original --vanilla source")
    verified = {}
    for relative in sorted(records):
        raw = (source_root / relative).read_bytes()
        source_hash = digest(raw)
        if source_hash != expected_hashes[relative] or source_hash != records[relative]["source_sha256"]:
            raise ValueError(f"Original native politics hash mismatch: {relative}")
        _, changed = native_rules.neutralize(raw.decode("utf-8-sig"), relative)
        if records[relative].get("changed_definitions") != changed:
            raise ValueError(f"Native politics changed-definition inventory mismatch: {relative}")
        verified[relative] = reconstruct(relative, raw, (staged / relative).read_bytes())
    return verified
