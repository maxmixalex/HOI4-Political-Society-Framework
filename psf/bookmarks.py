"""Static PSF snapshots through the front end's native bookmark history field.

The country selection screen has no documented scripted-GUI country context.
This adapter instead changes only bookmark `history` references and preserves
the original prose via localisation substitution. It does not pretend that the
map's hardcoded four-ideology pie can display arbitrary organization arrays.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import unicodedata

from . import charts
from .localization import LANGUAGES, write_localization
from .script import quoted

TOKEN = re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|[<>!]=|[=<>]|[^\s{}=<>!]+')
TEXT_ICON_SIZE = 12
LABEL_COLUMNS = 22


@dataclass(frozen=True)
class Field:
    key: str
    value: str | tuple["Field", ...]
    start: int
    end: int


def fields(text: str) -> tuple[Field, ...]:
    """Parse positions while retaining the original file for surgical changes."""
    tokens = []
    end = 0
    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError(f"Unrecognized bookmark syntax at offset {end}")
        token = match.group()
        end = match.end()
        if not token.isspace() and not token.startswith("#"):
            tokens.append((token, match.start(), match.end()))
    if end != len(text):
        raise ValueError("Unparsed bookmark text")
    index = 0

    def atom(value: str) -> str:
        return json.loads(value) if value.startswith('"') else value

    def body(nested: bool = False) -> tuple[Field, ...]:
        nonlocal index
        result = []
        while index < len(tokens):
            key, begin, finish = tokens[index]
            if key == "}":
                if not nested:
                    raise ValueError("Unexpected bookmark closing brace")
                index += 1
                return tuple(result)
            index += 1
            if index < len(tokens) and tokens[index][0] in {"=", "<", ">", "<=", ">=", "!="}:
                index += 1
                if index >= len(tokens):
                    raise ValueError(f"Missing bookmark value for {key}")
                token, start, finish = tokens[index]
                index += 1
                if token == "{":
                    value = body(True)
                    finish = tokens[index - 1][2]
                elif token in {"}", "=", "<", ">"}:
                    raise ValueError(f"Invalid bookmark value for {key}")
                else:
                    value = atom(token)
                result.append(Field(atom(key), value, start, finish))
            else:
                # Bare values in ideas/focuses/filters etc. are preserved. They
                # never provide the metadata this adapter changes.
                result.append(Field(atom(key), "", begin, finish))
        if nested:
            raise ValueError("Unclosed bookmark block")
        return tuple(result)

    return body()


def _value(items: tuple[Field, ...], key: str) -> str | None:
    values = [item.value for item in items if item.key == key and isinstance(item.value, str)]
    if len(values) > 1:
        raise ValueError(f"Ambiguous bookmark field {key}")
    return values[0] if values else None


def _compact_label(group: dict, language: str) -> str:
    """Keep authored short names readable beside two percentages in 380 pixels.

    Long names use the native textbox's normal wrapping after this conservative
    label bound. No image extends beyond the 16-pixel font's text row.
    """
    label = group.get("short_name", group["name"])[language]
    label = " ".join(label.split())
    width = lambda char: 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    if sum(width(char) for char in label) <= LABEL_COLUMNS:
        return label
    result, used = [], 0
    for char in label:
        if used + width(char) > LABEL_COLUMNS - 2:
            break
        result.append(char)
        used += width(char)
    return "".join(result) + "…"


def _color_key(output: Path, group: dict) -> dict:
    """Emit a text-sized color key, independently usable in front-end history."""
    stem = "psf_bookmark_key_" + group["id"]
    relative = "gfx/interface/psf/bookmarks/keys/" + group["id"] + ".tga"
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    rgb = charts.color(group)
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
                         TEXT_ICON_SIZE, TEXT_ICON_SIZE, 32, 0x28)
    target.write_bytes(header + bytes((rgb[2], rgb[1], rgb[0], 255)) * TEXT_ICON_SIZE ** 2)
    return {"sprite": "GFX_" + stem, "texture": relative,
            "width": TEXT_ICON_SIZE, "height": TEXT_ICON_SIZE, "color": list(rgb)}


def _history_text(snapshot: dict, original: str, language: str) -> str:
    header = "Support / Influence" if language == "english" else "支持率 / 影响力"
    lines = [header]
    for row in snapshot["rows"]:
        icon = row["sprite"].removeprefix("GFX_")
        lines.append(f"£{icon}£ {row['labels'][language]}  {row['support']:.1f}% / {row['influence']:.1f}%")
    if not snapshot["rows"]:
        lines.append("No active organizations" if language == "english" else "尚无活跃政治团体")
    return "\n".join(lines) + f"\n\n${original}$"


def generate_bookmark_previews(manifest: dict, output: Path, vanilla: Path | None = None) -> dict:
    """Wrap existing histories for declared country profiles, preserving DLCs.

    Country entries without a PSF profile are untouched, as are all availability
    gates, focuses, ideas, portraits, country order and original descriptions.
    Date-specific snapshots are compile-time data, never live campaign state.
    """
    profile_by_tag = {profile["tag"]: profile for profile in manifest["profiles"]}
    report = {
        "implementation": "native bookmark history with font-sized color keys and support/influence rows",
        "scope": "existing interesting-country history panels; map country-details pie is not an arbitrary-group chart",
        "profiles": sorted(profile_by_tag), "source_files": {}, "previews": [],
        "untouched_countries": [], "runtime_render_tested": False,
        "text_icon_size": TEXT_ICON_SIZE, "label_columns": LABEL_COLUMNS,
    }
    if not profile_by_tag:
        return report
    source = (vanilla / "common/bookmarks") if vanilla else Path(__file__).parent / "assets/native_bookmarks"
    if not source.is_dir():
        raise ValueError(f"Missing native bookmark directory: {source}")
    localisation = {language: {} for language in LANGUAGES}
    sprites: dict[str, dict] = {}
    snapshots: dict[str, dict] = {}
    untouched = set()
    for path in sorted(source.glob("*.txt")):
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        replacements = []
        for root in fields(text):
            if root.key != "bookmarks" or isinstance(root.value, str):
                continue
            for bookmark in root.value:
                if bookmark.key != "bookmark" or isinstance(bookmark.value, str):
                    continue
                date = _value(bookmark.value, "date")
                if date is None:
                    raise ValueError(f"Bookmark without date in {path}")
                parts = date.split(".")
                if len(parts) not in {3, 4} or not all(part.isdigit() for part in parts):
                    raise ValueError(f"Unsupported bookmark date {date!r}")
                day = ".".join(parts[:3])
                for country in bookmark.value:
                    if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", country.key) or isinstance(country.value, str):
                        continue
                    history_fields = [item for item in country.value if item.key == "history" and isinstance(item.value, str)]
                    if country.key not in profile_by_tag:
                        untouched.add(country.key)
                        continue
                    if len(history_fields) != 1:
                        raise ValueError(f"Expected exactly one history in {country.key} bookmark in {path}")
                    original = history_fields[0]
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", original.value):
                        raise ValueError(f"History must be a localisation key in {country.key}: {original.value!r}")
                    key_id = hashlib.sha256(f"{path.name}:{date}:{country.key}:{original.value}".encode()).hexdigest()[:12]
                    key = f"psf_bookmark_history_{country.key.lower()}_{key_id}"
                    preview_id = f"{country.key}:{day}"
                    if preview_id not in snapshots:
                        snapshot = charts.bookmark_values(manifest, profile_by_tag[country.key], day)
                        rows = []
                        for group in snapshot["organizations"]:
                            gid = group["id"]
                            support, influence = snapshot["support"][gid], snapshot["influence"][gid]
                            if support == 0 and influence == 0:
                                continue
                            if gid not in sprites:
                                sprites[gid] = _color_key(output, group)
                            rows.append({"group": gid, **sprites[gid], "support": support, "influence": influence,
                                         "labels": {language: _compact_label(group, language) for language in LANGUAGES}})
                        snapshots[preview_id] = {"support": snapshot["support"], "influence": snapshot["influence"], "rows": rows}
                    snapshot = snapshots[preview_id]
                    for language in LANGUAGES:
                        localisation[language][key] = _history_text(snapshot, original.value, language)
                    replacements.append((original.start, original.end, quoted(key)))
                    report["previews"].append({
                        "file": "common/bookmarks/" + path.name, "tag": country.key, "date": date,
                        "version": _value(country.value, "version"), "history_key": key,
                        "original_history_key": original.value, "snapshot": preview_id, **snapshot,
                    })
        if replacements:
            for start, end, replacement in sorted(replacements, reverse=True):
                text = text[:start] + replacement + text[end:]
            destination = output / "common/bookmarks" / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8", newline="\n")
            report["source_files"]["common/bookmarks/" + path.name] = hashlib.sha256(raw).hexdigest()
    if snapshots:
        definitions = ["spriteTypes = {"]
        for picture in sprites.values():
            definitions.append(f'spriteType = {{ name = {quoted(picture["sprite"])} texturefile = {quoted(picture["texture"])} noOfFrames = 1 legacy_lazy_load = no }}')
        definitions.append("}")
        interface = output / "interface"
        interface.mkdir(parents=True, exist_ok=True)
        (interface / "psf_bookmarks.gfx").write_text("\n".join(definitions) + "\n", encoding="utf-8")
        write_localization(output, "psf_bookmarks", localisation)
    report["untouched_countries"] = sorted(untouched)
    report["covered_countries"] = sorted({entry["tag"] for entry in report["previews"]})
    report["unique_snapshots"] = len(snapshots)
    report["unique_text_icons"] = len(sprites)
    report["unrepresented_profiles"] = sorted(set(profile_by_tag) - set(report["covered_countries"]))
    (output / "psf_bookmark_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
