"""Country-selection politics through the engine's native party-name binding.

The front end has no documented scripted-GUI country context. Country history
can, however, set party names, and both native selection panels already resolve
the selected country's party field. A temporary, date-specific presentation
key supplies a dedicated political block there. Campaign startup and opening
the campaign political interface restore ordinary party names.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
import math
from pathlib import Path
import unicodedata

from . import charts, icons
from .model import ENGINE_IDEOLOGIES
from .localization import LANGUAGES, write_localization
from .script import Block, block, conditional, quoted


def states(profile: dict) -> list[str | None]:
    return [None, *sorted({item["date"] for item in profile.get("start_overrides", [])},
                         key=lambda value: tuple(map(int, value.split("."))))]


def state_id(profile: dict, day: str | None) -> str:
    return profile["id"] + "_" + (day.replace(".", "_") if day else "base")


def applied_profile(profile: dict, day: str | None) -> dict:
    result = copy.deepcopy(profile)
    if "government" not in result:
        result["government"] = next(({"alliance": item["id"]} for item in result.get("alliances", [])
                                     if item["kind"] == "government"), None)
    groups = {item["id"]: item for item in result["groups"]}
    alliances = {item["id"]: item for item in result.get("alliances", [])}
    for override in sorted(result.pop("start_overrides", []), key=lambda item: tuple(map(int, item["date"].split(".")))):
        if day is None or tuple(map(int, override["date"].split("."))) > tuple(map(int, day.split("."))):
            continue
        for key in ("regime", "government", "legitimacy"):
            if key in override:
                result[key] = copy.deepcopy(override[key])
        for update in override.get("groups", []):
            target = groups[update["id"]]
            for key, value in update.items():
                if key == "positions":
                    target[key].update(value)
                elif key != "id":
                    target[key] = copy.deepcopy(value)
        for update in override.get("alliances", []):
            alliances[update["id"]].update(update)
            if update.get("kind") == "government" and "government" not in override:
                result["government"] = {"alliance": update["id"]}
    return result


def snapshot(manifest: dict, profile: dict, day: str | None) -> dict:
    current = applied_profile(profile, day)
    values = charts.bookmark_values(manifest, current, day or "1936.1.1")
    government = current.get("government")
    member_ids = []
    if government:
        if "group" in government:
            member_ids = [government["group"]]
        else:
            member_ids = next((item["members"] for item in current.get("alliances", [])
                               if item["id"] == government["alliance"]), [])
    members = [item for item in current["groups"] if item["id"] in member_ids
               and item.get("status", "legal") == "legal"]
    weights = {item["id"]: weight for item, weight in zip(values["organizations"], values["weights"]["influence"])}
    total = math.fsum(weights[item["id"]] for item in members)
    # Match runtime.psf_government_leader_group: the strongest governing party
    # represents a coalition even when its army or court has greater influence.
    parties = [item for item in members if item.get("electoral", False) or item.get("kind") == "party"]
    candidates = parties or members
    ruling = max(candidates, key=lambda item: (weights[item["id"]], -item.get("_index", 0))) if candidates and total else None
    positions = {axis["id"]: math.fsum(item["positions"][axis["id"]] * weights[item["id"]]
                                      for item in members) / total
                 for axis in manifest.get("axes", [])} if total else {}
    ideology = icons.closest_ideology(manifest, {"positions": positions}) if ruling else None
    regime = next(item for item in manifest["regimes"] if item["id"] == current["regime"])
    native = {}
    for engine in ENGINE_IDEOLOGIES:
        candidates = [item for item in current["groups"] if item.get("status", "legal") != "inactive"
                      and item.get("electoral", item.get("kind", "party") == "party")
                      and icons.closest_ideology(manifest, item).get("engine_ideology") == engine]
        native[engine] = max(candidates, key=lambda item: (item.get("support", 0), -item.get("_index", 0))) if candidates else None
    return {"id": state_id(profile, day), "profile": current, "day": day,
            "ruling_group": ruling, "regime": regime, "ideology": ideology,
            "native_parties": native, "support": values["support"], "influence": values["influence"]}


def _limit_label(value: str, columns: int = 22) -> str:
    value = " ".join(value.split())
    width = lambda char: 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    if sum(width(char) for char in value) <= columns:
        return value
    out, used = [], 0
    for char in value:
        if used + width(char) > columns - 2:
            break
        out.append(char)
        used += width(char)
    return "".join(out) + "…"


def _name(item: dict | None, language: str, short: bool = False) -> str:
    if item is None:
        return "Caretaker government" if language == "english" else "看守政府"
    return item.get("short_name", item["name"])[language] if short else item["name"][language]


def panel_text(state: dict, image: dict, language: str) -> str:
    group = state["ruling_group"]
    regime_label = "Regime" if language == "english" else "政体"
    title = (icons.texticon(group) + " " if group else "") + "§Y" + _limit_label(_name(group, language, True)) + "§!"
    regime = regime_label + ": §Y" + _limit_label(_name(state["regime"], language), 20) + "§!"
    heading = "Support / Influence" if language == "english" else "支持率 / 影响力"
    ideology = state["ideology"]
    large_party = "£" + (icons.sprite(group) if group else "GFX_ideology_unknown").removeprefix("GFX_") + "£"
    large_ideology = "£" + (icons.sprite(ideology, "ideology") if ideology else "GFX_ideology_unknown").removeprefix("GFX_") + "£"
    pie = "£" + image["sprite"].removeprefix("GFX_") + "£"
    # The large images occupy their own reserved block below the three text
    # rows. The native party textbox sits inside a bounded political region;
    # no part of this payload is written to the historical description.
    return "\n".join((title, regime, heading, "", "", large_party + " " + large_ideology + " " + pie))


def _party_effects(profile: dict, day: str | None, preview: bool) -> list[Block]:
    identifier = state_id(profile, day)
    return [block("set_party_name", "ideology = " + engine,
                  "name = psf_frontend_panel_" + identifier if preview else "name = psf_native_" + identifier + "_" + engine,
                  "long_name = psf_frontend_panel_" + identifier if preview else "long_name = psf_native_" + identifier + "_" + engine + "_long")
            for engine in ENGINE_IDEOLOGIES]


def runtime_effects(manifest: dict) -> list[Block]:
    """History calls prepare; campaign bootstrap/startup calls idempotent finish."""
    prepare, finish = [], []
    for index, profile in enumerate(manifest.get("profiles", []) + manifest.get("fallback_profiles", [])):
        incoming = _party_effects(profile, None, True)
        outgoing = _party_effects(profile, None, False)
        for day in states(profile)[1:]:
            previous = date(*map(int, day.split("."))) - timedelta(days=1)
            limit = [f"date > {previous.year}.{previous.month}.{previous.day}"]
            incoming.append(conditional(limit, _party_effects(profile, day, True)))
            outgoing.append(conditional(limit, _party_effects(profile, day, False)))
        condition = ["has_country_flag = psf_profile_" + profile["id"]]
        prepare.append(conditional(condition, incoming, "set_country_flag = psf_frontend_preview_active",
                                   kind="if" if index == 0 else "else_if"))
        finish.append(conditional(condition, outgoing, "clr_country_flag = psf_frontend_preview_active",
                                  kind="if" if index == 0 else "else_if"))
    return [
        block("psf_prepare_frontend", conditional(["has_country_flag = psf_initialized"],
              prepare)),
        block("psf_finish_frontend", conditional(["has_country_flag = psf_frontend_preview_active"],
              finish)),
    ]


def generate(manifest: dict, output: Path) -> dict:
    icons.generate_icons(manifest, output)
    report = {"implementation": "native selected-country party field with temporary history-initialized presentation names",
              "binding_enabled": manifest.get("settings", {}).get("mechanics_mode", "compat") == "strict",
              "history_overridden": False, "runtime_render_tested": False, "states": []}
    localisation = {language: {} for language in LANGUAGES}
    definitions = ["spriteTypes = {"]
    for profile in manifest.get("profiles", []) + manifest.get("fallback_profiles", []):
        for day in states(profile):
            state = snapshot(manifest, profile, day)
            current = copy.deepcopy(state["profile"])
            current["id"] = "frontend_" + state["id"]
            image = charts.bookmark_artwork(manifest, current, day or "1936.1.1", output)
            definitions.append(f"spriteType = {{ name = {quoted(image['sprite'])} texturefile = {quoted(image['texture'])} "
                               "noOfFrames = 1 legacy_lazy_load = no }")
            key = "psf_frontend_panel_" + state["id"]
            for language in LANGUAGES:
                localisation[language][key] = panel_text(state, image, language)
                for engine, group in state["native_parties"].items():
                    native_key = "psf_native_" + state["id"] + "_" + engine
                    absent = "No electoral organization" if language == "english" else "无参选团体"
                    localisation[language][native_key] = _name(group, language, True) if group else absent
                    localisation[language][native_key + "_long"] = _name(group, language) if group else absent
            report["states"].append({"id": state["id"], "profile": profile["id"], "date": day,
                                     "panel_key": key, "ruling_group": state["ruling_group"]["id"] if state["ruling_group"] else None,
                                     "regime": state["regime"]["id"], "ideology": state["ideology"]["id"] if state["ideology"] else None,
                                     **image})
    definitions.append("}")
    target = output / "interface/psf_frontend.gfx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(definitions) + "\n", encoding="utf-8")
    write_localization(output, "psf_frontend", localisation)
    return report


def patch_native(pick, hide, move, changes: list) -> None:
    """Preserve engine-owned field names and ancestry; replace only their layout."""
    def prop(node, key, value):
        previous = node.properties.get(key.lower())
        child = next((item for item in node.children if item.kind.lower() == key.lower()), None)
        replacement = key + " = " + value
        if previous:
            changes.append((previous[0], previous[1], replacement))
        elif child:
            changes.append((child.start, child.end, replacement))
        else:
            changes.append((node.opening + 1, node.opening + 1, "\n" + replacement + "\n"))
    hide("political_pie_chart", "gamesetup_country_details")
    hide("pol_faction_icon", "gamesetup_country_details")
    for parent in ("gamesetup_country_details", "gamesetup_interesting_countries_window"):
        if parent == "gamesetup_interesting_countries_window":
            hide("pol_faction_icon", parent)
        for name in ("ideology_label", "ideology", "government_label", "government", "elections_label", "elections"):
            hide(name, parent)
        panel = pick("info", parent)
        prop(panel, "clipping", "yes")
        party = pick("party", parent)
        prop(party, "format", "left")
        prop(party, "fixedsize", "yes")
        prop(party, "multiline", "yes")
        prop(party, "maxHeight", "170")
        prop(party, "font", '"hoi_18mbs"')
        label = pick("party_label", parent)
        prop(label, "text", '"RULING_PARTY"')
        prop(label, "font", '"hoi_18mbs"')
        if parent == "gamesetup_country_details":
            move(panel, changes, 0, 0)
            prop(panel, "size", "{ width = 492 height = 301 }")
            move(label, changes, 110, 10)
            move(party, changes, 110, 34)
            prop(party, "maxWidth", "350")
            move(pick("leader_label", parent), changes, 30, 204)
            move(pick("leader", parent), changes, 120, 204)
            for name in ("spirit_grid", "spirit_grid_over_defined"):
                move(pick(name, parent), changes, 30, 230)
        else:
            move(panel, changes, 35, 477)
            prop(panel, "size", "{ width = 305 height = 225 }")
            move(pick("info_title", parent), changes, 10, 445)
            move(pick("leader_label", parent), changes, 0, 0)
            move(pick("leader", parent), changes, 0, 17)
            prop(pick("leader", parent), "maxWidth", "305")
            move(label, changes, 0, 35)
            move(party, changes, 0, 52)
            prop(party, "maxWidth", "305")
            # Two 64-pixel identities and the 140-pixel dual pie need their
            # own width. Reclaim the unused gap before the native focus grid;
            # never widen the text through the portrait or into the history.
            move(pick("minor_country_leader", parent), changes, 349, 457)
            move(pick("minor_portrait_overlay", parent), changes, 340, 446)
            move(pick("nation_title", parent), changes, 477, 433)
            prop(pick("nation_title", parent), "maxWidth", "305")
    history = pick("history", "gamesetup_interesting_countries_window")
    prop(history, "maxHeight", "160")
    prop(history, "multiline", "yes")
    prop(history, "scrollbartype", '"standardtext_slider"')
