#!/usr/bin/env python3
"""Run the pinned Rust CWTools engine against a layered, generated PSF build.

This is semantic CWT validation, not a substitute bracket-counting linter.  The
negative controls deliberately exercise semantics, references and syntax.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from .engine_safety import MAX_SCRIPT_BYTES, inspect_build
except ImportError:  # Direct `python tools/ci/validate.py` invocation.
    from engine_safety import MAX_SCRIPT_BYTES, inspect_build

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
VENDOR = HERE / "vendor"
LOCK = HERE / "toolchain.lock.json"
# MAX_SCRIPT_BYTES is measured on the supplied CLI: 2,097,152 bytes are
# discovered, +1 is skipped. The same boundary is used by both gates.


class ValidationFailure(RuntimeError):
    pass


def mod_names(root: Path) -> tuple[str, str]:
    manifest = root / "build-manifest.json"
    if manifest.is_file():
        content_id = json.loads(manifest.read_text(encoding="utf-8"))["content_id"]
    else:
        content_id = "psf_vanilla_example"
    if not isinstance(content_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", content_id) or content_id == "psf":
        raise ValidationFailure(f"Invalid generated content_id: {content_id!r}")
    return "psf", content_id


def verify_toolchain() -> Path:
    """Fail closed on missing or modified validation inputs."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for name, expected in lock["sha256"].items():
        path = HERE / name
        if not path.is_file():
            raise ValidationFailure(f"Missing pinned toolchain input: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValidationFailure(f"SHA-256 mismatch for {name}: {actual}")
    pinned_rules = {name for name in lock["sha256"] if name.endswith(".cwt")}
    actual_rules = {p.relative_to(HERE).as_posix() for p in (VENDOR / "rules").rglob("*.cwt")}
    if pinned_rules != actual_rules:
        raise ValidationFailure("Rules were added or removed without a toolchain lock update")
    binary = VENDOR / "cwtools-linux-x86_64"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValidationFailure("The pinned CLI is Linux x86-64. Use WSL2, a Linux container, or GitHub Actions.")
    binary.chmod(binary.stat().st_mode | 0o111)
    version = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if version != "cwtools " + lock["engine"]["version"]:
        raise ValidationFailure(f"Unexpected engine version: {version}")
    return binary


def merge_mods(root: Path, destination: Path) -> int:
    """Overlay dependency first and example second, as the launcher does."""
    count = 0
    for name in mod_names(root):
        mod = root / name
        if not (mod / "descriptor.mod").is_file():
            raise ValidationFailure(f"Missing generated mod descriptor: {mod / 'descriptor.mod'}")
        for source in sorted(mod.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(mod)
            if any(part.startswith(".") for part in relative.parts):
                continue
            if source.suffix in {".txt", ".gui", ".gfx"} and source.stat().st_size > MAX_SCRIPT_BYTES:
                raise ValidationFailure(f"Script exceeds CWTools' 2 MiB discovery limit: {source}; split complete top-level definitions across files")
            if relative.parts[:2] == ("common", "scripted_effects") and re.search(r"\$[A-Za-z_][A-Za-z0-9_]*\$", source.read_text(encoding="utf-8-sig")):
                raise ValidationFailure(f"Unsupported parameter macro leaked into generated HOI4 effects: {source}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if source.suffix in {".txt", ".gui", ".gfx", ".yml", ".mod"}:
                count += 1
    if count < 3:
        raise ValidationFailure("Generated output is empty or incomplete")
    return count


def add_declared_stock_imports(staged: Path) -> int:
    """Resolve only existing imported stock UI keys absent from the script pack.

    These are dependency declarations, never PSF translations and never shipped
    in a mod.  The manifest records the source of every key.  It cannot declare
    new psf_* names, so missing PSF localisation remains a real CWTools error.
    """
    imports: dict[str, list] = {}
    for filename in ("stock-ui-imports.json", "stock-bookmark-imports.json"):
        manifest_path = HERE / filename
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, sources in manifest["localisation_keys"].items():
                if not sources:
                    raise ValidationFailure(f"Missing source evidence for external localisation declaration: {key}")
                imports.setdefault(key, []).extend(sources)
    if not imports:
        return 0
    for key, sources in imports.items():
        if key.lower().startswith("psf_") or not sources:
            raise ValidationFailure(f"Invalid external localisation declaration: {key}")
    languages: set[str] = set()
    for path in staged.rglob("*.yml"):
        header = path.read_text(encoding="utf-8-sig").splitlines()[0]
        match = re.fullmatch(r"l_([a-z_]+):\s*", header)
        if match:
            languages.add(match.group(1))
    for language in sorted(languages):
        path = staged / "localisation" / language / f"__cwtools_stock_imports_l_{language}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"l_{language}:\n" + "".join(f' {key}:0 "External base-game key"\n' for key in sorted(imports)),
            encoding="utf-8-sig",
        )
    return len(imports)


def invoke(binary: Path, mod: Path, report: Path, vanilla: Path | None = None) -> tuple[int, list[dict]]:
    command = [
        str(binary), "validate", "--config", str(HERE / "cwtools.toml"),
        "--game", "hoi4", "--directory", str(mod),
        "--rules", str(VENDOR / "rules"), "--report-type", "json", "--output-file", str(report),
    ]
    if vanilla is None:
        command.extend(["--vanilla-cache", str(VENDOR / "vanilla-symbols.cwv")])
    else:
        command.extend(["--vanilla", str(vanilla)])
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if not report.is_file():
        raise ValidationFailure(f"CWTools did not write a diagnostic report (exit {result.returncode})")
    try:
        diagnostics = json.loads(report.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValidationFailure(f"CWTools wrote an unreadable report: {exc}") from exc
    if not isinstance(diagnostics, list):
        raise ValidationFailure("CWTools report format changed; expected a diagnostic array")
    return result.returncode, diagnostics


def self_test(binary: Path, output: Path) -> None:
    """Prove the actual CWT engine rejects invalid, parseable scripts."""
    script_path = "common/scripted_effects/probe.txt"
    cases = {
        "valid": (script_path, "psf_ci_valid = { add_political_power = 1 }\n", None),
        "unknown_effect": (script_path, "psf_ci_bad = { psf_ci_unknown_engine_effect = 1 }\n", "CW263"),
        "wrong_value": (script_path, "psf_ci_bad = { set_politics = { elections_allowed = perhaps } }\n", None),
        "broken_syntax": (script_path, "psf_ci_bad = { add_political_power = 1\n", None),
        "known_stock_sprite": ("interface/probe.gui", 'guiTypes = { containerWindowType = { name = psf_ci_ui background = { name = icon spriteType = "SandboxFloaterBackground" } } }\n', None),
        "missing_sprite": ("interface/probe.gui", 'guiTypes = { containerWindowType = { name = psf_ci_ui background = { name = icon spriteType = "GFX_psf_ci_undefined_sprite" } } }\n', "CW500"),
        "missing_localisation": (script_path, "psf_ci_bad = { custom_effect_tooltip = psf_ci_missing_key }\n", "CW100"),
        "scripted_localisation_trigger": ("common/scripted_localisation/probe.txt", 'defined_text = { name = PSFCIText text = { trigger = { psf_ci_unknown_trigger = yes } localization_key = "Literal string" } }\n', "CW263"),
        "wrong_trigger_value": ("common/scripted_triggers/probe.txt", "psf_ci_bad_trigger = { always = perhaps }\n", "CW240"),
        "known_equipment_category": ("common/scripted_triggers/probe.txt", "psf_ci_category = { infantry > 0.5 }\n", None),
    }
    summary = {}
    with tempfile.TemporaryDirectory(prefix="psf-cwtools-selftest-") as temp:
        temp_root = Path(temp)
        for name, (relative_path, script, expected_code) in cases.items():
            mod = temp_root / name
            path = mod / relative_path
            path.parent.mkdir(parents=True)
            path.write_text(script, encoding="utf-8")
            if name == "missing_localisation":
                localisation = mod / "localisation/english/probe_l_english.yml"
                localisation.parent.mkdir(parents=True)
                localisation.write_text('l_english:\n psf_ci_defined_key:0 "Known"\n', encoding="utf-8-sig")
            result, diagnostics = invoke(binary, mod, output / f"selftest-{name}.json")
            failures = [d for d in diagnostics if d.get("severity", "").lower() in {"error", "warning"}]
            codes = {d["code"] for d in failures}
            if name in {"valid", "known_stock_sprite", "known_equipment_category"}:
                if result != 0 or failures:
                    raise ValidationFailure(f"Positive CWTools control failed: {diagnostics}")
            elif not failures or (expected_code and expected_code not in codes) or (name != "missing_localisation" and result == 0):
                raise ValidationFailure(f"CWTools failed to reject {name}: exit={result}, diagnostics={diagnostics}")
            summary[name] = {"engine_exit_code": result, "gate_exit_code": result or int(bool(failures)), "diagnostic_codes": sorted(codes), "passed": True}
    (output / "selftest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("CWTools positive and negative semantic controls passed.")


def write_annotations(diagnostics: list[dict], staged: Path, root: Path) -> None:
    for diagnostic in diagnostics:
        severity = diagnostic.get("severity", "info").lower()
        filename = diagnostic.get("file", "")
        try:
            relative = Path(filename).relative_to(staged)
            owner = next((root / name / relative for name in reversed(mod_names(root)) if (root / name / relative).exists()), root / relative)
            filename = str(owner)
        except ValueError:
            pass
        text = f"{diagnostic.get('code', '?')}: {diagnostic.get('message', '')}"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            kind = "error" if severity == "error" else "warning" if severity == "warning" else "notice"
            escaped = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            escaped_file = filename.replace("%", "%25").replace(",", "%2C").replace(":", "%3A")
            print(f"::{kind} file={escaped_file},line={diagnostic.get('line', 1)}::{escaped}")
        else:
            print(f"{filename}:{diagnostic.get('line', 1)}: {severity}: {text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO / "dist", help="Directory containing both generated mod roots")
    parser.add_argument("--reports", type=Path, default=REPO / "build" / "validation")
    parser.add_argument("--vanilla", type=Path, help="Optional full licensed installation; replaces bundled script-symbol cache")
    parser.add_argument("--self-test", action="store_true", help="Also prove semantic and syntax failures are rejected")
    parser.add_argument("--self-test-only", action="store_true")
    parser.add_argument("--preflight-only", action="store_true", help="Check raw encodings, launcher versions and required native windows without invoking CWTools")
    args = parser.parse_args(argv)
    args.reports.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an older successful report beside it.
    if not args.self_test_only:
        for filename in ("summary.json", "cwtools.json", "engine-preflight.json"):
            (args.reports / filename).unlink(missing_ok=True)
    try:
        preflight = None
        if not args.self_test_only:
            preflight = inspect_build(args.root.resolve(), mod_names(args.root))
            (args.reports / "engine-preflight.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
            for diagnostic in preflight["diagnostics"]:
                print(f"{diagnostic['file']}:1: error: {diagnostic['code']}: {diagnostic['message']}", file=sys.stderr)
            if preflight["errors"]:
                raise ValidationFailure(f"HOI4 engine preflight rejected {preflight['errors']} loader hazard(s); see engine-preflight.json")
            print(f"HOI4 engine preflight passed: {preflight['checked_files']} text files, {preflight['native_gui_files']} native GUI files.")
            if args.preflight_only:
                return 0
        binary = verify_toolchain()
        if args.self_test or args.self_test_only:
            self_test(binary, args.reports)
        if args.self_test_only:
            return 0
        with tempfile.TemporaryDirectory(prefix="psf-cwtools-") as temp:
            staged = Path(temp)
            count = merge_mods(args.root.resolve(), staged)
            imports = 0 if args.vanilla else add_declared_stock_imports(staged)
            result, diagnostics = invoke(binary, staged, args.reports / "cwtools.json", args.vanilla)
            (args.reports / "cwtools.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
            write_annotations(diagnostics, staged, args.root.resolve())
            errors = sum(d.get("severity", "").lower() == "error" for d in diagnostics)
            warnings = sum(d.get("severity", "").lower() == "warning" for d in diagnostics)
            summary = {
                "engine": "cwtools 2.3.0", "generated_files": count,
                "declared_stock_localisation_imports": imports,
                "errors": errors, "warnings": warnings, "exit_code": result,
                "engine_preflight": {key: preflight[key] for key in ("checked_files", "native_gui_files", "errors")},
                "runtime_launch_tested": False,
            }
            (args.reports / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(summary))
            if result != 0 or errors or warnings:
                return result if result != 0 else 1
        return 0
    except (OSError, KeyError, ValueError, subprocess.SubprocessError, ValidationFailure) as exc:
        (args.reports / "summary.json").write_text(json.dumps({
            "status": "failed", "exit_code": 2, "message": str(exc),
            "runtime_launch_tested": False,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"PSF CWTools validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
