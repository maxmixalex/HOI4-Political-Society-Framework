"""Playable policies, content events, AI and lifecycle integration."""
from __future__ import annotations

from .model import ENGINE_IDEOLOGIES, profiles, stable_id
from .runtime import active, av, ev, flag, gv, legal
from .script import Block, addv, block, check, clamp, conditional, emit, setv, subv


def op_effect(op: dict) -> list[Block | str]:
    name = op["op"]
    if name in ("activate", "ban", "legalize", "underground", "deactivate"):
        return [f"psf_{name}_{op['group']} = yes"]
    if name in ("support", "influence", "satisfaction"):
        return [setv("psf_amount", op["value"], True), f"psf_add_{op['group']}_{name} = yes"]
    if name in ("add_modifier", "remove_modifier"):
        action = "add" if name == "add_modifier" else "remove"
        return [f"psf_{action}_{op['group']}_modifier_{op['modifier']} = yes"]
    if name in ("join", "leave"):
        return [f"psf_{name}_{op['alliance']}_{op['group']} = yes"]
    if name in ("govern", "dissolve"):
        return [f"psf_{name}_{op['alliance']} = yes"]
    if name == "govern_group":
        return [f"psf_govern_group_{op['group']} = yes"]
    if name == "clear_government":
        return ["psf_clear_government = yes"]
    if name == "regime":
        return [f"psf_set_regime_{op['regime']} = yes"]
    if name == "legitimacy":
        return [setv("psf_amount", op["value"], True), "psf_add_legitimacy = yes"]
    if name == "position":
        return [setv("psf_position", op["value"], True), f"psf_set_{op['group']}_position_{op['axis']} = yes"]
    if name == "cohesion":
        return [setv("psf_amount", op["value"], True), f"psf_add_{op['alliance']}_cohesion = yes"]
    raise ValueError(name)


def events(manifest: dict) -> str:
    out: list[Block | str] = ["add_namespace = psf", "add_namespace = psf_content"]
    for number in (1, 2):
        out.append(block("country_event", f"id = psf.{number}", f"title = psf_event_{number}_title", f"desc = psf_event_{number}_desc", "is_triggered_only = yes",
                         block("option", "name = psf_acknowledge")))
    for scenario in manifest["scenarios"]:
        options = []
        for i, option in enumerate(scenario["options"]):
            actions: list[Block | str] = ["psf_begin_transaction = yes"]
            for operation in option["effects"]:
                actions += op_effect(operation)
            actions += ["psf_commit_transaction = yes", "psf_export_popularity = yes"]
            options.append(block("option", "name = psf_scenario_" + scenario["id"] + "_" + option["id"],
                                 block("ai_chance", "base = " + str(option.get("ai_chance", 70 if i == 0 else 30))), actions))
        out.append(block("country_event", f"id = psf_content.{stable_id(scenario['id'])}", "title = psf_scenario_" + scenario["id"] + "_title",
                         "desc = psf_scenario_" + scenario["id"] + "_desc", "is_triggered_only = yes", options))
    return emit(out) + "\n"


def rules(manifest: dict) -> str:
    enabled = manifest["settings"]["scenarios_enabled"]
    return emit([block("psf_content_events", "name = psf_rule_events", "group = psf_rule_group",
                       block("default" if enabled else "option", "name = ENABLED", "text = psf_rule_enabled", "desc = psf_rule_events_enabled_desc", "allow_achievements = no"),
                       block("option" if enabled else "default", "name = DISABLED", "text = psf_rule_disabled", "desc = psf_rule_events_disabled_desc", "allow_achievements = no"))]) + "\n"


def on_actions(manifest: dict) -> str:
    weekly: list[Block | str] = ["psf_initialize = yes"]
    if manifest["settings"]["bridge_mode"] == "bidirectional":
        weekly += ["psf_import_popularity = yes", "psf_export_popularity = yes"]
    for scenario in manifest["scenarios"]:
        weekly.append(conditional(["has_game_rule = { rule = psf_content_events option = ENABLED }",
                                   "has_country_flag = psf_profile_" + scenario["profile"],
                                   "NOT = { has_country_flag = psf_scenario_" + scenario["id"] + " }", "date > " + scenario["date"]],
                                  "set_country_flag = psf_scenario_" + scenario["id"], f"country_event = {{ id = psf_content.{stable_id(scenario['id'])} }}"))
    changed = [conditional(["has_country_flag = psf_initialized", "NOT = { has_country_flag = psf_bridge_busy }"],
                           "psf_import_government = yes", "psf_capture_engine_government = yes")]
    # on_daily already runs in country scope: wrapping every_country here would
    # apply N days of drift per day in a world containing N countries.
    out = [block("on_startup", block("effect", block("every_country", "psf_bootstrap = yes"))),
           block("on_daily", block("effect", "psf_initialize = yes", "psf_daily_modifiers = yes")),
           block("on_weekly", block("effect", weekly)),
           block("on_monthly", block("effect", "psf_initialize = yes", "psf_monthly = yes", "psf_ai_governance = yes")),
           block("on_release_as_free", block("effect", "psf_bootstrap = yes")),
           block("on_release_as_puppet", block("effect", "psf_bootstrap = yes"))]
    if manifest["settings"]["bridge_mode"] == "bidirectional":
        out.append(block("on_government_change", block("effect", changed)))
    elif manifest["settings"].get("mechanics_mode", "compat") == "strict":
        out.append(block("on_government_change", block("effect", conditional(
            ["has_country_flag = psf_initialized", "NOT = { has_country_flag = psf_bridge_busy }"],
            "psf_export_government = yes"))))
    return emit([block("on_actions", out)]) + "\n"


def ai_effects(manifest: dict) -> str:
    out: list[Block | str] = []
    branches = []
    for p in profiles(manifest):
        nodes: list[Block | str] = [
            conditional(["has_political_power > 75", check("psf_legitimacy", 45, "less_than")], "add_political_power = -50", "psf_rebuild_public_confidence = yes"),
        ]
        recover: list[Block | str] = [setv("psf_candidate_weight", -1, True), setv("psf_winning_group", 0)]
        for g in p["groups"]:
            recover.append(conditional([legal(g), check(gv(g["id"], "effective_influence"), "psf_candidate_weight", "greater_than")],
                                       setv("psf_candidate_weight", gv(g["id"], "effective_influence"), True), setv("psf_winning_group", g["_index"])))
        recover.append("psf_form_cabinet_" + p["id"] + " = yes")
        nodes.append(conditional([check("psf_caretaker", 1)], recover))
        for a in p["alliances"]:
            nodes.append(conditional(["has_political_power > 60", check("psf_governing_alliance", a["_index"]), check(av(a["id"], "cohesion"), 40, "less_than")],
                                     "add_political_power = -30", addv(av(a["id"], "cohesion"), 8),
                                     [conditional([check(av(a["id"], "g_" + g["id"]), 1)], addv(gv(g["id"], "satisfaction"), 4)) for g in p["groups"]]))
        nodes.append("psf_refresh = yes")
        branches.append(conditional([flag(p)], nodes, kind="if" if not branches else "else_if"))
    out.append(block("psf_ai_governance", conditional(["is_ai = yes", "psf_is_initialized = yes"], branches)))
    return emit(out) + "\n"


def decision(name: str, visible: list[Block | str], available: list[Block | str], effects: list[Block | str], cost: int,
             cooldown: int = 30) -> Block:
    return block(name, "icon = generic_political_discourse", "cost = " + str(cost),
                 block("visible", "has_country_flag = psf_initialized", visible),
                 block("available", available), "days_re_enable = " + str(cooldown),
                 block("complete_effect", effects), block("ai_will_do", "factor = 0"))


def categories() -> str:
    return emit([block("psf_government_category", "icon = generic_political_discourse", block("visible", "psf_is_initialized = yes")),
                 block("psf_groups_category", "icon = generic_political_discourse", block("visible", "psf_is_initialized = yes")),
                 block("psf_alliances_category", "icon = generic_political_discourse", block("visible", "psf_is_initialized = yes")),
                 block("psf_institutions_category", "icon = generic_political_discourse", block("visible", "psf_is_initialized = yes"))]) + "\n"


def decisions(manifest: dict) -> str:
    government: list[Block | str] = [
        decision("psf_public_consultation", [], [check("psf_legitimacy", 95, "less_than")], ["psf_rebuild_public_confidence = yes"], 50, 60),
        decision("psf_snap_election", ["psf_has_elections = yes"], [check("psf_election_clock", 6, "greater_than_or_equals")], ["psf_hold_election = yes"], 100, 180),
        decision("psf_appoint_caretaker", [], [check("psf_caretaker", 0)], ["psf_clear_government = yes"], 50, 90),
        decision("psf_open_society_view", [], [], [setv("psf_ui_open", 1), setv("psf_ui_page", 0)], 0, 1),
    ]
    groups: list[Block | str] = []
    alliances: list[Block | str] = []
    institutions: list[Block | str] = []
    for p in profiles(manifest):
        for g in p["groups"]:
            gid = g["id"]
            selected = [flag(p), check("psf_ui_group", g["_index"])]
            entries = [
                ("ban", [f"psf_{gid}_can_be_banned = yes"], [f"psf_ban_{gid} = yes"], 50, 60),
                ("legalize", [check(gv(gid, "status"), 1, "greater_than")], [f"psf_legalize_{gid} = yes"], 25, 30),
                ("activate", [check(gv(gid, "status"), 0)], [f"psf_activate_{gid} = yes"], 25, 30),
                ("negotiate", [active(g), check(ev(gid, "satisfaction"), 95, "less_than"), check(gv(gid, "satisfaction"), 100, "less_than")], [setv("psf_amount", 10, True), f"psf_add_{gid}_satisfaction = yes"], 35, 60),
                ("campaign", [legal(g)], [setv("psf_amount", 4, True), f"psf_add_{gid}_support = yes"], 40, 60),
                ("empower", [legal(g)], [setv("psf_amount", 4, True), f"psf_add_{gid}_influence = yes"], 45, 90),
                ("govern_group", [legal(g), check(gv(gid, "effective_influence"), 0, "greater_than"), block("NOT", check("psf_governing_group", g["_index"]))], [f"psf_govern_group_{gid} = yes"], 100, 90),
            ]
            for action, requirements, effects, cost, cooldown in entries:
                groups.append(decision(f"psf_policy_{action}_{gid}", selected, requirements, effects, cost, cooldown))
        for a in p["alliances"]:
            aid = a["id"]
            a_visible = [flag(p)]
            alliances += [decision("psf_policy_govern_" + aid, a_visible,
                                   ["NOT = { " + check("psf_governing_alliance", a["_index"]) + " }", block("OR", [block("AND", legal(g), check(av(aid, "g_" + g["id"]), 1), check(gv(g["id"], "effective_influence"), 0, "greater_than")) for g in p["groups"]])],
                                   ["psf_govern_" + aid + " = yes"], 100, 90),
                          decision("psf_policy_dissolve_" + aid, a_visible, [check(av(aid, "active"), 1)], ["psf_dissolve_" + aid + " = yes"], 25, 60),
                          decision("psf_policy_mediate_" + aid, a_visible, [check(av(aid, "active"), 1), check(av(aid, "cohesion"), 95, "less_than")],
                                   [setv("psf_amount", 10, True), "psf_add_" + aid + "_cohesion = yes"], 40, 60)]
            for g in p["groups"]:
                gid = g["id"]
                visibility = [flag(p), check("psf_ui_group", g["_index"])]
                alliances.append(decision(f"psf_policy_join_{aid}_{gid}", visibility,
                                          [active(g), check(av(aid, "g_" + gid), 0), block("OR", block("NOT", check("psf_governing_alliance", a["_index"])), legal(g))],
                                          [f"psf_join_{aid}_{gid} = yes"], 30, 30))
                alliances.append(decision(f"psf_policy_leave_{aid}_{gid}", visibility, [check(av(aid, "g_" + gid), 1)], [f"psf_leave_{aid}_{gid} = yes"], 10, 30))
    for regime in manifest["regimes"]:
        institutions.append(decision("psf_policy_regime_" + regime["id"], [], [block("NOT", check("psf_regime", regime["_index"])), check("psf_legitimacy", 35, "greater_than_or_equals")],
                                     ["psf_set_regime_" + regime["id"] + " = yes", setv("psf_amount", -8, True), "psf_add_legitimacy = yes"], 150, 180))
    return emit([block("psf_government_category", government), block("psf_groups_category", groups), block("psf_alliances_category", alliances), block("psf_institutions_category", institutions)]) + "\n"
