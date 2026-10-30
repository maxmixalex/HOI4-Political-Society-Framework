"""Preserving country-history patches for immediate vanilla initialization.

Country history is available before the first day is advanced. We patch the
original filename and append at each top-level date boundary, preserving every
original statement. We never create a competing, abbreviated TAG history file.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from .model import ManifestError


ASSETS = Path(__file__).resolve().parent / "assets" / "native_history"
MARKER = "# PSF immediate country-history bootstrap"
TOKEN = re.compile(r'#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')
KNOWN_MISSING_FINAL_BRACE = {"f26704f9311af80a35a72d7620f0e991eb0682f038ded4c663f293b4f60ca3a1"}
REPAIR = "\n# PSF source repair: close the supplied NOR 1939 history block.\n}\n"
KNOWN_EMPTY_BRANCH = '\tif = {\n\t\tlimit = { not = { has_dlc = "Man the Guns" } }\n\t\t# Ship variants #\n\t}\n'
EMPTY_BRANCH_REPAIR = ("\t# PSF source repair: preserve the empty pre-MtG branch as comments.\n" +
                       "".join("# " + line for line in KNOWN_EMPTY_BRANCH.splitlines(keepends=True)))


def patch_history(text: str, *, frontend: bool = True) -> tuple[str, int]:
    if MARKER in text:
        raise ManifestError("Country-history input already contains a PSF bootstrap patch; use the original source")
    source_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Keep input bytes/hashes in the source bundle, but generated script files
    # obey the project's no-BOM engine preflight rule.
    text = text.removeprefix("\ufeff")
    if source_digest in KNOWN_MISSING_FINAL_BRACE:
        # The exact user-supplied Norway source ends with 88 opening and 87
        # closing braces. Do not guess repairs for other sources or versions.
        if text.count(KNOWN_EMPTY_BRANCH) != 1:
            raise ManifestError("Known Norway source repair does not match the original empty branch")
        text = text.replace(KNOWN_EMPTY_BRANCH, EMPTY_BRANCH_REPAIR, 1) + REPAIR
    # History may contain anonymous lists of blocks (equipment/technology),
    # unlike GUI trees. Track every brace, including those without `name =`.
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith("#")]
    stack: list[bool] = []
    dated: list[int] = []
    for index, token in enumerate(tokens):
        if token.group() == "{":
            is_date = (not stack and index >= 2 and tokens[index - 1].group() == "=" and
                       bool(re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}", tokens[index - 2].group())))
            stack.append(is_date)
        elif token.group() == "}":
            if not stack:
                raise ManifestError("Original country history has an unmatched closing brace")
            if stack.pop():
                dated.append(token.start())
    if stack:
        raise ManifestError("Original country history has an unmatched opening brace")
    newline = "\r\n" if "\r\n" in text else "\n"
    calls = [MARKER, "psf_history_bootstrap = yes"]
    if frontend:
        calls.append("psf_prepare_frontend = yes")
    for closing in sorted(dated, reverse=True):
        insertion = newline + newline.join("\t" + line for line in calls) + newline
        text = text[:closing] + insertion + text[closing:]
    # A terminal root call covers countries with no dated blocks and engines
    # which evaluate root effects after the selected dated history blocks.
    text += newline + newline.join(calls) + newline
    return text, len(dated)


def write_bootstrap_history(manifest: dict, output: Path, vanilla_path: str | Path | None = None) -> dict:
    if manifest["settings"].get("mechanics_mode", "compat") != "strict":
        return {"enabled": False, "source": None, "files": [], "country_count": 0}
    source_dir = Path(vanilla_path) / "history/countries" if vanilla_path else ASSETS
    sources = sorted(source_dir.glob("*.txt"))
    if not sources:
        raise ManifestError(f"No original country history found in {source_dir}")
    destination = Path(output) / "history/countries"
    destination.mkdir(parents=True, exist_ok=True)
    result = []
    combined = hashlib.sha256()
    for source in sources:
        if not re.match(r"[A-Z0-9]{3}(?:\W|_)", source.name, re.I):
            raise ManifestError(f"Country history filename has no native three-character tag: {source.name}")
        raw = source.read_bytes()
        # Decode without discarding provenance; patch_history normalizes the
        # output BOM and records only the known, reversible source repairs.
        original = raw.decode("utf-8")
        text, date_blocks = patch_history(original)
        (destination / source.name).write_bytes(text.encode("utf-8"))
        digest = hashlib.sha256(raw).hexdigest()
        combined.update(source.name.encode("utf-8") + b"\0" + raw)
        record = {"file": "history/countries/" + source.name, "sha256": digest,
                  "original_bytes": len(raw), "dated_boundaries": date_blocks,
                  "source_had_bom": raw.startswith(b"\xef\xbb\xbf"),
                  "encoding_normalized": raw.startswith(b"\xef\xbb\xbf")}
        if digest in KNOWN_MISSING_FINAL_BRACE:
            record["known_source_repair"] = ["append_missing_final_date_block_closing_brace",
                                             "preserve_empty_pre_mtg_branch_as_comments"]
        result.append(record)
    return {"enabled": True, "source": "external_game_snapshot/history/countries" if vanilla_path else "bundled/native_history",
            "source_kind": "explicit_game_snapshot" if vanilla_path else "bundled_user_supplied_snapshot",
            "source_sha256": combined.hexdigest(), "country_count": len(sources), "files": result,
            "entrypoint": "psf_history_bootstrap", "requires_snapshot_matching_game": True}
