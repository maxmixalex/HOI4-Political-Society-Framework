"""Reproducible framework and dependent content mod builds."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
import tempfile
import zipfile

from . import __version__
from . import bookmarks, bootstrap, gameplay, icons, identity, localization, mechanics, modifiers, runtime
from .model import load, profiles
from .script import quoted

FRAMEWORK_NAME = "Political Society Framework"


def write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_effect_chunks(root: Path, text: str, max_bytes: int = 900_000, *,
                        directory: str = "common/scripted_effects", prefix: str = "10_psf_registry") -> None:
    """Keep complete PSF definitions together, below the tool discovery limit."""
    matches = list(re.finditer(r"^psf_[a-zA-Z0-9_]+ = \{$", text, re.M))
    starts = [m.start() for m in matches] + [len(text)]
    chunk = text[:starts[0]] if matches else text
    index = 0
    for begin, end in zip(starts, starts[1:]):
        effect = text[begin:end]
        if len(effect.encode()) > max_bytes:
            raise ValueError("One script definition exceeds the safe file size; split the profile into smaller declarations")
        if chunk and len((chunk + effect).encode()) > max_bytes:
            write(root, f"{directory}/{prefix}_{index:03}.txt", chunk)
            chunk = ""
            index += 1
        chunk += effect
    if chunk:
        write(root, f"{directory}/{prefix}_{index:03}.txt", chunk)


def descriptor(name: str, *, dependency: bool = False, launcher_path: str | None = None,
               supported_version: str | None = None) -> str:
    lines = [f"version={quoted(__version__)}", 'tags={ "Gameplay" "Alternative History" }', f"name={quoted(name)}"]
    # This optional launcher hint is not an engine compatibility guarantee. The
    # supplied script snapshot has no version manifest, so do not invent one.
    # In particular, the engine rejects the previously emitted `1.*`.
    if supported_version is not None:
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.(?:[0-9]+(?:\.[0-9]+)?|\*)", supported_version):
            raise ValueError("supported_version must be major.minor.patch, major.minor.patch.build, or major.minor.*")
        lines.append("supported_version=" + quoted(supported_version))
    if dependency:
        lines.append("dependencies={ " + quoted(FRAMEWORK_NAME) + " }")
    if launcher_path:
        lines.append("path=" + quoted(launcher_path))
    return "\n".join(lines) + "\n"


def compile_manifest(manifest_path: str | Path, output: str | Path, *, vanilla: str | Path | None = None,
                     supported_version: str | None = None) -> dict:
    manifest_path, output = Path(manifest_path), Path(output)
    manifest = load(manifest_path)
    for name in ("psf", manifest["id"]):
        target = (output / name).resolve()
        if Path(__file__).resolve().is_relative_to(target) or manifest_path.resolve().is_relative_to(target):
            raise ValueError(f"Output would overwrite authoring source: {target}; choose a separate build directory")
    output.mkdir(parents=True, exist_ok=True)
    # Build outside the destination; validation errors cannot partially replace a
    # working pack. Only PSF's known output directories are replaced on success.
    with tempfile.TemporaryDirectory(prefix="psf-build-") as temporary:
        staging = Path(temporary)
        framework = staging / "psf"
        content = staging / manifest["id"]
        for mod in (framework, content):
            for notice in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
                write(mod, notice, (Path(__file__).parent / "assets" / notice).read_text(encoding="utf-8"))
        write(framework, "descriptor.mod", descriptor(FRAMEWORK_NAME, supported_version=supported_version))
        write(staging, "psf.mod", descriptor(FRAMEWORK_NAME, launcher_path="mod/psf", supported_version=supported_version))
        write(framework, "common/scripted_effects/00_psf_core.txt", runtime.core_effects())
        write(framework, "common/scripted_triggers/00_psf_core.txt", runtime.core_triggers())
        write(framework, "common/dynamic_modifiers/00_psf_legitimacy.txt", """psf_political_legitimacy = {
    enable = { has_country_flag = psf_initialized }
    stability_factor = psf_stability_modifier
    political_power_factor = psf_political_power_modifier
}
""")
        localization.write_localization(framework, "psf_core", localization.core_localization())
        write(content, "descriptor.mod", descriptor(manifest["name"]["english"], dependency=True, supported_version=supported_version))
        write(staging, manifest["id"] + ".mod", descriptor(manifest["name"]["english"], dependency=True, launcher_path="mod/" + manifest["id"], supported_version=supported_version))
        write(staging, "INSTALL.md", f"""# Political Society Framework {__version__}

## 安装

将 `psf`、`{manifest['id']}` 两个目录，以及 `psf.mod`、`{manifest['id']}.mod` 两个文件，放入 HOI4 用户资料目录中的 `mod` 文件夹。

- Windows 通常为 `文档/Paradox Interactive/Hearts of Iron IV/mod`。
- Linux 通常为 `~/.local/share/Paradox Interactive/Hearts of Iron IV/mod`。
- macOS 通常为 `~/Documents/Paradox Interactive/Hearts of Iron IV/mod`。

在启动器的同一游玩集中同时启用 **{FRAMEWORK_NAME}** 和 **{manifest['name']['english']}**。本版本请开始新战役。
从旧版升级时，先移走旧的 `psf/` 与 `{manifest['id']}/` 两个目录，再复制本包；不要只把新文件覆盖到旧目录上，否则旧的 GUI 分块可能继续被游戏加载。保留其他模组目录。
打开本国政治面板或其他国家的外交面板，即可查看国家总览、政治团体、政治光谱与联盟。选中本国团体后，决议面板提供对应政治行动。

此包按提供的原版界面脚本构建。会同时替换政治、外交或选国界面文件的其他模组需要合并适配。原版脚本快照没有提供可核实的游戏版本号；默认省略可选的 `supported_version`，作者可在编译时显式指定本机目标版本。
已完成 Schema、行为回归、界面结构和真实 cwtools 校验；尚未在实际 HOI4 引擎中运行验收。

## Installation

Copy both mod folders and both `.mod` launcher files to your HOI4 user-data `mod` directory. Enable the framework and the dependent content pack together and start a new campaign.
When upgrading, move the old `psf/` and `{manifest['id']}/` folders aside before copying the new folders. Overlaying files can leave obsolete GUI chunks loaded alongside this version; leave unrelated mods in place.
Open politics or diplomacy to inspect societies. Select a domestic organization for its actions in the decisions panel.
The native interface overrides need compatibility work with other UI overhauls. Static/script checks do not replace an in-game launch test.

Source and authoring documentation: https://github.com/maxmixalex/HOI4-Political-Society-Framework

`psf-registry.json` lists the compiled APIs and stable IDs. `build-manifest.json` records generated-file hashes. The per-mod notices retain original-work and third-party attribution.
""")
        effects = runtime.effects(manifest)
        triggers = runtime.triggers(manifest)
        write_effect_chunks(content, effects)
        write(content, "common/scripted_effects/11_psf_ai.txt", gameplay.ai_effects(manifest))
        write_effect_chunks(content, triggers, directory="common/scripted_triggers")
        write_effect_chunks(content, modifiers.definitions(manifest),
                            directory="common/modifier_definitions", prefix="psf_organization_modifiers")
        write(content, "common/on_actions/psf_on_actions.txt", gameplay.on_actions(manifest))
        write(content, "common/decisions/categories/psf_categories.txt", gameplay.categories())
        write_effect_chunks(content, gameplay.decisions(manifest),
                            directory="common/decisions", prefix="psf_society_decisions")
        write(content, "common/game_rules/psf_rules.txt", gameplay.rules(manifest))
        write(content, "events/psf_events.txt", gameplay.events(manifest))
        write(content, "common/scripted_localisation/psf_events.txt", localization.dynamic_localization(manifest))
        localization.write_localization(content, "psf_content", localization.content_localization(manifest))
        localization.write_localization(content, "psf_modifiers", modifiers.localizations(manifest))
        identity_report = identity.write_assets(manifest, content, manifest_path.parent)
        native_root = Path(vanilla).parent if vanilla else None
        bootstrap_report = bootstrap.write_bootstrap_history(manifest, content, native_root)
        mechanics_report = mechanics.write_native_mechanics(manifest, content, native_root)
        from .ui import generate_ui
        ui = generate_ui(manifest, content, Path(vanilla) if vanilla else None)
        bookmark_report = bookmarks.generate_bookmark_previews(
            manifest, content, Path(vanilla).parent if vanilla else None)
        registry = {
            "schema_version": "1.0", "compiler_version": __version__, "content_id": manifest["id"],
            "axes": [a["id"] for a in manifest["axes"]],
            "groups": {g["id"]: {"numeric_id": g["_index"], "profile": p["id"], "kind": g["kind"], "color": g["color"],
                                  "large_icon": icons.sprite(g, "group", "large"), "small_icon": icons.sprite(g, "group", "small"),
                                  "texticon": icons.texticon(g, "group"),
                                  "variables": {field: runtime.gv(g["id"], field) for field in ("support", "influence", "effective_influence", "satisfaction", "status", "prohibited", "ideology", "governing", "vote_share")}}
                       for p in profiles(manifest) for g in p["groups"]},
            "alliances": {a["id"]: {"numeric_id": a["_index"], "profile": p["id"]} for p in profiles(manifest) for a in p["alliances"]},
            "regimes": {r["id"]: r["_index"] for r in manifest["regimes"]},
            "ideologies": {i["id"]: i["_index"] for i in manifest["ideologies"]},
            "ideology_icons": {i["id"]: {"large_icon": icons.sprite(i, "ideology", "large"),
                                          "small_icon": icons.sprite(i, "ideology", "small"),
                                          "texticon": icons.texticon(i, "ideology")} for i in manifest["ideologies"]},
            "identities": identity_report["identities"],
            "governments": {p["id"]: p["government"] for p in profiles(manifest)},
            "government_variables": {"independent_group": "psf_governing_group", "alliance": "psf_governing_alliance",
                                     "display_party": "psf_government_leader_group", "caretaker": "psf_caretaker"},
            "modifiers": modifiers.registry(manifest),
            "effects": sorted(set(re.findall(r"^(psf_[a-zA-Z0-9_]+) =", effects + "\n" + runtime.core_effects(), re.M))),
            "triggers": sorted(set(re.findall(r"^(psf_[a-zA-Z0-9_]+) =", triggers + "\n" + runtime.core_triggers(), re.M))),
        }
        write(staging, "psf-registry.json", json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
        files = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                files[path.relative_to(staging).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        summary = {"compiler_version": __version__, "supported_version": supported_version,
                   "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                   "content_id": manifest["id"], "counts": {"axes": len(manifest["axes"]), "ideologies": len(manifest["ideologies"]), "regimes": len(manifest["regimes"]),
                   "country_profiles": len(manifest["profiles"]), "fallback_profiles": len(manifest["fallback_profiles"]), "groups": len(registry["groups"]),
                   "alliances": len(registry["alliances"]), "scenarios": len(manifest["scenarios"]),
                   "named_modifiers": len(manifest.get("modifiers", [])),
                   "country_identities": len(identity_report["identities"]),
                   "native_modifiers": len(registry["groups"]) * (3 + len(manifest["axes"])) * 3,
                   "effects": len(registry["effects"]), "triggers": len(registry["triggers"])},
                   "files": files, "ui": ui, "bookmarks": bookmark_report, "identities": identity_report,
                   "bootstrap": bootstrap_report, "native_mechanics": mechanics_report}
        write(staging, "build-manifest.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        for source in staging.iterdir():
            destination = output / source.name
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
    return summary


def pack(output: str | Path, archive: str | Path) -> Path:
    output, archive = Path(output), Path(archive)
    manifest = json.loads((output / "build-manifest.json").read_text())
    archive.parent.mkdir(parents=True, exist_ok=True)
    expected = manifest["files"]
    for name, digest in expected.items():
        path = output / name
        if not path.resolve().is_relative_to(output.resolve()):
            raise ValueError(f"Unsafe build-manifest path: {name}")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Build changed after compilation: {name}. Recompile before packaging.")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted([*expected, "build-manifest.json"]):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (output / name).read_bytes())
    return archive
