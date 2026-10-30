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
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from .engine_safety import MAX_SCRIPT_BYTES, inspect_build
    from . import native_history
except ImportError:  # Direct `python tools/ci/validate.py` invocation.
    from engine_safety import MAX_SCRIPT_BYTES, inspect_build
    import native_history

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


def declared_stock_textures() -> dict[str, list[dict]]:
    """Load pinned native declarations, not fabricated texture payloads.

    The script-only archive has no DDS bytes. Keep that limitation explicit:
    these imports classify CW113 dependency diagnostics only when validating
    with the same script-only cache. A real --vanilla run uses no imports.
    """
    manifest = json.loads((HERE / "stock-texture-imports.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise ValidationFailure("Unknown stock texture evidence format")
    textures = manifest["textures"]
    for texture, sources in textures.items():
        path = PurePosixPath(texture)
        if (not path.parts or path.is_absolute() or ".." in path.parts or path.parts[0] != "gfx"
                or path.suffix != ".dds" or "psf" in texture.lower() or not sources):
            raise ValidationFailure(f"Invalid external stock texture declaration: {texture}")
        for source in sources:
            source_path = PurePosixPath(source["source"])
            digest = manifest["source_files"].get(source["source"], "")
            declaration = re.fullmatch(r'texturefile\s*=\s*"([^"\n]+)"',
                                       source["declaration"], re.IGNORECASE)
            if (not source_path.parts or source_path.is_absolute() or ".." in source_path.parts
                    or source_path.parts[0] != "interface" or source_path.suffix != ".gfx"
                    or not re.fullmatch(r"[a-f0-9]{64}", digest)
                    or not isinstance(source["line"], int) or source["line"] < 1
                    or not source["sprite"] or not declaration or declaration[1] != texture):
                raise ValidationFailure(f"Incomplete native evidence for stock texture: {texture}")
    return textures


def classify_stock_texture_dependencies(diagnostics: list[dict], *,
                                        enabled: bool) -> tuple[list[dict], list[dict]]:
    """Separate exact, evidenced imports while preserving raw engine errors."""
    if not enabled:
        return diagnostics, []
    imports = declared_stock_textures()
    checked, dependencies = [], []
    for diagnostic in diagnostics:
        match = re.fullmatch(r"File (.+) not found, this is case sensitive",
                             diagnostic.get("message", ""))
        if (diagnostic.get("code") == "CW113"
                and diagnostic.get("severity", "").lower() == "error"
                and Path(diagnostic.get("file", "")).suffix.lower() == ".gfx"
                and match and match[1] in imports):
            dependencies.append({"diagnostic": diagnostic, "texture": match[1],
                                 "evidence": imports[match[1]]})
        else:
            checked.append(diagnostic)
    return checked, dependencies


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
        "declared_stock_texture": ("interface/probe.gfx", 'spriteTypes = { spriteType = { name = "GFX_psf_ci_external" texturefile = "gfx/interface/ideologies/democratic_group.dds" } }\n', "CW113"),
        "misspelled_stock_texture": ("interface/probe.gfx", 'spriteTypes = { spriteType = { name = "GFX_psf_ci_external" texturefile = "gfx/interface/ideologies/democratic_groupp.dds" } }\n', "CW113"),
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
            checked, dependencies = classify_stock_texture_dependencies(diagnostics, enabled=True)
            if name == "declared_stock_texture":
                if checked or len(dependencies) != 1:
                    raise ValidationFailure("Declared stock texture did not produce exactly one external dependency")
                strict, strict_dependencies = classify_stock_texture_dependencies(diagnostics, enabled=False)
                if not strict or strict_dependencies:
                    raise ValidationFailure("Full-install validation must retain missing stock textures")
            elif name == "misspelled_stock_texture" and (dependencies or not checked):
                raise ValidationFailure("A misspelled stock texture escaped the CWTools error gate")
            summary[name] = {"engine_exit_code": result, "gate_exit_code": result or int(bool(failures)), "diagnostic_codes": sorted(codes), "passed": True}
            if name in {"declared_stock_texture", "misspelled_stock_texture"}:
                summary[name]["external_stock_texture_dependencies"] = len(dependencies)
                summary[name]["remaining_diagnostics"] = len(checked)
                if name == "declared_stock_texture":
                    summary[name]["gate_exit_code"] = 0
    summary.update(self_test_native_history(binary, output))
    (output / "selftest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("CWTools positive and negative semantic controls passed.")


def self_test_native_history(binary: Path, output: Path) -> dict:
    """Real source/engine controls, including a new effect outside the baseline."""
    source = native_history.bootstrap.ASSETS / "PRC - ComChina.txt"
    relative = "history/countries/" + source.name
    raw = source.read_bytes()
    expected = native_history.bootstrap.patch_history(raw.decode("utf-8"))[0].encode("utf-8")
    history = native_history.reconstruct(relative, raw, expected)
    summary = {}
    with tempfile.TemporaryDirectory(prefix="psf-history-control-") as temporary:
        staged = Path(temporary)
        path = staged / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(expected)
        effects = staged / "common/scripted_effects/bootstrap.txt"
        effects.parent.mkdir(parents=True)
        effects.write_text("psf_history_bootstrap = { add_political_power = 0 }\n"
                           "psf_prepare_frontend = { add_political_power = 0 }\n", encoding="utf-8")
        baseline_result, baseline = native_history.run_baseline(
            invoke, binary, staged, output / "selftest-native-history-baseline.json", {relative: history})
        generated_result, generated = invoke(binary, staged, output / "selftest-native-history-generated.json")
        checked, inherited = native_history.classify(generated, baseline, staged, {relative: history})
        if not inherited or any(item.get("severity", "").lower() in {"error", "warning"} for item in checked):
            raise ValidationFailure("Exact original history + bootstrap did not match its genuine engine baseline")
        summary["native_history_exact_source"] = {"engine_exit_code": generated_result,
            "baseline_engine_exit_code": baseline_result, "gate_exit_code": 0,
            "inherited_diagnostics": len(inherited), "passed": True}
        # A recognized effect with an altered value is not a syntax failure,
        # but it is still unauthorized history drift and must fail byte proof.
        mutations = {
            "native_history_bootstrap_tamper": expected.replace(b"psf_history_bootstrap = yes", b"psf_history_bootstrap = no", 1),
            "native_history_source_tamper": expected.replace(b"state = 622", b"state = 623", 1),
        }
        for name, tampered in mutations.items():
            if tampered == expected:
                raise ValidationFailure(f"Native-history negative control did not mutate its target: {name}")
            try:
                native_history.reconstruct(relative, raw, tampered)
            except ValueError:
                summary[name] = {"gate_exit_code": 2, "rejected_before_engine": True, "passed": True}
            else:
                raise ValidationFailure(f"Native history reconstruction accepted {name}")
        # Even if byte proof were bypassed, a new effect on a PSF insertion
        # line cannot inherit an original source diagnostic. Run the real CLI.
        tampered = expected.replace(b"psf_history_bootstrap = yes", b"psf_ci_new_invalid_history_effect = yes", 1)
        path.write_bytes(tampered)
        result, diagnostics = invoke(binary, staged, output / "selftest-native-history-new-effect.json")
        checked, inherited = native_history.classify(diagnostics, baseline, staged, {relative: history})
        new_errors = [item for item in checked if item.get("severity", "").lower() == "error"
                      and "psf_ci_new_invalid_history_effect" in item.get("message", "")]
        if result == 0 or not new_errors:
            raise ValidationFailure("New PSF history effect escaped the exact-source diagnostic baseline")
        summary["native_history_new_effect"] = {"engine_exit_code": result, "gate_exit_code": result,
            "new_diagnostic_codes": sorted({item["code"] for item in new_errors}),
            "inherited_diagnostics": len(inherited), "passed": True}
    return summary


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
        for filename in ("summary.json", "cwtools.json", "stock-texture-dependencies.json", "engine-preflight.json",
                         "native-history-baseline.json", "inherited-native-history-diagnostics.json"):
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
            # Full byte reconstruction precedes both engine runs and every
            # inherited-diagnostic decision. A tampered insertion cannot earn
            # the source file's baseline merely by living in history/countries.
            verified_history = native_history.prepare(staged, args.root.resolve(), args.vanilla)
            result, diagnostics = invoke(binary, staged, args.reports / "cwtools.json", args.vanilla)
            # Keep the engine's complete unmodified report, including CW113.
            (args.reports / "cwtools.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
            checked, dependencies = classify_stock_texture_dependencies(diagnostics, enabled=args.vanilla is None)
            (args.reports / "stock-texture-dependencies.json").write_text(json.dumps(dependencies, indent=2) + "\n", encoding="utf-8")
            inherited, baseline_result, baseline_diagnostics = [], None, []
            if verified_history:
                baseline_result, baseline_diagnostics = native_history.run_baseline(
                    invoke, binary, staged, args.reports / "native-history-baseline.json", verified_history, args.vanilla)
                checked, inherited = native_history.classify(checked, baseline_diagnostics, staged, verified_history)
            (args.reports / "inherited-native-history-diagnostics.json").write_text(json.dumps(inherited, indent=2) + "\n", encoding="utf-8")
            write_annotations(checked, staged, args.root.resolve())
            errors = sum(d.get("severity", "").lower() == "error" for d in checked)
            warnings = sum(d.get("severity", "").lower() == "warning" for d in checked)
            raw_errors = sum(d.get("severity", "").lower() == "error" for d in diagnostics)
            # Exit 1 means ordinary diagnostics. Crashes/empty discovery/other
            # nonzero statuses cannot be recategorized as dependency-only.
            dependency_only = result == 1 and bool(dependencies or inherited) and not errors and not warnings
            gate_exit = 0 if dependency_only else result or int(bool(errors or warnings))
            summary = {
                "engine": "cwtools 2.3.0", "generated_files": count,
                "declared_stock_localisation_imports": imports,
                "errors": errors, "warnings": warnings, "exit_code": gate_exit,
                "validation_errors": errors, "validation_warnings": warnings,
                "raw_engine_errors": raw_errors, "raw_engine_exit_code": result,
                "raw_engine_warnings": sum(d.get("severity", "").lower() == "warning" for d in diagnostics),
                "external_stock_texture_dependencies": len(dependencies),
                "external_stock_texture_paths": len({item["texture"] for item in dependencies}),
                "stock_texture_payloads_bundled": False,
                "native_history_verified_files": len(verified_history),
                "native_history_baseline_exit_code": baseline_result,
                "inherited_native_history_diagnostics": len(inherited),
                "inherited_native_history_errors": sum(item["diagnostic"].get("severity", "").lower() == "error" for item in inherited),
                "inherited_native_history_warnings": sum(item["diagnostic"].get("severity", "").lower() == "warning" for item in inherited),
                "inherited_native_history_info": sum(item["diagnostic"].get("severity", "").lower() in {"info", "information"} for item in inherited),
                "engine_preflight": {key: preflight[key] for key in ("checked_files", "native_gui_files", "errors")},
                "runtime_launch_tested": False,
            }
            (args.reports / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(summary))
            if gate_exit:
                return gate_exit
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
