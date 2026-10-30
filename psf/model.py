"""Manifest loading, Draft 2020-12 validation, and cross-reference checking."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from .palette import color

ENGINE_IDEOLOGIES = ("democratic", "fascism", "communism", "neutrality")
STATUS = {"inactive": 0, "legal": 1, "underground": 2, "banned": 3}
ROLES = {"government": 1, "opposition": 2, "electoral": 3}
DEFAULTS = {
    "bridge_mode": "bidirectional",
    "term_months": 48,
    "monthly_legitimacy_recovery": 0.8,
    "alignment_penalty": 0.04,
    "underground_influence_factor": 0.35,
    "banned_influence_factor": 0.12,
    "monthly_government_satisfaction": 0.8,
    "monthly_opposition_satisfaction": -0.15,
    "cohesion_gap_penalty": 0.035,
    "coalition_fracture_threshold": 20,
    "member_defection_satisfaction": 20,
    "scenarios_enabled": True,
}


class ManifestError(ValueError):
    pass


def load(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json":
        def unique_pairs(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ManifestError(f"Duplicate JSON object key: {key}")
                out[key] = value
            return out
        data = json.loads(text, object_pairs_hook=unique_pairs)
    elif suffix == ".toml":
        import tomllib
        data = tomllib.loads(text)
    elif suffix in (".yaml", ".yml"):
        import yaml
        class UniqueLoader(yaml.SafeLoader):
            pass
        def construct_mapping(loader, node, deep=False):
            loader.flatten_mapping(node)
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in result:
                    raise ManifestError(f"Duplicate YAML mapping key: {key}")
                result[key] = loader.construct_object(value_node, deep=deep)
            return result
        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
        data = yaml.load(text, Loader=UniqueLoader)
    else:
        raise ManifestError("Manifest must be JSON, TOML, or YAML")
    validate(data)
    return normalize(data)


def profiles(manifest: dict) -> list[dict]:
    return manifest["profiles"] + manifest["fallback_profiles"]


def _ids(items: list[dict], location: str, errors: list[str]) -> set[str]:
    result = set()
    for item in items:
        identifier = item["id"]
        if identifier in result:
            errors.append(f"{location}: duplicate id '{identifier}'")
        result.add(identifier)
    return result


def stable_id(identifier: str) -> int:
    # HOI4 fixed-point variables cannot safely hold arbitrary 32-bit hashes.
    return int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:4], "big") % 900000 + 1


def date_tuple(value: str) -> tuple[int, int, int]:
    parts = tuple(int(x) for x in value.split("."))
    dt.date(*parts)
    return parts


def validate(data: dict) -> None:
    schema = json.loads(files("psf").joinpath("schemas/manifest.schema.json").read_text())
    problems = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(list(e.path)))
    if problems:
        raise ManifestError("\n".join(f"/{'/'.join(map(str, e.path))}: {e.message}" for e in problems[:30]))
    errors: list[str] = []
    if data["id"] == "psf":
        errors.append("content id 'psf' is reserved for the reusable framework mod")
    axis_ids = _ids(data["axes"], "axes", errors)
    _ids(data["ideologies"], "ideologies", errors)
    regime_ids = _ids(data["regimes"], "regimes", errors)
    all_profiles = profiles(data)
    profile_ids = _ids(all_profiles, "profiles", errors)
    all_groups = [g for p in all_profiles for g in p["groups"]]
    all_alliances = [a for p in all_profiles for a in p["alliances"]]
    group_ids = _ids(all_groups, "groups (global)", errors)
    _ids(data.get("modifiers", []), "modifiers", errors)
    modifier_map = {m["id"]: m for m in data.get("modifiers", [])}
    modifier_indices = {}
    for modifier in data.get("modifiers", []):
        index = modifier.get("numeric_id", stable_id(modifier["id"]))
        if index in modifier_indices:
            errors.append(f"modifiers: numeric id collision between {modifier_indices[index]} and {modifier['id']}")
        modifier_indices[index] = modifier["id"]
        if set(modifier.get("groups", [])) - group_ids:
            errors.append(f"modifier {modifier['id']}: unknown target groups")
        if set(modifier.get("positions", {})) - axis_ids:
            errors.append(f"modifier {modifier['id']}: unknown position axes")
    # Concatenated author IDs must not produce the same engine token. The
    # registry uses human-readable keys, so ambiguous joins are rejected rather
    # than silently making two organizations share a saved modifier source.
    generated_symbols = {}
    def claim_symbol(symbol: str, owner: tuple[str, ...]) -> None:
        previous = generated_symbols.get(symbol)
        if previous is not None and previous != owner:
            errors.append(f"Generated modifier symbol collision {symbol}: {previous} / {owner}; rename one id")
        generated_symbols[symbol] = owner
    for group in all_groups:
        gid = group["id"]
        for field in ("support", "influence", "satisfaction", *("position_" + a for a in axis_ids)):
            for kind in ("add", "factor", "daily"):
                claim_symbol(f"psf_{gid}_{field}_{kind}", (gid, field, kind))
        for modifier in data.get("modifiers", []):
            if "groups" in modifier and gid not in modifier["groups"]:
                continue
            mid = modifier["id"]
            claim_symbol(f"psf_m_{gid}_{mid}_active", (gid, mid, "source"))
            for action in ("add", "add_timed", "remove"):
                claim_symbol(f"psf_{action}_{gid}_modifier_{mid}", (gid, mid, action))
    _ids(all_alliances, "alliances (global)", errors)
    for kind, items in (("groups", all_groups), ("alliances", all_alliances), ("regimes", data["regimes"]), ("ideologies", data["ideologies"])):
        indices = {}
        for item in items:
            index = item.get("numeric_id", stable_id(item["id"]))
            if index in indices:
                errors.append(f"{kind}: numeric id collision between {indices[index]} and {item['id']}; set numeric_id explicitly")
            indices[index] = item["id"]
    for item in all_groups + data["ideologies"]:
        if set(item["positions"]) != axis_ids:
            errors.append(f"{item['id']}: positions must name exactly all axes; missing {sorted(axis_ids-set(item['positions']))}, unknown {sorted(set(item['positions'])-axis_ids)}")
    for regime in data["regimes"]:
        if set(regime["positions"]) - axis_ids:
            errors.append(f"regime {regime['id']}: unknown axes")
    tags = set()
    fallbacks = set()
    for p in all_profiles:
        if p in data["profiles"]:
            if "tag" not in p or "engine_ideology" in p:
                errors.append(f"{p['id']}: country profile requires tag, not engine_ideology")
            elif p["tag"] in tags:
                errors.append(f"duplicate country tag {p['tag']}")
            else:
                tags.add(p["tag"])
        else:
            if "engine_ideology" not in p or "tag" in p:
                errors.append(f"{p['id']}: fallback requires engine_ideology, not tag")
            elif p["engine_ideology"] in fallbacks:
                errors.append(f"duplicate fallback {p['engine_ideology']}")
            else:
                fallbacks.add(p["engine_ideology"])
        if p["regime"] not in regime_ids:
            errors.append(f"{p['id']}: unknown regime {p['regime']}")
        gids = {g["id"] for g in p["groups"]}
        aids = {a["id"] for a in p["alliances"]}
        governments = [a for a in p["alliances"] if a["kind"] == "government"]
        if len(governments) != 1:
            errors.append(f"{p['id']}: exactly one initial government alliance is required")
        for a in p["alliances"]:
            if set(a["members"]) - gids:
                errors.append(f"{a['id']}: members must belong to the same profile")
            if a["kind"] == "government" and not any(g["status"] == "legal" and g["id"] in a["members"] for g in p["groups"]):
                errors.append(f"{a['id']}: initial government needs at least one legal group")
        dates = []
        for override in p.get("start_overrides", []):
            try:
                dates.append(date_tuple(override["date"]))
            except ValueError:
                errors.append(f"{p['id']}: invalid calendar date {override['date']}")
            if "regime" in override and override["regime"] not in regime_ids:
                errors.append(f"{p['id']}: start override references unknown regime")
            for g in override.get("groups", []):
                if g["id"] not in gids:
                    errors.append(f"{p['id']}: override references unknown group {g['id']}")
                if "positions" in g and set(g["positions"]) - axis_ids:
                    errors.append(f"{p['id']}: override contains unknown axes")
            for a in override.get("alliances", []):
                if a["id"] not in aids or set(a.get("members", [])) - gids:
                    errors.append(f"{p['id']}: override has unknown alliance/member")
        if len(set(dates)) != len(dates):
            errors.append(f"{p['id']}: duplicate bookmark override date")
    if fallbacks != set(ENGINE_IDEOLOGIES):
        errors.append("fallback_profiles must cover democratic, fascism, communism, neutrality exactly once")
    _ids(data.get("scenarios", []), "scenarios", errors)
    scenario_indices = {}
    for scenario in data.get("scenarios", []):
        index = stable_id(scenario["id"])
        if index in scenario_indices:
            errors.append(f"Scenario event id collision: {scenario_indices[index]} and {scenario['id']}; rename one id")
        scenario_indices[index] = scenario["id"]
    pmap = {p["id"]: p for p in all_profiles}
    for scenario in data.get("scenarios", []):
        if scenario["profile"] not in profile_ids:
            errors.append(f"{scenario['id']}: unknown profile {scenario['profile']}")
            continue
        try:
            date_tuple(scenario["date"])
        except ValueError:
            errors.append(f"{scenario['id']}: invalid calendar date")
        p = pmap[scenario["profile"]]
        gids = {g["id"] for g in p["groups"]}
        aids = {a["id"] for a in p["alliances"]}
        _ids(scenario["options"], scenario["id"] + "/options", errors)
        for option in scenario["options"]:
            for op in option["effects"]:
                needed = {
                    "activate": {"group"}, "ban": {"group"}, "legalize": {"group"},
                    "underground": {"group"}, "deactivate": {"group"},
                    "support": {"group", "value"}, "influence": {"group", "value"},
                    "satisfaction": {"group", "value"}, "join": {"group", "alliance"},
                    "leave": {"group", "alliance"}, "govern": {"alliance"},
                    "dissolve": {"alliance"}, "regime": {"regime"},
                    "legitimacy": {"value"}, "position": {"group", "axis", "value"},
                    "cohesion": {"alliance", "value"},
                    "add_modifier": {"group", "modifier"}, "remove_modifier": {"group", "modifier"},
                }[op["op"]]
                if set(op) != needed | {"op"}:
                    errors.append(f"{scenario['id']}/{option['id']}: {op['op']} requires only {sorted(needed)}")
                for key, allowed in (("group", gids), ("alliance", aids), ("regime", regime_ids), ("axis", axis_ids)):
                    if key in op and op[key] not in allowed:
                        errors.append(f"{scenario['id']}: unknown or cross-country {key}: {op[key]}")
                if "modifier" in op:
                    modifier = modifier_map.get(op["modifier"])
                    if modifier is None:
                        errors.append(f"{scenario['id']}: unknown modifier {op['modifier']}")
                    elif "groups" in modifier and op.get("group") not in modifier["groups"]:
                        errors.append(f"{scenario['id']}: modifier {op['modifier']} does not target {op.get('group')}")
                if op["op"] == "position" and "value" in op and not -100 <= op["value"] <= 100:
                    errors.append(f"{scenario['id']}: position must be between -100 and 100")
    def finite(value, path=""):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"{path}: NaN/Infinity is not a supported game value")
        elif isinstance(value, dict):
            for key, v in value.items():
                finite(v, path + "/" + str(key))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                finite(v, path + "/" + str(i))
    finite(data)
    if errors:
        raise ManifestError("\n".join(errors))


def normalize(data: dict) -> dict:
    data = copy.deepcopy(data)
    data["settings"] = {**DEFAULTS, **data.get("settings", {})}
    data.setdefault("scenarios", [])
    data.setdefault("modifiers", [])
    for modifier in data["modifiers"]:
        modifier.setdefault("duration_days", -1)
        modifier["_index"] = modifier.get("numeric_id", stable_id(modifier["id"]))
    for p in profiles(data):
        identifier = p["id"] + "_transition_cabinet"
        if any(a["id"] == identifier for a in p["alliances"]):
            raise ManifestError(f"{identifier} is reserved for the compiler's transitional cabinet")
        p["alliances"].append({
            "id": identifier,
            "name": {"english": "Cabinet agreement", "simp_chinese": "内阁协定"},
            "description": {"english": "A cabinet formed following an election or a change of government. Other legal organizations can negotiate membership.", "simp_chinese": "由选举或政府更替产生的内阁。其他合法政治组织可以协商加入。"},
            "kind": "opposition", "members": [], "cohesion": 65,
        })
    for item in data["regimes"] + data["ideologies"] + [x for p in profiles(data) for x in p["groups"] + p["alliances"]]:
        item["_index"] = item.get("numeric_id", stable_id(item["id"]))
    alliance_indices = {}
    for p in profiles(data):
        for alliance in p["alliances"]:
            index = alliance["_index"]
            if index in alliance_indices:
                raise ManifestError(f"Alliance numeric id collision including generated cabinets: {alliance_indices[index]} and {alliance['id']}; give the authored alliance a different numeric_id")
            alliance_indices[index] = alliance["id"]
    for p in profiles(data):
        # Canonical RGB keeps JSON/TOML/YAML and equivalent hex spellings
        # byte-identical throughout all generated UI and bookmark artwork.
        for organization in p["groups"]:
            organization["color"] = list(color(organization))
        p["start_overrides"] = sorted(p.get("start_overrides", []), key=lambda v: date_tuple(v["date"]))
    return data
