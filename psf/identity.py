"""Country appearance selected from PSF institutions and governing organizations.

The engine still owns the single cosmetic-tag slot. A foreign tag installed
after a PSF identity suspends automatic updates until the author resumes them.
Flags are authored assets, not guessed historical images; each provided flag
is emitted for every native ideology so changing the compatibility projection
cannot silently change the selected PSF identity.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from .localization import LANGUAGES, write_localization
from .model import ENGINE_IDEOLOGIES, ManifestError, profiles
from .script import Block, addv, block, check, conditional, setv

FLAG_SIZES = {"large": (82, 52), "medium": (41, 26), "small": (10, 7)}


def all_identities(manifest: dict) -> list[dict]:
    return [identity for p in profiles(manifest) for identity in p.get("identities", [])]


def _conditions(manifest: dict, profile: dict, identity: dict) -> list[str]:
    index = {kind: {item["id"]: item["_index"] for item in items} for kind, items in
             (("regime", manifest["regimes"]), ("ideology", manifest["ideologies"]),
              ("group", profile["groups"]), ("alliance", profile["alliances"]))}
    variable = {"regime": "psf_regime", "ideology": "psf_government_ideology",
                "group": "psf_governing_group", "alliance": "psf_governing_alliance"}
    return [check(variable[kind], index[kind][identifier])
            for kind, identifier in identity.get("when", {}).items()]


def _select(identity: dict) -> list[Block | str]:
    tag = identity["cosmetic_tag"]
    return [conditional([f"NOT = {{ has_cosmetic_tag = {tag} }}"],
                        "set_cosmetic_tag = " + tag, addv("psf_ui_revision", 1)),
            setv("psf_identity", identity["_index"])]


def definitions(manifest: dict) -> list[Block]:
    """Emit actual effects, including public manual/suspend/resume APIs."""
    result: list[Block] = []
    dispatch: list[Block] = []
    owned = ["has_cosmetic_tag = " + item["cosmetic_tag"] for item in all_identities(manifest)]
    for profile in profiles(manifest):
        identities = profile.get("identities", [])
        if not identities:
            continue
        chain: list[Block] = []
        for i, identity in enumerate(identities):
            condition = _conditions(manifest, profile, identity)
            if condition or i == 0:
                chain.append(conditional(condition, _select(identity), kind="if" if i == 0 else "else_if"))
            else:
                chain.append(block("else", _select(identity)))
            result.append(block("psf_set_identity_" + identity["id"],
                                conditional(["has_country_flag = psf_profile_" + profile["id"]],
                                            "set_country_flag = psf_identity_manual",
                                            "clr_country_flag = psf_identity_external_override", _select(identity))))
        # Do not overwrite a formable nation, occupation or puppet tag installed
        # by another script after PSF took ownership of the appearance slot.
        detect = conditional([check("psf_identity", 0, "greater_than"),
                              block("NOT", block("OR", owned))],
                             "set_country_flag = psf_identity_external_override")
        body = [detect, conditional(["NOT = { has_country_flag = psf_identity_manual }",
                                     "NOT = { has_country_flag = psf_identity_external_override }"], chain)]
        result.append(block("psf_apply_identity_" + profile["id"], body))
        dispatch.append(conditional(["has_country_flag = psf_profile_" + profile["id"]],
                                    f"psf_apply_identity_{profile['id']} = yes"))
    result.append(block("psf_apply_identity", dispatch))
    result.append(block("psf_suspend_identity", "set_country_flag = psf_identity_manual"))
    result.append(block("psf_resume_identity", "clr_country_flag = psf_identity_manual",
                        "clr_country_flag = psf_identity_external_override", setv("psf_identity", 0),
                        "psf_apply_identity = yes"))
    release: list[Block | str] = []
    if owned:
        release.append(conditional([block("OR", owned)], "drop_cosmetic_tag = yes"))
    release += [setv("psf_identity", 0), "set_country_flag = psf_identity_manual",
                "clr_country_flag = psf_identity_external_override", addv("psf_ui_revision", 1)]
    result.append(block("psf_release_identity", release))
    return result


def localizations(manifest: dict) -> dict[str, dict[str, str]]:
    out = {language: {} for language in LANGUAGES}
    for identity in all_identities(manifest):
        for language in LANGUAGES:
            for engine in ("", *ENGINE_IDEOLOGIES):
                prefix = identity["cosmetic_tag"] + ("_" + engine if engine else "")
                for suffix, field in (("", "name"), ("_DEF", "definite_name"), ("_ADJ", "adjective")):
                    out[language][prefix + suffix] = identity[field][language]
    return out


def _flag_bytes(root: Path, relative: str, size: str) -> bytes:
    source = (root / relative).resolve()
    if not source.is_relative_to(root.resolve()) or not source.is_file():
        raise ManifestError(f"Identity flag asset is missing or outside the manifest directory: {relative}")
    raw = source.read_bytes()
    if len(raw) < 18:
        raise ManifestError(f"Identity flag {relative} is not a complete TGA")
    header = struct.unpack("<BBBHHBHHHHBB", raw[:18])
    width, height, depth, descriptor = header[8:12]
    if (header[1] != 0 or header[2] != 2 or (width, height) != FLAG_SIZES[size]
            or depth != 32 or descriptor & 0x30
            or len(raw) < 18 + header[0] + width * height * 4):
        raise ManifestError(f"Identity flag {relative} must be an uncompressed 32-bit, bottom-left TGA at {FLAG_SIZES[size][0]}x{FLAG_SIZES[size][1]}")
    return raw


def write_assets(manifest: dict, output: Path, manifest_dir: Path) -> dict:
    """Write names and optional flags; return exact provenance."""
    identities = all_identities(manifest)
    if identities:
        write_localization(output, "psf_country_identities", localizations(manifest))
    report = {"identities": {}, "flags": {}}
    for identity in identities:
        tag = identity["cosmetic_tag"]
        report["identities"][identity["id"]] = {
            "numeric_id": identity["_index"], "cosmetic_tag": tag,
            "when": identity["when"], "custom_flags": "flags" in identity,
            "flag_behavior": "fixed_across_native_ideologies" if "flags" in identity else "inherited_from_game",
        }
        for size, source in identity.get("flags", {}).items():
            raw = _flag_bytes(manifest_dir, source, size)
            directory = output / "gfx/flags" / ("" if size == "large" else size)
            directory.mkdir(parents=True, exist_ok=True)
            destinations = []
            for engine in ("", *ENGINE_IDEOLOGIES):
                path = directory / (tag + ("_" + engine if engine else "") + ".tga")
                path.write_bytes(raw)
                destinations.append(path.relative_to(output).as_posix())
            report["flags"][identity["id"] + "/" + size] = {
                "source": source, "sha256": hashlib.sha256(raw).hexdigest(), "outputs": destinations}
    return report
