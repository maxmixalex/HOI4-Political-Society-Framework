"""Make PSF institutions authoritative while retaining native ideology IDs.

Strict mode is a vanilla adapter, not a rewrite of every vanilla focus, event
or peace-conference condition. Those scripts still see a projected native
government. Compat mode leaves the installed game's political mechanics alone.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .model import ENGINE_IDEOLOGIES, ManifestError
from .script import Block, block, check, conditional, emit, setv, subv


ASSETS = Path(__file__).resolve().parent / "assets" / "native_ideologies"

# Names and namespaces are taken from the supplied original 00_defines.lua.
# Equal/non-equal ideology costs are both retained at the same neutral value.
DEFINES = {
    "NCountry.BASE_STABILITY_PARTY_POPULARITY_FACTOR": 0,
    "NTrade.PARTY_SUPPORT_TRADE_FACTOR": 0,
    "NDiplomacy.BASE_IMPROVE_RELATION_SAME_IDEOLOGY_GROUP_MAINTAIN_COST": 0.3,
    "NDiplomacy.BASE_IMPROVE_RELATION_DIFFERENT_IDEOLOGY_GROUP_MAINTAIN_COST": 0.3,
    "NDiplomacy.IDEOLOGY_JOIN_FACTION_MIN_LEVEL": 0,
    "NDiplomacy.EMBARGO_SAME_IDEOLOGY_AI_WEIGHT": 0,
    "NDiplomacy.EMBARGO_DIFFERENT_IDEOLOGY_AI_WEIGHT": 0,
    "NDiplomacy.EMBARGO_DIFFERENT_IDEOLOGY_AT_OFFENSIVE_WAR_AI_WEIGHT": 0,
    "NDiplomacy.EQUIPMENT_PURCHASE_ACCEPTANCE_SAME_IDEOLOGY": 0,
    "NDiplomacy.MARKET_ACCESS_ACCEPTANCE_SAME_IDEOLOGY": 0,
    "NAI.DIPLOMATIC_ACTION_NAVAL_BLOCKADE_DECREMENT_SAME_IDEOLOGY": 0,
    "NAI.DIPLOMACY_FACTION_WRONG_IDEOLOGY_PENALTY": 0,
    "NAI.DIPLOMACY_FACTION_SAME_IDEOLOGY_MAJOR": 0,
    "NAI.PROPOSE_LEND_LEASE_AIDESIRE_SAME_IDEOLOGY": 0,
    "NAI.PROPOSE_LEND_LEASE_AIDESIRE_SAME_IDEOLOGY_CIVIL_WAR": 0,
    "NAI.SEND_VOLUNTEER_AIDESIRE_SAME_IDEOLOGY": 0,
    "NAI.SEND_VOLUNTEER_AIDESIRE_SAME_IDEOLOGY_CIVIL_WAR": 0,
}

# These thresholds replace four different ideology bonuses with two explicit
# institutional policies. Values are fractions of world tension, as in vanilla.
# Electoral institutions have public authorization constraints; other regimes
# use the neutral baseline. Party classification does not select these values.
POLICY = {
    "generate_wargoal_tension": (1.0, 0.5),
    "join_faction_tension": (0.8, 0.4),
    "lend_lease_tension": (0.5, 0.5),
    "send_volunteers_tension": (0.5, 0.4),
    "guarantee_tension": (0.25, 0.4),
}


def strict(manifest: dict) -> bool:
    return manifest["settings"].get("mechanics_mode", "compat") == "strict"


def definitions(manifest: dict) -> list[Block]:
    if not strict(manifest):
        return [block("psf_apply_native_policy", "# Native mechanics retained in compat mode.")]
    body: list[Block | str] = [
        # Disable the engine's four-slot election scheduler; PSF's independent
        # election clock and electoral regime trigger remain active.
        conditional(["has_elections = yes"], block("set_politics", "elections_allowed = no")),
        conditional(["NOT = { has_variable = psf_native_popularity_stability_offset }"],
                    setv("psf_native_popularity_stability_offset", 0)),
        # The observed total includes our previous offset. Subtracting it from
        # the previous offset cancels external sources without sign oscillation.
        "force_update_dynamic_modifier = yes",
        setv("psf_native_popularity_stability_total", "modifier@party_popularity_stability_factor", True),
        subv("psf_native_popularity_stability_offset", "psf_native_popularity_stability_total"),
    ]
    for electoral, kind in ((True, "if"), (False, "else")):
        values: list[Block | str] = [setv("psf_native_" + modifier, pair[0 if electoral else 1])
                                    for modifier, pair in POLICY.items()]
        values.append(block("set_rule",
                            "can_only_justify_war_on_threat_country = " + ("yes" if electoral else "no"),
                            "can_lower_tension = " + ("yes" if electoral else "no"),
                            "can_create_collaboration_government = " + ("no" if electoral else "yes")))
        body.append(conditional([check("psf_elections_enabled", 1)], values) if kind == "if" else block("else", values))
    body += [conditional(["NOT = { has_dynamic_modifier = { modifier = psf_native_political_policy } }"],
                         block("add_dynamic_modifier", "modifier = psf_native_political_policy")),
             "force_update_dynamic_modifier = yes"]
    return [block("psf_apply_native_policy", body)]


def dynamic_modifiers(manifest: dict) -> str:
    if not strict(manifest):
        return ""
    return emit([block("psf_native_political_policy", block("enable", "has_country_flag = psf_initialized"),
                       "party_popularity_stability_factor = psf_native_popularity_stability_offset",
                       [modifier + " = psf_native_" + modifier for modifier in POLICY])]) + "\n"


def neutralize_ideologies(text: str) -> str:
    """Preserve native identity fields; replace each group's mechanical body."""
    from .ui import gui_nodes

    roots = [node for node in gui_nodes(text) if node.parent is None and node.kind == "ideologies"]
    if len(roots) != 1:
        raise ManifestError("Strict mechanics require one native ideologies root")
    root = roots[0]
    if {node.kind for node in root.children} != set(ENGINE_IDEOLOGIES):
        raise ManifestError("Strict vanilla mechanics require exactly the four original ideology groups; use compat for total conversions")
    changes = []
    for ideology in root.children:
        keep = {node.kind: text[node.start:node.end] for node in ideology.children
                if node.kind in {"types", "dynamic_faction_names", "color"}}
        if set(keep) != {"types", "dynamic_faction_names", "color"}:
            raise ManifestError(f"Incomplete native ideology identity fields: {ideology.kind}")
        mechanical = [block("rules", "can_force_government = yes", "can_puppet = yes",
                            "can_send_volunteers = yes", "can_declare_war_on_same_ideology = yes",
                            "can_guarantee_other_ideologies = yes", "can_boost_other_ideologies = no",
                            "can_boost_own_ideology = no", "can_only_justify_war_on_threat_country = no",
                            "can_lower_tension = no", "can_create_collaboration_government = yes"),
                      "can_collaborate = yes", "can_host_government_in_exile = yes", "can_be_boosted = no",
                      "war_impact_on_world_tension = 1.0", "faction_impact_on_world_tension = 1.0",
                      block("modifiers", "political_power_factor = 0"),
                      block("faction_modifiers", "faction_trade_opinion_factor = 0"),
                      "ai_neutral = yes", "ai_ideology_wanted_units_factor = 1.0",
                      "ai_give_core_state_control_threshold = 0"]
        body = "\n\t\t# PSF: native identifiers retained; mechanics come from PSF institutions.\n\t\t"
        body += "\n\t\t".join(keep[name] for name in ("types", "dynamic_faction_names", "color"))
        body += "\n" + emit(mechanical, 2) + "\n\t"
        changes.append((ideology.opening + 1, ideology.end - 1, body))
    for begin, end, replacement in sorted(changes, reverse=True):
        text = text[:begin] + replacement + text[end:]
    return text


def write_native_mechanics(manifest: dict, output: Path, vanilla_path: str | Path | None = None) -> dict:
    if not strict(manifest):
        return {"enabled": False, "mode": "compat", "files": []}
    if manifest["settings"]["bridge_mode"] != "export":
        raise ManifestError("Strict mechanics require bridge_mode='export' so native party drift cannot change PSF support")
    source_dir = Path(vanilla_path) / "common/ideologies" if vanilla_path else ASSETS
    candidates = sorted(source_dir.glob("*.txt"))
    if len(candidates) != 1:
        raise ManifestError("Strict vanilla adapter requires exactly one source ideology file; select compat for a custom ideology system")
    source = candidates[0]
    raw = source.read_bytes()
    converted = neutralize_ideologies(raw.decode("utf-8-sig"))
    ideology_out = Path(output) / "common/ideologies" / source.name
    ideology_out.parent.mkdir(parents=True, exist_ok=True)
    ideology_out.write_text(converted, encoding="utf-8", newline="\n")
    defines = Path(output) / "common/defines/zz_psf_native_politics.lua"
    defines.parent.mkdir(parents=True, exist_ok=True)
    defines.write_text("-- PSF strict vanilla political mechanics adapter.\n" +
                       "\n".join("NDefines." + name + " = " + str(value) for name, value in DEFINES.items()) + "\n", encoding="utf-8")
    dynamic = Path(output) / "common/dynamic_modifiers/psf_native_political_policy.txt"
    dynamic.parent.mkdir(parents=True, exist_ok=True)
    dynamic.write_text(dynamic_modifiers(manifest), encoding="utf-8")
    return {"enabled": True, "mode": "strict", "source": ("external_game_snapshot/common/ideologies/" if vanilla_path else "bundled/native_ideologies/") + source.name,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "files": [str(path.relative_to(output)) for path in (ideology_out, defines, dynamic)],
            "native_groups_preserved": list(ENGINE_IDEOLOGIES), "neutralized_defines": len(DEFINES),
            "remaining_native_script_projection": True}
