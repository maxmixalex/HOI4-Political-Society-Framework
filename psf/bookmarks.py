"""Independent country-selection politics with untouched native histories."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from . import frontend

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
    """Generate independent politics and report native bookmark coverage.

    Original bookmark files, history keys, prose, DLC gates and portraits remain
    owned by the installed game. The selected country's native party field
    carries the date-specific political presentation in both selection panels.
    """
    presentation = frontend.generate(manifest, output)
    profile_by_tag = {profile["tag"]: profile for profile in manifest["profiles"]}
    report = {
        "implementation": presentation["implementation"],
        "scope": "native political information areas in both country-selection panels",
        "profiles": sorted(profile_by_tag), "source_files": {}, "previews": [],
        "untouched_countries": [], "runtime_render_tested": False,
        "history_overridden": False, "frontend": presentation,
    }
    source = (vanilla / "common/bookmarks") if vanilla else Path(__file__).parent / "assets/native_bookmarks"
    if not source.is_dir():
        raise ValueError(f"Missing native bookmark directory: {source}")
    snapshots, untouched = {}, set()
    for path in sorted(source.glob("*.txt")):
        raw = path.read_bytes()
        report["source_files"]["common/bookmarks/" + path.name] = hashlib.sha256(raw).hexdigest()
        for root in fields(raw.decode("utf-8-sig")):
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
                    if country.key not in profile_by_tag:
                        untouched.add(country.key)
                        continue
                    original = _value(country.value, "history")
                    if original is None:
                        raise ValueError(f"Expected a history in {country.key} bookmark in {path}")
                    profile = profile_by_tag[country.key]
                    boundary = None
                    for candidate in frontend.states(profile)[1:]:
                        if tuple(map(int, candidate.split("."))) <= tuple(map(int, day.split("."))):
                            boundary = candidate
                    preview_id = f"{country.key}:{day}"
                    if preview_id not in snapshots:
                        state = frontend.snapshot(manifest, profile, boundary)
                        snapshots[preview_id] = {
                            "support": state["support"], "influence": state["influence"],
                            "frontend_state": state["id"], "panel_key": "psf_frontend_panel_" + state["id"],
                            "ruling_group": state["ruling_group"]["id"] if state["ruling_group"] else None,
                            "regime": state["regime"]["id"],
                            "ideology": state["ideology"]["id"] if state["ideology"] else None,
                        }
                    report["previews"].append({
                        "file": "common/bookmarks/" + path.name, "tag": country.key, "date": date,
                        "version": _value(country.value, "version"), "history_key": original,
                        "original_history_key": original, "snapshot": preview_id, **snapshots[preview_id],
                    })
    report["untouched_countries"] = sorted(untouched)
    report["covered_countries"] = sorted({entry["tag"] for entry in report["previews"]})
    report["unique_snapshots"] = len(snapshots)
    report["unrepresented_profiles"] = sorted(set(profile_by_tag) - set(report["covered_countries"]))
    report["compiled_states"] = len(presentation["states"])
    (output / "psf_bookmark_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
