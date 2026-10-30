"""Checks for HOI4 loader hazards which a tolerant CWT parser can miss.

This supplements CWTools; it is not a script parser or an in-game launch test.
In particular, the game treats a BOM before ``guiTypes`` as part of the token,
although the pinned Rust CLI accepts that file.
"""

from __future__ import annotations

from pathlib import Path
import re

UTF8_BOM = b"\xef\xbb\xbf"
MAX_SCRIPT_BYTES = 2 * 1024 * 1024
GAME_TEXT_SUFFIXES = {".txt", ".gui", ".gfx", ".yml", ".mod", ".lua", ".asset"}
NATIVE_GUI_WINDOWS = {
    "countrypoliticsview.gui": "countrypoliticsview",
    "countrydiplomacyview.gui": "countrydiplomacyview",
    "frontendgamesetupview.gui": "frontendgamesetupview",
}
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}=]|[^\s{}=#"]+')


def gui_windows(text: str) -> set[str]:
    """Return independent window names, ignoring comments and nested impostors."""
    tokens = [m.group() for m in TOKEN.finditer(text) if not m.group().startswith("#")]
    depth = 0
    in_window = False
    windows = set()
    for index, token in enumerate(tokens):
        if token == "{":
            depth += 1
            if depth == 2:
                in_window = index >= 2 and tokens[index - 2].lower() in {
                    "containerwindowtype", "windowtype", "eu3dialogtype",
                }
        elif token == "}":
            if depth == 2:
                in_window = False
            depth -= 1
        elif depth == 2 and in_window and token == "name":
            if index + 2 < len(tokens) and tokens[index + 1] == "=":
                windows.add(tokens[index + 2].strip('"'))
    return windows


def file_findings(path: Path) -> list[dict[str, str | int]]:
    """Inspect original bytes, before any ``utf-8-sig`` decode or overlay."""
    if path.suffix.lower() not in GAME_TEXT_SUFFIXES:
        return []
    findings: list[dict[str, str | int]] = []

    def fail(code: str, message: str) -> None:
        findings.append({"file": str(path), "line": 1, "severity": "error", "code": code, "message": message})

    raw = path.read_bytes()
    if path.suffix.lower() in {".txt", ".gui", ".gfx"} and len(raw) > MAX_SCRIPT_BYTES:
        fail("PSF_DISCOVERY_SIZE", "Script exceeds the pinned CWTools 2 MiB discovery limit and would escape semantic validation; split complete definitions into smaller files.")
    localisation = path.suffix.lower() == ".yml" and "localisation" in path.parts
    if localisation:
        if not raw.startswith(UTF8_BOM):
            fail("PSF_ENCODING", "HOI4 localisation requires UTF-8 with BOM.")
    elif raw.startswith(UTF8_BOM):
        fail("PSF_ENCODING", "HOI4 scripts, GUI/GFX and descriptors require UTF-8 without BOM; the engine can reject the root token.")
    try:
        text = raw.decode("utf-8-sig" if localisation else "utf-8")
    except UnicodeDecodeError:
        fail("PSF_ENCODING", "Game text is not valid UTF-8.")
        return findings
    if "\x00" in text:
        fail("PSF_ENCODING", "NUL bytes are not valid game text; check for UTF-16 or a damaged file.")
    if localisation:
        match = re.search(r"_l_([a-z_]+)\.yml$", path.name)
        first_content = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")), "")
        if not match or first_content != f"l_{match.group(1)}:":
            fail("PSF_LOCALISATION_HEADER", "Localisation filename and language header must agree (for example *_l_english.yml and l_english:).")
    if path.suffix.lower() == ".gui":
        tokens = [m.group() for m in TOKEN.finditer(text) if not m.group().startswith("#")]
        if tokens[:3] != ["guiTypes", "=", "{"]:
            fail("PSF_GUI_ROOT", "Interface file must begin with the guiTypes root after comments and whitespace.")
        required = NATIVE_GUI_WINDOWS.get(path.name)
        if required and required not in gui_windows(text):
            fail("PSF_NATIVE_GUI", f"Missing independent native window {required!r}; replacing this file without its engine window can crash HOI4.")
    elif path.suffix.lower() == ".gfx" and path.name.startswith("psf_"):
        # Our generated sprite files always use this root. The supplied CWT
        # indexes sprite declarations under *any* root to cover vanilla's
        # bitmapfonts imports, so it cannot reject a misspelled engine token.
        # Restrict this guard to PSF-owned files rather than forbidding other
        # legitimate native GFX roots in third-party files.
        tokens = [m.group() for m in TOKEN.finditer(text) if not m.group().startswith("#")]
        if tokens[:3] != ["spriteTypes", "=", "{"]:
            fail("PSF_GFX_ROOT", "Generated PSF sprite file must begin with the spriteTypes root after comments and whitespace.")
    elif path.suffix.lower() == ".mod":
        for version in re.findall(r'(?m)^\s*supported_version\s*=\s*"([^"\n]*)"', text):
            if not re.fullmatch(r"\d+\.\d+\.(?:\d+(?:\.\d+)?|\*)", version):
                fail("PSF_SUPPORTED_VERSION", f"Unsupported descriptor version {version!r}; use major.minor.patch, major.minor.patch.build, or major.minor.*.")
    return findings


def inspect_build(root: Path, names: tuple[str, ...]) -> dict:
    """Check each shipped layer, including the launcher's outer .mod files."""
    files: list[Path] = []
    for name in names:
        files.append(root / f"{name}.mod")
        mod = root / name
        files.append(mod / "descriptor.mod")
        files.extend(p for p in sorted(mod.rglob("*")) if p.is_file() and p != mod / "descriptor.mod" and not any(part.startswith(".") for part in p.relative_to(mod).parts))
    diagnostics = []
    checked = 0
    native_windows = 0
    for path in files:
        if not path.is_file():
            diagnostics.append({"file": str(path), "line": 1, "severity": "error", "code": "PSF_MISSING_FILE", "message": "Missing generated mod descriptor."})
            continue
        if path.suffix.lower() not in GAME_TEXT_SUFFIXES:
            continue
        checked += 1
        native_windows += int(path.name in NATIVE_GUI_WINDOWS)
        diagnostics.extend(file_findings(path))
    return {
        "checked_files": checked,
        "native_gui_files": native_windows,
        "errors": len(diagnostics),
        "diagnostics": diagnostics,
        "runtime_launch_tested": False,
    }
