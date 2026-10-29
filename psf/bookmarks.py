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

from . import charts
from .localization import LANGUAGES, write_localization
from .script import quoted

TOKEN = re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|[<>!]=|[=<>]|[^\s{}=<>!]+')


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


def generate_bookmark_previews(manifest: dict, output: Path, vanilla: Path | None = None) -> dict:
    """Wrap existing histories for declared country profiles, preserving DLCs.

    Country entries without a PSF profile are untouched, as are all availability
    gates, focuses, ideas, portraits, country order and original descriptions.
    Date-specific snapshots are compile-time data, never live campaign state.
    """
    profile_by_tag = {profile["tag"]: profile for profile in manifest["profiles"]}
    report = {
        "implementation": "native bookmark history localisation with static text icons",
        "scope": "existing interesting-country history panels; map country-details pie is not an arbitrary-group chart",
        "profiles": sorted(profile_by_tag), "source_files": {}, "previews": [],
        "untouched_countries": [], "runtime_render_tested": False,
    }
    if not profile_by_tag:
        return report
    source = (vanilla / "common/bookmarks") if vanilla else Path(__file__).parent / "assets/native_bookmarks"
    if not source.is_dir():
        raise ValueError(f"Missing native bookmark directory: {source}")
    localisation = {language: {} for language in LANGUAGES}
    sprites: dict[str, dict] = {}
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
                    if preview_id not in sprites:
                        sprites[preview_id] = charts.bookmark_artwork(manifest, profile_by_tag[country.key], day, output)
                    picture = sprites[preview_id]
                    text_icon = picture["sprite"].removeprefix("GFX_")
                    for language in LANGUAGES:
                        label = "Support       Influence" if language == "english" else "支持率         影响力"
                        localisation[language][key] = f"{label}\n£{text_icon}£\n\n${original.value}$"
                    replacements.append((original.start, original.end, quoted(key)))
                    report["previews"].append({
                        "file": "common/bookmarks/" + path.name, "tag": country.key, "date": date,
                        "version": _value(country.value, "version"), "history_key": key,
                        "original_history_key": original.value, "sprite": picture["sprite"],
                        "texture": picture["texture"], "support": picture["support"], "influence": picture["influence"],
                    })
        if replacements:
            for start, end, replacement in sorted(replacements, reverse=True):
                text = text[:start] + replacement + text[end:]
            destination = output / "common/bookmarks" / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8", newline="\n")
            report["source_files"]["common/bookmarks/" + path.name] = hashlib.sha256(raw).hexdigest()
    if sprites:
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
    report["unique_snapshots"] = len(sprites)
    report["unrepresented_profiles"] = sorted(set(profile_by_tag) - set(report["covered_countries"]))
    (output / "psf_bookmark_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
