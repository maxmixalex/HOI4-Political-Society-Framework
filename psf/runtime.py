"""Compile a manifest to native HOI4 effects and triggers.

Only ordinary HOI4 =yes scripted effects are emitted. Parameters are temporary
variables; declaration-specific wrappers save authors from numeric registry IDs.
"""
from __future__ import annotations

from datetime import date, timedelta
import math

from .model import ENGINE_IDEOLOGIES, ROLES, STATUS, profiles
from . import modifiers, charts, identity, mechanics, frontend
from .script import Block, addv, block, check, clamp, conditional, divv, emit, mulv, setv, subv


def gv(group: str, field: str) -> str:
    return f"psf_g_{group}_{field}"


def ev(group: str, field: str) -> str:
    """Current value after reversible sources; gv() is always the baseline."""
    return modifiers.modified_var(group, field)


def av(alliance: str, field: str) -> str:
    return f"psf_a_{alliance}_{field}"


def flag(profile: dict) -> str:
    return "has_country_flag = psf_profile_" + profile["id"]


def active(group: dict) -> str:
    return check(gv(group["id"], "status"), 0, "greater_than")


def legal(group: dict) -> str:
    return check(gv(group["id"], "status"), 1)


def governing_member(profile: dict, group: dict) -> Block:
    """Read current membership, including changes inside an open transaction.

    The derived ``governing`` flag is a UI cache. Using it as a permission
    predicate would reject leaving a cabinet and banning that organization in
    the same event, or permit banning a member that just joined the cabinet.
    """
    membership = [check("psf_governing_group", group["_index"])]
    membership += [block("AND", check("psf_governing_alliance", alliance["_index"]),
                         check(av(alliance["id"], "g_" + group["id"]), 1))
                   for alliance in profile["alliances"]]
    return block("AND", legal(group), block("OR", membership))


def government_selection(profile: dict) -> dict | None:
    """Explicit government takes precedence; omitted fields keep legacy data."""
    if "government" in profile:
        return profile["government"]
    return next(({"alliance": a["id"]} for a in profile.get("alliances", [])
                 if a["kind"] == "government"), None)


def select_government(profile: dict, selection: dict | None) -> list[Block | str]:
    out: list[Block | str] = [setv("psf_governing_alliance", 0), setv("psf_governing_group", 0)]
    if selection:
        kind = "group" if "group" in selection else "alliance"
        items = profile["groups"] if kind == "group" else profile["alliances"]
        chosen = next(item for item in items if item["id"] == selection[kind])
        out.append(setv("psf_governing_" + kind, chosen["_index"]))
    return out


def distance(destination: str, pairs: list[tuple[str, str | float, float]], scale: float = 1) -> list[Block | str]:
    """Weighted Manhattan distance; source variables, constants, explicit divisor."""
    out: list[Block | str] = [setv(destination, 0, True)]
    for left, right, weight in pairs:
        out += [setv("psf_delta", left, True), subv("psf_delta", right, True),
                conditional([check("psf_delta", 0, "less_than")], mulv("psf_delta", -1, True)),
                mulv("psf_delta", weight, True), addv(destination, "psf_delta", True)]
    if pairs:
        # Unlike built-in sum(float), fsum keeps the same accumulation across
        # Python 3.11/3.12; a changed last bit can cross our rounding boundary.
        out.append(divv(destination, math.fsum(p[2] for p in pairs) / scale, True))
    return out


def classify(manifest: dict, prefix: str, effect: str) -> Block:
    items: list[Block | str] = [setv("psf_best_distance", 201, True)]
    for ideology in manifest["ideologies"]:
        pairs = [(prefix + a["id"], ideology["positions"][a["id"]], a["weight"]) for a in manifest["axes"]]
        items += distance("psf_distance", pairs)
        items.append(conditional([check("psf_distance", "psf_best_distance", "less_than")],
                                 setv("psf_best_distance", "psf_distance", True),
                                 setv(effect, ideology["_index"])))
    return block("psf_classify_" + effect.removeprefix("psf_").removesuffix("_ideology"), items)


def core_effects() -> str:
    return emit([
        block("psf_add_legitimacy", "custom_effect_tooltip = psf_effect_legitimacy", addv("psf_legitimacy", "psf_amount"), clamp("psf_legitimacy", 0, 100), "psf_refresh_modifiers = yes", addv("psf_ui_revision", 1)),
        block("psf_refresh_modifiers",
              setv("psf_previous_stability_modifier", "psf_stability_modifier", True),
              setv("psf_previous_political_power_modifier", "psf_political_power_modifier", True),
              setv("psf_stability_modifier", "psf_legitimacy"), subv("psf_stability_modifier", 60), divv("psf_stability_modifier", 500),
              clamp("psf_stability_modifier", -0.12, 0.08),
              setv("psf_political_power_modifier", "psf_legitimacy"), subv("psf_political_power_modifier", 60), divv("psf_political_power_modifier", 400),
              clamp("psf_political_power_modifier", -0.15, 0.10),
              conditional(["NOT = { has_dynamic_modifier = { modifier = psf_political_legitimacy } }"],
                          "add_dynamic_modifier = { modifier = psf_political_legitimacy }"),
              # Existing native dynamic modifiers otherwise retain yesterday's
              # values while the PSF panel already shows the new legitimacy.
              conditional([block("OR",
                                 block("NOT", check("psf_stability_modifier", "psf_previous_stability_modifier")),
                                 block("NOT", check("psf_political_power_modifier", "psf_previous_political_power_modifier")))],
                          "force_update_dynamic_modifier = yes")),
        block("psf_prepare_change", conditional(["NOT = { has_country_flag = psf_batch_update }"], "psf_import_popularity = yes")),
        block("psf_begin_transaction", "psf_prepare_change = yes", "set_country_flag = psf_batch_update"),
        # Content compiler supplies psf_commit_transaction, which refreshes once.
        block("psf_rebuild_public_confidence", setv("psf_amount", 6, True), "psf_add_legitimacy = yes"),
    ]) + "\n"


def core_triggers() -> str:
    return emit([
        block("psf_is_initialized", "has_country_flag = psf_initialized"),
        block("psf_has_legitimacy_crisis", check("psf_legitimacy", 30, "less_than")),
        block("psf_has_stable_government", check("psf_caretaker", 0), check("psf_legitimacy", 60, "greater_than_or_equals")),
        block("psf_has_elections", check("psf_elections_enabled", 1)),
        block("psf_is_caretaker", check("psf_caretaker", 1)),
        block("psf_has_group_government", check("psf_governing_group", 0, "greater_than"), check("psf_caretaker", 0)),
        block("psf_has_alliance_government", check("psf_governing_alliance", 0, "greater_than"), check("psf_caretaker", 0)),
        block("psf_legitimacy_at_least", check("psf_legitimacy", "psf_threshold", "greater_than_or_equals")),
    ]) + "\n"


def refresh_effect(manifest: dict, p: dict) -> Block:
    settings = manifest["settings"]
    axes = manifest["axes"]
    out: list[Block | str] = [
        setv("psf_total_influence", 0), setv("psf_total_party_support", 0),
        setv("psf_government_weight", 0), setv("psf_government_support", 0),
        setv("psf_government_satisfaction", 0), setv("psf_group_count", 0),
        setv("psf_government_members", 0), setv("psf_caretaker", 1),
        setv("psf_government_leader_group", 0), setv("psf_government_leader_weight", -1, True),
    ]
    for axis in axes:
        aid = axis["id"]
        out += [setv("psf_gov_" + aid, 0), setv("psf_institution_" + aid, 0),
                setv("psf_ui_institution_defined_" + aid, 0)]
    for alliance in p["alliances"]:
        out += [setv(av(alliance["id"], "active"), 0),
                conditional([block("OR", [check(av(alliance["id"], "g_" + group["id"]), 1) for group in p["groups"]])],
                            setv(av(alliance["id"], "active"), 1))]
    for g in p["groups"]:
        gid = g["id"]
        out += modifiers.recalculate_group(manifest, g)
        out += [setv(gv(gid, "governing"), 0), setv(gv(gid, "effective_influence"), ev(gid, "influence")),
                conditional([check(gv(gid, "status"), 0)], setv(gv(gid, "effective_influence"), 0)),
                conditional([check(gv(gid, "status"), 2)], mulv(gv(gid, "effective_influence"), settings["underground_influence_factor"])),
                conditional([check(gv(gid, "status"), 3)], mulv(gv(gid, "effective_influence"), settings["banned_influence_factor"])),
                addv("psf_total_influence", gv(gid, "effective_influence")),
                conditional([active(g)], addv("psf_group_count", 1))]
        if g["electoral"]:
            out.append(conditional([active(g)], addv("psf_total_party_support", ev(gid, "support"))))
        membership = [check("psf_governing_group", g["_index"])] + [block("AND", check("psf_governing_alliance", a["_index"]), check(av(a["id"], "active"), 1), check(av(a["id"], "g_" + gid), 1)) for a in p["alliances"]]
        body: list[Block | str] = [setv(gv(gid, "governing"), 1), setv("psf_caretaker", 0), addv("psf_government_members", 1),
                                  addv("psf_government_weight", gv(gid, "effective_influence")),
                                  setv("psf_weighted", ev(gid, "satisfaction"), True), mulv("psf_weighted", gv(gid, "effective_influence"), True),
                                  addv("psf_government_satisfaction", "psf_weighted")]
        if g["electoral"]:
            body.append(addv("psf_government_support", ev(gid, "support")))
        for axis in axes:
            aid = axis["id"]
            body += [setv("psf_weighted", ev(gid, "position_" + aid), True), mulv("psf_weighted", gv(gid, "effective_influence"), True), addv("psf_gov_" + aid, "psf_weighted")]
        out.append(conditional([legal(g), block("OR", membership)], body))
    out += [setv("psf_government_influence", "psf_government_weight"),
            conditional([check("psf_total_influence", 0, "greater_than")], divv("psf_government_influence", "psf_total_influence"), mulv("psf_government_influence", 100)),
            conditional([check("psf_total_party_support", 0, "greater_than")], divv("psf_government_support", "psf_total_party_support"), mulv("psf_government_support", 100))]
    out.append(conditional([check("psf_government_weight", 0, "greater_than")],
                           [divv("psf_gov_" + axis["id"], "psf_government_weight") for axis in axes],
                           divv("psf_government_satisfaction", "psf_government_weight")))
    # Zero-power legal cabinets remain a caretaker: their coordinates are undefined.
    out.append(conditional([check("psf_government_weight", 0)], setv("psf_caretaker", 1), setv("psf_governing_alliance", 0), setv("psf_governing_group", 0),
                           setv("psf_government_members", 0), setv("psf_government_support", 0), setv("psf_government_satisfaction", 0),
                           [setv(gv(g['id'], 'governing'), 0) for g in p['groups']]))
    # The displayed governing organization prioritizes a governing party over
    # the army, palace or another institutional member of a coalition. This is
    # presentation data; it does not change cabinet membership or its weights.
    political, other = [], []
    for g in sorted(p["groups"], key=lambda group: group["_index"]):
        candidate = conditional([check(gv(g["id"], "governing"), 1),
                                 check(gv(g["id"], "effective_influence"), "psf_government_leader_weight", "greater_than")],
                                setv("psf_government_leader_group", g["_index"]),
                                setv("psf_government_leader_weight", gv(g["id"], "effective_influence"), True))
        (political if g.get("electoral", False) or g.get("kind") == "party" else other).append(candidate)
    out += political
    if other:
        out.append(conditional([check("psf_government_leader_group", 0)], other))
    out.append("psf_classify_government = yes")
    out += [setv("psf_alignment_gap", 0), setv("psf_elections_enabled", 0)]
    for regime in manifest["regimes"]:
        pairs = [("psf_gov_" + axis["id"], regime["positions"][axis["id"]], axis["weight"]) for axis in axes if axis["id"] in regime["positions"]]
        institution = [value for aid, coordinate in regime["positions"].items()
                       for value in (setv("psf_institution_" + aid, coordinate),
                                     setv("psf_ui_institution_defined_" + aid, 1))]
        out.append(conditional([check("psf_regime", regime["_index"])],
                               distance("psf_distance", pairs, 0.5), setv("psf_alignment_gap", "psf_distance"),
                               setv("psf_elections_enabled", int(regime.get("elections", False))), institution))
    for axis in axes:
        aid = axis["id"]
        for identity, source in (("institution", "psf_institution_"), ("government", "psf_gov_")):
            position = "psf_ui_" + identity + "_" + aid
            out += [setv(position, source + aid), clamp(position, -100, 100), addv(position, 184)]
    out.append(conditional([check("psf_caretaker", 1)], setv("psf_alignment_gap", 100), setv("psf_government_ideology", 0)))
    for alliance in p["alliances"]:
        aid = alliance["id"]
        body = [conditional([check("psf_governing_alliance", alliance["_index"])], setv(av(aid, "role"), 1)),
                conditional([block("NOT", check("psf_governing_alliance", alliance["_index"])), check(av(aid, "role"), 1)], setv(av(aid, "role"), 2)),
                setv(av(aid, "member_count"), 0), setv(av(aid, "support"), 0), setv(av(aid, "influence"), 0), setv(av(aid, "satisfaction"), 0), setv(av(aid, "gap"), 0)]
        for axis in axes:
            body.append(setv(av(aid, "position_" + axis["id"]), 0))
        for g in p["groups"]:
            gid = g["id"]
            # Membership and active political weight are distinct. A pact with
            # dormant members still exists until its membership is removed.
            body.append(conditional([check(av(aid, "g_" + gid), 1)], addv(av(aid, "member_count"), 1)))
            contribution: list[Block | str] = [addv(av(aid, "influence"), gv(gid, "effective_influence")),
                setv("psf_weighted", ev(gid, "satisfaction"), True), mulv("psf_weighted", gv(gid, "effective_influence"), True), addv(av(aid, "satisfaction"), "psf_weighted")]
            if g["electoral"]:
                contribution.append(addv(av(aid, "support"), ev(gid, "support")))
            for axis in axes:
                dim = axis["id"]
                contribution += [setv("psf_weighted", ev(gid, "position_" + dim), True), mulv("psf_weighted", gv(gid, "effective_influence"), True), addv(av(aid, "position_" + dim), "psf_weighted")]
            body.append(conditional([check(av(aid, "g_" + gid), 1), active(g)], contribution))
        body.append(conditional([check(av(aid, "influence"), 0, "greater_than")],
                                [divv(av(aid, "position_" + axis["id"]), av(aid, "influence")) for axis in axes], divv(av(aid, "satisfaction"), av(aid, "influence"))))
        for g in p["groups"]:
            pairs = [(ev(g["id"], "position_" + axis["id"]), av(aid, "position_" + axis["id"]), axis["weight"]) for axis in axes]
            body.append(conditional([check(av(aid, "g_" + g["id"]), 1), active(g)],
                                    distance("psf_distance", pairs, 0.5), mulv("psf_distance", gv(g["id"], "effective_influence"), True), addv(av(aid, "gap"), "psf_distance")))
        body += [conditional([check(av(aid, "influence"), 0, "greater_than")], divv(av(aid, "gap"), av(aid, "influence"))),
                 clamp(av(aid, "gap"), 0, 100), clamp(av(aid, "cohesion"), 0, 100),
                 conditional([check(av(aid, "member_count"), 0)], setv(av(aid, "active"), 0),
                             conditional([check("psf_governing_alliance", alliance["_index"])], setv("psf_governing_alliance", 0), setv("psf_caretaker", 1)))]
        out += body
    out += [clamp("psf_alignment_gap", 0, 100), clamp("psf_legitimacy", 0, 100),
            setv("psf_legitimacy_change", settings["monthly_legitimacy_recovery"]),
            setv("psf_alignment_loss", "psf_alignment_gap", True), mulv("psf_alignment_loss", settings["alignment_penalty"], True),
            subv("psf_legitimacy_change", "psf_alignment_loss"),
            setv("psf_satisfaction_bonus", "psf_government_satisfaction", True), subv("psf_satisfaction_bonus", 50, True), divv("psf_satisfaction_bonus", 100, True),
            addv("psf_legitimacy_change", "psf_satisfaction_bonus"),
            conditional([check("psf_caretaker", 1)], subv("psf_legitimacy_change", 1)),
            "psf_refresh_modifiers = yes", "psf_update_charts_" + p["id"] + " = yes", "psf_apply_identity = yes", addv("psf_ui_revision", 1)]
    if manifest["settings"].get("mechanics_mode", "compat") == "strict":
        out += ["psf_apply_native_policy = yes", "psf_export_government = yes"]
    return block("psf_refresh_" + p["id"], out)


def finish() -> Block:
    return conditional(["NOT = { has_country_flag = psf_batch_update }"], "psf_refresh = yes", "psf_export_popularity = yes")


def group_effects(manifest: dict, p: dict, g: dict) -> list[Block]:
    gid = g["id"]
    state = gv(gid, "status")
    out = [classify(manifest, gv(gid, "modified_position_"), gv(gid, "ideology"))]
    # Idempotent state transitions; repeated ban/legalize cannot mint power.
    changes = {
        "activate": ([check(state, 0)], [setv(state, 1), setv(gv(gid, "prohibited"), 0)]),
        "legalize": ([check(state, 1, "greater_than")], [setv(state, 1), setv(gv(gid, "prohibited"), 0), addv(gv(gid, "satisfaction"), 8)]),
        "ban": ([check(state, 0, "greater_than"), check(state, 3, "less_than"), block("NOT", governing_member(p, g))],
                [setv(state, 3), setv(gv(gid, "prohibited"), 1), subv(gv(gid, "satisfaction"), 15), subv("psf_legitimacy", 3)]),
        "underground": ([block("OR", check(state, 1), check(state, 3))], [setv(state, 2)]),
        "deactivate": ([active(g), block("NOT", governing_member(p, g))], [setv(state, 0)]),
    }
    for name, (requirements, body) in changes.items():
        if name in ("ban", "deactivate", "underground"):
            # Only the governing coalition loses an illegal member; electoral or
            # opposition cooperation may continue in clandestine form.
            for a in p["alliances"]:
                body.append(conditional([check("psf_governing_alliance", a["_index"])], setv(av(a["id"], "g_" + gid), 0)))
            body.append(conditional([check("psf_governing_group", g["_index"])], setv("psf_governing_group", 0)))
        out.append(block(f"psf_{name}_{gid}", conditional([flag(p), *requirements], "psf_prepare_change = yes", f"custom_effect_tooltip = psf_effect_{name}_{gid}", body, finish())))
    for metric in ("support", "influence", "satisfaction"):
        out.append(block(f"psf_add_{gid}_{metric}", conditional([flag(p)], "psf_prepare_change = yes", f"custom_effect_tooltip = psf_effect_add_{gid}_{metric}", addv(gv(gid, metric), "psf_amount"), clamp(gv(gid, metric), 0, 100), finish())))
        out.append(block(f"psf_set_{gid}_{metric}", conditional([flag(p)], "psf_prepare_change = yes", f"custom_effect_tooltip = psf_effect_set_{gid}_{metric}", setv(gv(gid, metric), "psf_amount"), clamp(gv(gid, metric), 0, 100), finish())))
    for axis in manifest["axes"]:
        out.append(block(f"psf_add_{gid}_position_{axis['id']}", conditional([flag(p)], "psf_prepare_change = yes",
                         f"custom_effect_tooltip = psf_effect_add_position_{gid}_{axis['id']}", addv(gv(gid, "position_" + axis["id"]), "psf_amount"), clamp(gv(gid, "position_" + axis["id"]), -100, 100), finish())))
        out.append(block(f"psf_set_{gid}_position_{axis['id']}", conditional([flag(p)], "psf_prepare_change = yes",
                         f"custom_effect_tooltip = psf_effect_position_{gid}_{axis['id']}", setv(gv(gid, "position_" + axis["id"]), "psf_position"), clamp(gv(gid, "position_" + axis["id"]), -100, 100),
                         finish())))
    cabinet: list[Block | str] = ["custom_effect_tooltip = psf_effect_govern_group_" + gid]
    for member in p["groups"]:
        if member["id"] != gid:
            cabinet.append(conditional([check(gv(member["id"], "governing"), 1)], subv(gv(member["id"], "satisfaction"), 10)))
    cabinet += [conditional([check(gv(gid, "governing"), 0)], addv(gv(gid, "satisfaction"), 20), clamp(gv(gid, "satisfaction"), 60, 100))]
    for alliance in p["alliances"]:
        cabinet.append(conditional([check(av(alliance["id"], "role"), 1)], setv(av(alliance["id"], "role"), 2)))
    cabinet += [setv("psf_governing_alliance", 0), setv("psf_governing_group", g["_index"]),
                "psf_refresh = yes", "psf_export_government = yes",
                conditional(["NOT = { has_country_flag = psf_batch_update }"], "psf_export_popularity = yes")]
    out.append(block("psf_govern_group_" + gid, conditional([flag(p)], "psf_prepare_change = yes", "psf_refresh = yes",
                     conditional([legal(g), check(ev(gid, "influence"), 0, "greater_than")], cabinet))))
    return out


def alliance_effects(manifest: dict, p: dict, a: dict) -> list[Block]:
    aid = a["id"]
    out = []
    legal_member = [block("AND", legal(g), check(av(aid, "g_" + g["id"]), 1), check(ev(g["id"], "influence"), 0, "greater_than")) for g in p["groups"]]
    government_body: list[Block | str] = ["custom_effect_tooltip = psf_effect_govern_" + aid]
    for g in p["groups"]:
        government_body += [
            conditional([check(gv(g["id"], "governing"), 1), check(av(aid, "g_" + g["id"]), 0)], subv(gv(g["id"], "satisfaction"), 10)),
            conditional([check(gv(g["id"], "governing"), 0), check(av(aid, "g_" + g["id"]), 1), legal(g)],
                        addv(gv(g["id"], "satisfaction"), 20), clamp(gv(g["id"], "satisfaction"), 60, 100)),
        ]
    for other in p["alliances"]:
        government_body.append(conditional([check(av(other["id"], "role"), 1)], setv(av(other["id"], "role"), 2)))
    government_body += [setv("psf_governing_group", 0), setv("psf_governing_alliance", a["_index"]), setv(av(aid, "active"), 1), setv(av(aid, "role"), 1),
                        "psf_refresh = yes", "psf_export_government = yes",
                        conditional(["NOT = { has_country_flag = psf_batch_update }"], "psf_export_popularity = yes")]
    # Elections and native government imports may have just raised a winner's
    # baseline institutional access. Refresh before checking derived influence,
    # including when a caller is batching changes. Reading the previous cache
    # would reject a legitimate zero-influence winner; checking the baseline
    # instead would incorrectly bypass a real suppressing modifier.
    out.append(block("psf_govern_" + aid, conditional([flag(p)], "psf_prepare_change = yes", "psf_refresh = yes",
                     conditional([block("OR", legal_member)], government_body))))
    out.append(block("psf_dissolve_" + aid, conditional([flag(p), check(av(aid, "active"), 1)], "psf_prepare_change = yes",
                     "custom_effect_tooltip = psf_effect_dissolve_" + aid,
                     setv(av(aid, "active"), 0),
                     [setv(av(aid, "g_" + g["id"]), 0) for g in p["groups"]],
                     conditional([check("psf_governing_alliance", a["_index"])], setv("psf_governing_alliance", 0), subv("psf_legitimacy", 8)), finish())))
    out.append(block("psf_add_" + aid + "_cohesion", conditional([flag(p)], "psf_prepare_change = yes", "custom_effect_tooltip = psf_effect_cohesion_" + aid, addv(av(aid, "cohesion"), "psf_amount"), clamp(av(aid, "cohesion"), 0, 100), finish())))
    for g in p["groups"]:
        gid = g["id"]
        requirements = [flag(p), active(g), block("OR", block("NOT", check("psf_governing_alliance", a["_index"])), legal(g))]
        out.append(block(f"psf_join_{aid}_{gid}", conditional(requirements, "psf_prepare_change = yes",
                         f"custom_effect_tooltip = psf_effect_join_{aid}_{gid}",
                         conditional([check(av(aid, "active"), 0)], setv(av(aid, "cohesion"), a["cohesion"])),
                         setv(av(aid, "active"), 1), setv(av(aid, "g_" + gid), 1), finish())))
        out.append(block(f"psf_leave_{aid}_{gid}", conditional([flag(p), check(av(aid, "g_" + gid), 1)], "psf_prepare_change = yes", f"custom_effect_tooltip = psf_effect_leave_{aid}_{gid}", setv(av(aid, "g_" + gid), 0), finish())))
    return out


def initialize_effect(manifest: dict, p: dict) -> Block:
    regime_map = {r["id"]: r for r in manifest["regimes"]}
    body: list[Block | str] = ["set_country_flag = psf_initialized", "set_country_flag = psf_profile_" + p["id"],
                             setv("psf_schema_version", 2), setv("psf_legitimacy", p["legitimacy"]),
                             setv("psf_regime", regime_map[p["regime"]]["_index"]), setv("psf_election_clock", p.get("election_months_elapsed", 0)),
                             setv("psf_election_term", p.get("election_term_months", manifest['settings']['term_months'])),
                             setv("psf_election_count", 0), setv("psf_ui_open", 0), setv("psf_ui_page", 0), setv("psf_identity", 0),
                             setv("psf_governing_alliance", 0), setv("psf_governing_group", 0)]
    for g in p["groups"]:
        body += modifiers.initialize_group(manifest, g)
        for metric in ("support", "influence", "satisfaction"):
            body.append(setv(gv(g["id"], metric), g[metric]))
        body.append(setv(gv(g["id"], "status"), STATUS[g["status"]]))
        body.append(setv(gv(g["id"], "prohibited"), int(g["status"] in ("banned", "underground"))))
        body.append(setv(gv(g["id"], "vote_share"), 0))
        for axis, value in g["positions"].items():
            body.append(setv(gv(g["id"], "position_" + axis), value))
    for a in p["alliances"]:
        body += [setv(av(a["id"], "active"), int(bool(a["members"]))), setv(av(a["id"], "role"), ROLES[a["kind"]]), setv(av(a["id"], "electoral"), int(a["kind"] == "electoral")), setv(av(a["id"], "cohesion"), a["cohesion"])]
        for g in p["groups"]:
            body.append(setv(av(a["id"], "g_" + g["id"]), int(g["id"] in a["members"])))
    body += select_government(p, government_selection(p))
    for override in p.get("start_overrides", []):
        effects: list[Block | str] = []
        if "regime" in override:
            effects.append(setv("psf_regime", regime_map[override["regime"]]["_index"]))
        if "legitimacy" in override:
            effects.append(setv("psf_legitimacy", override["legitimacy"]))
        if "election_months_elapsed" in override:
            effects.append(setv("psf_election_clock", override["election_months_elapsed"]))
        if "election_term_months" in override:
            effects.append(setv("psf_election_term", override["election_term_months"]))
        for group in override.get("groups", []):
            for field in ("support", "influence", "satisfaction", "status"):
                if field in group:
                    effects.append(setv(gv(group["id"], field), STATUS[group[field]] if field == "status" else group[field]))
                    if field == "status":
                        effects.append(setv(gv(group["id"], "prohibited"), int(group[field] in ("banned", "underground"))))
            for axis, value in group.get("positions", {}).items():
                effects.append(setv(gv(group["id"], "position_" + axis), value))
        for alliance in override.get("alliances", []):
            if "members" in alliance:
                effects += [setv(av(alliance["id"], "g_" + group["id"]), int(group["id"] in alliance["members"])) for group in p["groups"]]
                effects.append(setv(av(alliance["id"], "active"), int(bool(alliance["members"]))))
            if "cohesion" in alliance:
                effects.append(setv(av(alliance["id"], "cohesion"), alliance["cohesion"]))
            if "kind" in alliance:
                effects.append(setv(av(alliance["id"], "role"), ROLES[alliance["kind"]]))
                effects.append(setv(av(alliance["id"], "electoral"), int(alliance["kind"] == "electoral")))
                if alliance["kind"] == "government":
                    index = next(a["_index"] for a in p["alliances"] if a["id"] == alliance["id"])
                    effects += [setv("psf_governing_group", 0), setv("psf_governing_alliance", index)]
        if "government" in override:
            effects += select_government(p, override["government"])
        previous_day = date(*map(int, override["date"].split('.'))) - timedelta(days=1)
        body.append(conditional([f"date > {previous_day.year}.{previous_day.month}.{previous_day.day}"], effects))
    body += [f"psf_refresh_{p['id']} = yes", "psf_export_popularity = yes", "psf_capture_engine_government = yes"]
    for scenario in manifest["scenarios"]:
        if scenario["profile"] == p["id"]:
            # Do not replay historical 1936 events when a 1939 bookmark loads.
            body.append(conditional(["date > " + scenario["date"]], "set_country_flag = psf_scenario_" + scenario["id"]))
    return block("psf_init_" + p["id"], conditional(["NOT = { has_country_flag = psf_initialized }"], body))


def election_effect(manifest: dict, p: dict) -> list[Block]:
    """Approval is normalized only at the ballot; civil organizations never vote."""
    body: list[Block | str] = [setv("psf_ballot_total", 0, True), setv("psf_winning_score", -1, True), setv("psf_winning_group", 0)]
    for g in p["groups"]:
        body.append(setv(gv(g["id"], "vote_share"), 0))
        if g["electoral"]:
            body.append(conditional([legal(g)], addv("psf_ballot_total", ev(g["id"], "support"), True)))
    count_votes: list[Block | str] = []
    for g in sorted(p["groups"], key=lambda group: group["_index"]):
        if not g["electoral"]:
            continue
        count_votes.append(conditional([legal(g)],
                           setv(gv(g["id"], "vote_share"), ev(g["id"], "support")), divv(gv(g["id"], "vote_share"), "psf_ballot_total"), mulv(gv(g["id"], "vote_share"), 100),
                           conditional([check(gv(g["id"], "vote_share"), "psf_winning_score", "greater_than")],
                                       setv("psf_winning_score", gv(g["id"], "vote_share"), True), setv("psf_winning_group", g["_index"]))))
    count_votes += [setv("psf_winning_alliance", 0), setv("psf_winning_score", -1, True)]
    # Electoral pacts compete as combined ballots; overlapping pacts do not
    # double count inside a pact, and a winning party is counted once per pact.
    for a in sorted(p["alliances"], key=lambda alliance: alliance["_index"]):
        pact: list[Block | str] = [setv("psf_pact_votes", 0, True)]
        for g in p["groups"]:
            if g["electoral"]:
                pact.append(conditional([legal(g), check(av(a["id"], "g_" + g["id"]), 1)], addv("psf_pact_votes", gv(g["id"], "vote_share"), True)))
        pact.append(conditional([check("psf_pact_votes", "psf_winning_score", "greater_than"), check("psf_pact_votes", 0, "greater_than")],
                                setv("psf_winning_score", "psf_pact_votes", True), setv("psf_winning_alliance", a["_index"])))
        count_votes.append(conditional([check(av(a["id"], "active"), 1), check(av(a["id"], "electoral"), 1)], pact))
    for g in p["groups"]:
        if g["electoral"]:
            count_votes.append(conditional([check("psf_winning_group", g["_index"]), check(gv(g["id"], "vote_share"), "psf_winning_score", "greater_than")], setv("psf_winning_alliance", 0)))
    for a in p["alliances"]:
        office = [conditional([legal(g), check(av(a['id'], 'g_' + g['id']), 1)], clamp(gv(g['id'], 'influence'), 10, 100)) for g in p['groups'] if g['electoral']]
        count_votes.append(conditional([check("psf_winning_alliance", a["_index"])], office, "psf_govern_" + a["id"] + " = yes"))
    for g in p['groups']:
        if g['electoral']:
            count_votes.append(conditional([check("psf_winning_alliance", 0), check("psf_winning_group", g['_index']), legal(g)], clamp(gv(g['id'], 'influence'), 10, 100)))
    count_votes.append(conditional([check("psf_winning_alliance", 0)], "psf_form_cabinet_" + p["id"] + " = yes"))
    count_votes += [setv("psf_election_clock", 0), addv("psf_election_count", 1), addv("psf_legitimacy", 3), f"psf_refresh_{p['id']} = yes",
                    conditional(["is_ai = no"], "country_event = { id = psf.1 }")]
    body.append(conditional([check("psf_ballot_total", 0, "greater_than")], count_votes))
    # Keep the public helper name, but a standalone winner does not need an
    # invented empty alliance. Authored electoral pacts still govern jointly.
    cabinet_body: list[Block | str] = []
    for g in p["groups"]:
        cabinet_body.append(conditional([check("psf_winning_group", g["_index"]), legal(g)], "psf_govern_group_" + g["id"] + " = yes"))
    # A caller can change support, sources or the regime inside a transaction.
    # Eligibility and ballots must use the resulting values, not the cache from
    # before the transaction began; the caller still owns the batch flag.
    return [block("psf_hold_election_" + p["id"], conditional([flag(p)], "psf_prepare_change = yes", "psf_refresh = yes",
                  conditional([check("psf_elections_enabled", 1)], body))),
            block("psf_form_cabinet_" + p["id"], conditional([flag(p)], "psf_prepare_change = yes", cabinet_body))]


def monthly_effect(manifest: dict, p: dict) -> Block:
    settings = manifest["settings"]
    out: list[Block | str] = ["psf_begin_transaction = yes"]
    for g in p["groups"]:
        gid = g["id"]
        body: list[Block | str] = [
            conditional([check(gv(gid, "governing"), 1)], addv(gv(gid, "satisfaction"), settings["monthly_government_satisfaction"])),
            conditional([check(gv(gid, "governing"), 0)], addv(gv(gid, "satisfaction"), settings["monthly_opposition_satisfaction"])),
            conditional([check(gv(gid, "status"), 3), check(ev(gid, "support"), 10, "greater_than_or_equals")], setv(gv(gid, "status"), 2)),
            clamp(gv(gid, "satisfaction"), 0, 100),
        ]
        out.append(conditional([active(g)], body))
    out += [f"psf_refresh_{p['id']} = yes", setv("psf_coalition_changed", 0)]
    for a in p["alliances"]:
        aid = a["id"]
        body = [setv("psf_cohesion_change", av(aid, "satisfaction"), True),
                conditional([block("NOT", check(av(aid, "role"), 1))], setv("psf_cohesion_change", 100, True), subv("psf_cohesion_change", av(aid, "satisfaction"), True)),
                subv("psf_cohesion_change", 50, True), divv("psf_cohesion_change", 30, True),
                setv("psf_cohesion_penalty", av(aid, "gap"), True), mulv("psf_cohesion_penalty", settings["cohesion_gap_penalty"], True), subv("psf_cohesion_change", "psf_cohesion_penalty", True),
                addv(av(aid, "cohesion"), "psf_cohesion_change"), clamp(av(aid, "cohesion"), 0, 100)]
        for g in p["groups"]:
            body.append(conditional([check(av(aid, "cohesion"), settings["coalition_fracture_threshold"], "less_than"),
                                     check(av(aid, "g_" + g["id"]), 1),
                                     block("OR", block("AND", check(av(aid, "role"), 1), check(ev(g["id"], "satisfaction"), settings["member_defection_satisfaction"], "less_than")),
                                           block("AND", block("NOT", check(av(aid, "role"), 1)), check(ev(g["id"], "satisfaction"), 100-settings["member_defection_satisfaction"], "greater_than")))],
                                    setv(av(aid, "g_" + g["id"]), 0), setv("psf_coalition_changed", 1)))
        body.append(conditional([check(av(aid, "cohesion"), 5, "less_than")], "psf_dissolve_" + aid + " = yes", setv("psf_coalition_changed", 1)))
        out.append(conditional([check(av(aid, "active"), 1)], body))
    out += ["clr_country_flag = psf_batch_update", f"psf_refresh_{p['id']} = yes",
            setv("psf_legitimacy_change", settings["monthly_legitimacy_recovery"]),
            setv("psf_alignment_loss", "psf_alignment_gap", True), mulv("psf_alignment_loss", settings["alignment_penalty"], True),
            subv("psf_legitimacy_change", "psf_alignment_loss"),
            setv("psf_satisfaction_bonus", "psf_government_satisfaction", True), subv("psf_satisfaction_bonus", 50, True), divv("psf_satisfaction_bonus", 100, True),
            addv("psf_legitimacy_change", "psf_satisfaction_bonus"),
            conditional([check("psf_caretaker", 1)], subv("psf_legitimacy_change", 1)),
            addv("psf_legitimacy", "psf_legitimacy_change"), clamp("psf_legitimacy", 0, 100),
            conditional([check("psf_elections_enabled", 1)], addv("psf_election_clock", 1),
                        conditional([check("psf_election_clock", "psf_election_term", "greater_than_or_equals")], "psf_hold_election_" + p["id"] + " = yes")),
            conditional(["is_ai = no", check("psf_coalition_changed", 1)], "country_event = { id = psf.2 }"),
            "psf_refresh_modifiers = yes", "psf_export_popularity = yes"]
    return block("psf_monthly_" + p["id"], out)


def bridge_effects(manifest: dict, p: dict) -> list[Block]:
    """Project party approval onto four native slots; retain a delta import log."""
    out = []
    export: list[Block | str] = []
    for engine in ENGINE_IDEOLOGIES:
        export.append(setv("psf_engine_" + engine, 0))
    export.append(setv("psf_engine_total", 0, True))
    for g in p["groups"]:
        if not g["electoral"]:
            continue
        for ideology in manifest["ideologies"]:
            export.append(conditional([active(g), check(gv(g["id"], "ideology"), ideology["_index"])],
                                      addv("psf_engine_" + ideology["engine_ideology"], ev(g["id"], "support")), addv("psf_engine_total", ev(g["id"], "support"), True)))
    normalise: list[Block | str] = []
    for engine in ENGINE_IDEOLOGIES:
        normalise += [divv("psf_engine_" + engine, "psf_engine_total"), mulv("psf_engine_" + engine, 100)]
    normalise += [block("set_popularities", [f"{i} = var:psf_engine_{i}" for i in ENGINE_IDEOLOGIES])]
    # Store the engine's post-normalization result, including engine rounding.
    for engine in ENGINE_IDEOLOGIES:
        normalise.append(setv("psf_last_" + engine, "party_popularity_100@" + engine))
    export.append(conditional([check("psf_engine_total", 0, "greater_than")], normalise))
    out.append(block("psf_export_popularity_" + p["id"], "psf_import_popularity = yes", export))
    imported: list[Block | str] = [setv("psf_import_was_batched", 0, True),
        conditional(["has_country_flag = psf_batch_update"], setv("psf_import_was_batched", 1, True)),
        "set_country_flag = psf_batch_update"]
    for engine in ENGINE_IDEOLOGIES:
        imported += [setv("psf_engine_delta", "party_popularity_100@" + engine, True), subv("psf_engine_delta", "psf_last_" + engine, True),
                     setv("psf_engine_weight", 0, True), setv("psf_engine_members", 0, True)]
        compatible = [i["_index"] for i in manifest["ideologies"] if i["engine_ideology"] == engine]
        for g in p["groups"]:
            if g["electoral"]:
                imported.append(conditional([active(g), block("OR", [check(gv(g["id"], "ideology"), i) for i in compatible])],
                                            addv("psf_engine_weight", ev(g["id"], "support"), True), addv("psf_engine_members", 1, True)))
        for g in p["groups"]:
            if not g["electoral"]:
                continue
            body = [setv("psf_share_delta", "psf_engine_delta", True),
                    conditional([check("psf_total_party_support", 0, "greater_than")], mulv("psf_share_delta", "psf_total_party_support", True), divv("psf_share_delta", 100, True)),
                    conditional([check("psf_engine_weight", 0, "greater_than")], mulv("psf_share_delta", ev(g["id"], "support"), True), divv("psf_share_delta", "psf_engine_weight", True)),
                    conditional([check("psf_engine_weight", 0), check("psf_engine_members", 0, "greater_than")], divv("psf_share_delta", "psf_engine_members", True)),
                    conditional([check(gv(g["id"], "modifier_factor_support"), 0, "greater_than")], divv("psf_share_delta", gv(g["id"], "modifier_factor_support"), True)),
                    conditional([check(gv(g["id"], "modifier_factor_support"), 0)], setv("psf_share_delta", 0, True)),
                    addv(gv(g["id"], "support"), "psf_share_delta"), clamp(gv(g["id"], "support"), 0, 100)]
            imported.append(conditional([active(g), block("OR", [check(gv(g["id"], "ideology"), i) for i in compatible])], body))
    imported += [f"psf_refresh_{p['id']} = yes"]
    imported += [setv("psf_last_" + engine, "party_popularity_100@" + engine) for engine in ENGINE_IDEOLOGIES]
    imported.append(conditional([check("psf_import_was_batched", 0)], "clr_country_flag = psf_batch_update"))
    pending = block("OR", [block("NOT", check("psf_last_" + engine, "party_popularity_100@" + engine)) for engine in ENGINE_IDEOLOGIES])
    requirements = [flag(p), *("has_variable = psf_last_" + engine for engine in ENGINE_IDEOLOGIES), pending]
    out.append(block("psf_import_popularity_" + p["id"], conditional(requirements, imported)))
    import_government: list[Block | str] = ["psf_prepare_change = yes", setv("psf_winning_group", 0), setv("psf_candidate_weight", -1, True)]
    for g in p["groups"]:
        if not g["electoral"]:
            continue
        matches = [block("AND", "has_government = " + i["engine_ideology"], check(gv(g["id"], "ideology"), i["_index"])) for i in manifest["ideologies"]]
        import_government.append(conditional([block("OR", matches), check(ev(g["id"], "support"), "psf_candidate_weight", "greater_than")],
                                            setv("psf_candidate_weight", ev(g["id"], "support"), True), setv("psf_winning_group", g["_index"])))
    for g in p["groups"]:
        import_government.append(conditional([check("psf_winning_group", g["_index"])], setv(gv(g["id"], "status"), 1), setv(gv(g["id"], "prohibited"), 0), clamp(gv(g["id"], "influence"), 10, 100)))
    import_government.append(conditional([check("psf_winning_group", 0, "greater_than")], "psf_form_cabinet_" + p["id"] + " = yes"))
    out.append(block("psf_import_government_" + p["id"], import_government))
    return out


def effects(manifest: dict) -> str:
    all_profiles = profiles(manifest)
    out: list[Block | str] = ["# Generated by PSF. Edit the schema-validated manifest, then recompile.",
                             classify(manifest, "psf_gov_", "psf_government_ideology")]
    # Correct public classifier name is psf_classify_government.
    for p in all_profiles:
        out += [initialize_effect(manifest, p), refresh_effect(manifest, p), monthly_effect(manifest, p), charts.refresh_effect(manifest, p)]
        for g in p["groups"]:
            out.extend(group_effects(manifest, p, g))
        for a in p["alliances"]:
            out.extend(alliance_effects(manifest, p, a))
        out.extend(election_effect(manifest, p))
        out.extend(bridge_effects(manifest, p))
    for regime in manifest["regimes"]:
        out.append(block("psf_set_regime_" + regime["id"], conditional(["psf_is_initialized = yes"],
                         "psf_prepare_change = yes", "custom_effect_tooltip = psf_effect_regime_" + regime['id'], setv("psf_regime", regime["_index"]), finish())))
    initialize = []
    for index, p in enumerate(all_profiles):
        condition = "tag = " + p["tag"] if "tag" in p else "has_government = " + p["engine_ideology"]
        initialize.append(conditional([condition], "psf_init_" + p["id"] + " = yes", kind="if" if index == 0 else "else_if"))
    out.append(block("psf_initialize", conditional(["NOT = { has_country_flag = psf_initialized }"], initialize)))
    migration: list[Block | str] = [
        conditional(["NOT = { has_variable = psf_governing_group }"], setv("psf_governing_group", 0)),
        conditional(["NOT = { has_variable = psf_identity }"], setv("psf_identity", 0)),
    ]
    for p in all_profiles:
        valid = [check("psf_governing_alliance", 0)] + [check("psf_governing_alliance", a["_index"]) for a in p["alliances"]]
        recover: list[Block | str] = [setv("psf_governing_alliance", 0), setv("psf_migration_weight", -1, True)]
        for g in p["groups"]:
            recover.append(conditional([check(gv(g["id"], "governing"), 1), legal(g),
                                        check(gv(g["id"], "effective_influence"), "psf_migration_weight", "greater_than")],
                                       setv("psf_governing_group", g["_index"]),
                                       setv("psf_migration_weight", gv(g["id"], "effective_influence"), True)))
        migration.append(conditional([flag(p), block("NOT", block("OR", valid))], recover))
    migration.append(setv("psf_schema_version", 2))
    out.append(block("psf_upgrade_runtime", conditional([check("psf_schema_version", 2, "less_than")], migration)))
    # History and GUI entrypoints can rebuild immediately, without applying a
    # day of drift, expiring sources or reinitializing an existing campaign.
    out.append(block("psf_bootstrap",
        conditional(["has_country_flag = psf_initialized"], "psf_upgrade_runtime = yes", "psf_import_popularity = yes", "psf_refresh = yes", "psf_export_popularity = yes"),
        block("else", "psf_initialize = yes"), "psf_finish_frontend = yes"))
    # Only generated country-history files call this resettable entry point.
    # Date blocks can replace native politics after a root initialization; the
    # last applicable history block must therefore select its own fallback.
    out.append(block("psf_history_bootstrap", "clr_country_flag = psf_initialized",
                     ["clr_country_flag = psf_profile_" + p["id"] for p in all_profiles],
                     "psf_initialize = yes"))
    for action in ("refresh", "monthly", "hold_election", "import_popularity", "export_popularity", "import_government"):
        body = [conditional([flag(p)], f"psf_{action}_{p['id']} = yes", kind="if" if i == 0 else "else_if") for i, p in enumerate(all_profiles)]
        if action == "import_popularity" and manifest["settings"]["bridge_mode"] != "bidirectional":
            body = ["# Disabled by the manifest's bridge_mode."]
        if action in ("export_popularity", "import_government") and manifest["settings"]["bridge_mode"] == "none":
            body = ["# Disabled by the manifest's bridge_mode."]
        out.append(block("psf_" + action, body))
    out.append(block("psf_commit_transaction", "clr_country_flag = psf_batch_update", "psf_refresh = yes", "psf_export_popularity = yes"))
    clear_body: list[Block | str] = ["psf_prepare_change = yes", "custom_effect_tooltip = psf_effect_clear_government",
                                   setv("psf_governing_group", 0), setv("psf_governing_alliance", 0)]
    for p in all_profiles:
        if p["alliances"]:
            clear_body.append(conditional([flag(p)], [conditional([check(av(a["id"], "role"), 1)], setv(av(a["id"], "role"), 2)) for a in p["alliances"]]))
    clear_body.append(finish())
    out.append(block("psf_clear_government", conditional(["psf_is_initialized = yes"], clear_body)))
    capture: list[Block | str] = []
    for i, engine in enumerate(ENGINE_IDEOLOGIES, 1):
        capture.append(conditional(["has_government = " + engine], setv("psf_last_engine_government", i)))
    out.append(block("psf_capture_engine_government", capture))
    bridge = ["set_country_flag = psf_bridge_busy"]
    for ideology in manifest["ideologies"]:
        bridge.append(conditional([check("psf_government_ideology", ideology["_index"]), "NOT = { has_government = " + ideology["engine_ideology"] + " }"], block("set_politics", "ruling_party = " + ideology["engine_ideology"])))
    bridge += ["psf_capture_engine_government = yes", "clr_country_flag = psf_bridge_busy"]
    out.append(block("psf_export_government", bridge if manifest["settings"]["bridge_mode"] != "none" else ["# Engine government projection disabled."]))
    generic_actions = {"ban": "ban", "legalize": "legalize", "activate": "activate", "underground": "underground", "deactivate": "deactivate",
                       "add_support": "add", "add_influence": "add", "add_satisfaction": "add"}
    for action in generic_actions:
        nodes = []
        for p in all_profiles:
            for g in p["groups"]:
                target = f"psf_add_{g['id']}_{action.removeprefix('add_')}" if action.startswith("add_") else f"psf_{action}_{g['id']}"
                nodes.append(conditional([flag(p), check("psf_group", g["_index"])], target + " = yes"))
        out.append(block("psf_" + action + "_group", nodes))
    out.append(block("psf_govern_group", [conditional([flag(p), check("psf_group", g["_index"])], "psf_govern_group_" + g["id"] + " = yes")
                                         for p in all_profiles for g in p["groups"]]))
    out.extend(modifiers.effects(manifest))
    out.extend(identity.definitions(manifest))
    out.extend(mechanics.definitions(manifest))
    out.extend(frontend.runtime_effects(manifest))
    return emit(out) + "\n"


def triggers(manifest: dict) -> str:
    out: list[Block | str] = []
    for p in profiles(manifest):
        out.append(block("psf_has_profile_" + p["id"], flag(p)))
        for g in p["groups"]:
            gid = g["id"]
            for status, value in STATUS.items():
                out.append(block(f"psf_{gid}_is_{status}", flag(p), check(gv(gid, "prohibited"), 1) if status == "banned" else check(gv(gid, "status"), value)))
            out.append(block(f"psf_{gid}_is_suppressed", flag(p), check(gv(gid, "status"), 3)))
            out.append(block(f"psf_{gid}_is_governing", flag(p), governing_member(p, g).children))
            out.append(block(f"psf_{gid}_can_be_banned", flag(p), active(g), check(gv(gid, "status"), 3, "less_than"), block("NOT", governing_member(p, g))))
            for metric in ("support", "influence", "satisfaction"):
                out.append(block(f"psf_{gid}_{metric}_at_least", flag(p), check(ev(gid, metric), "psf_threshold", "greater_than_or_equals")))
        for a in p["alliances"]:
            aid = a["id"]
            out += [block("psf_" + aid + "_is_active", flag(p), check(av(aid, "active"), 1)),
                    block("psf_" + aid + "_is_government", flag(p), check("psf_governing_alliance", a["_index"]), check(av(aid, "active"), 1))]
            for g in p["groups"]:
                out.append(block(f"psf_{g['id']}_is_in_{aid}", flag(p), check(av(aid, "active"), 1), check(av(aid, "g_" + g["id"]), 1)))
    out.extend(modifiers.triggers(manifest))
    return emit(out) + "\n"
