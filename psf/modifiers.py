"""Native organization modifiers and reversible named modifier sources.

Custom modifier definitions are a documented engine extension: their numbers
are read with modifier@token.  They are not invented built-in political stats.
Base values remain writable; every refresh derives effective values from them.
"""
from __future__ import annotations

from .model import profiles
from .script import Block, addv, block, check, clamp, conditional, emit, mulv, setv, subv

METRICS = ("support", "influence", "satisfaction")
KINDS = ("add", "factor", "daily")


def gv(group: str, field: str) -> str:
    return f"psf_g_{group}_{field}"


def modified_var(group: str, field: str) -> str:
    return gv(group, "modified_" + field)


def native_key(group: str, field: str, kind: str) -> str:
    return f"psf_{group}_{field}_{kind}"


def source_var(group: str, modifier: str, field: str) -> str:
    return f"psf_m_{group}_{modifier}_{field}"


def fields(manifest: dict) -> tuple[str, ...]:
    return (*METRICS, *("position_" + a["id"] for a in manifest["axes"]))


def bounds(field: str) -> tuple[int, int]:
    return (-100, 100) if field.startswith("position_") else (0, 100)


def applicable(manifest: dict, group: str) -> list[dict]:
    return [m for m in manifest.get("modifiers", []) if "groups" not in m or group in m["groups"]]


def values(modifier: dict, field: str) -> dict:
    if field.startswith("position_"):
        return modifier.get("positions", {}).get(field.removeprefix("position_"), {})
    return modifier.get("attributes", {}).get(field, {})


def definitions(manifest: dict) -> str:
    """Declare real HOI4 modifier keys usable in ideas, traits and dynamics."""
    out: list[Block | str] = [
        "# Custom modifiers: see the vanilla common/modifier_definitions documentation.",
        "# Consumed via modifier@ by PSF; country scope, additive sources.",
    ]
    for profile in profiles(manifest):
        for group in profile["groups"]:
            for field in fields(manifest):
                for kind in KINDS:
                    out.append(block(native_key(group["id"], field, kind),
                                     "color_type = neutral", "value_type = " + ("percentage" if kind == "factor" else "number"),
                                     "precision = 2", "postfix = " + ("daily" if kind == "daily" else "none"),
                                     "category = country", "category = politics"))
    return emit(out) + "\n"


def recalculate_group(manifest: dict, group: dict) -> list[Block | str]:
    """Rebuild, never subtract a previously clamped bonus from a base value."""
    gid = group["id"]
    sources = applicable(manifest, gid)
    out: list[Block | str] = [setv(gv(gid, "modifier_count"), 0), setv("psf_position_changed", 0, True)]
    for modifier in sources:
        out.append(conditional([check(source_var(gid, modifier["id"], "active"), 1)], addv(gv(gid, "modifier_count"), 1)))
    for field in fields(manifest):
        base, current = gv(gid, field), modified_var(gid, field)
        out += [clamp(base, *bounds(field)), setv("psf_previous_attribute", current, True),
                setv("psf_attribute_add", "modifier@" + native_key(gid, field, "add"), True),
                setv("psf_attribute_factor", 1, True),
                addv("psf_attribute_factor", "modifier@" + native_key(gid, field, "factor"), True)]
        for modifier in sources:
            change = values(modifier, field)
            contributions = []
            if change.get("add", 0):
                contributions.append(addv("psf_attribute_add", change["add"], True))
            if change.get("factor", 0):
                contributions.append(addv("psf_attribute_factor", change["factor"], True))
            if contributions:
                out.append(conditional([check(source_var(gid, modifier["id"], "active"), 1)], contributions))
        out += [conditional([check("psf_attribute_factor", 0, "less_than")], setv("psf_attribute_factor", 0, True)),
                setv(gv(gid, "modifier_add_" + field), "psf_attribute_add"),
                setv(gv(gid, "modifier_factor_" + field), "psf_attribute_factor"),
                setv(current, base), addv(current, "psf_attribute_add"), mulv(current, "psf_attribute_factor"),
                clamp(current, *bounds(field))]
        if field.startswith("position_"):
            out.append(conditional([block("NOT", check(current, "psf_previous_attribute"))], setv("psf_position_changed", 1, True)))
    out.append(conditional([block("OR", check("psf_position_changed", 1), "NOT = { has_variable = " + gv(gid, "ideology") + " }")],
                           f"psf_classify_g_{gid} = yes"))
    return out


def initialize_group(manifest: dict, group: dict) -> list[Block | str]:
    out = []
    for modifier in applicable(manifest, group["id"]):
        out += [setv(source_var(group["id"], modifier["id"], "active"), 0),
                setv(source_var(group["id"], modifier["id"], "days"), 0)]
    return out


def _finish() -> Block:
    # Capture the projected engine totals in this same update. Otherwise a later
    # bidirectional bridge can mistake PSF's own change for a native delta.
    return conditional(["NOT = { has_country_flag = psf_batch_update }"],
                       "psf_refresh = yes", "psf_export_popularity = yes")


def group_effects(manifest: dict, profile: dict, group: dict) -> list[Block]:
    gid = group["id"]
    guard = "has_country_flag = psf_profile_" + profile["id"]
    out = []
    removals = []
    for modifier in applicable(manifest, gid):
        mid = modifier["id"]
        active, days = source_var(gid, mid, "active"), source_var(gid, mid, "days")
        for timed in (False, True):
            action = "add_timed" if timed else "add"
            body: list[Block | str] = ["psf_prepare_change = yes"]
            if timed:
                # Use the same normalized value for the duration and tooltip.
                # Preserve psf_days so callers can reuse their input unchanged.
                body += [setv("psf_modifier_days", "psf_days", True),
                         "round_temp_variable = psf_modifier_days", clamp("psf_modifier_days", 1, 36500, True)]
            body += ["custom_effect_tooltip = psf_effect_" + action + "_" + gid + "_modifier_" + mid,
                     setv(active, 1), setv(days, "psf_modifier_days" if timed else modifier["duration_days"]), _finish()]
            out.append(block(f"psf_{action}_{gid}_modifier_{mid}",
                             conditional([guard, *([check("psf_days", 0, "greater_than")] if timed else [])], body)))
        clear = [setv(active, 0), setv(days, 0)]
        removals.append(conditional([check(active, 1)], clear))
        out.append(block(f"psf_remove_{gid}_modifier_{mid}", conditional([guard, check(active, 1)], "psf_prepare_change = yes",
            "custom_effect_tooltip = psf_effect_remove_" + gid + "_modifier_" + mid, clear, _finish())))
    out.append(block("psf_clear_" + gid + "_modifiers", conditional([guard], "psf_prepare_change = yes", removals, _finish())))
    return out


def daily_effect(manifest: dict, profile: dict) -> Block:
    # Import any real native ideology movement before exporting the new PSF
    # values. Export-only daily updates would silently erase native drift.
    out: list[Block | str] = ["psf_import_popularity = yes"]
    for group in profile["groups"]:
        gid = group["id"]
        sources = applicable(manifest, gid)
        drift: list[Block | str] = []
        for field in fields(manifest):
            change: list[Block | str] = [setv("psf_daily_attribute", "modifier@" + native_key(gid, field, "daily"), True)]
            for modifier in sources:
                amount = values(modifier, field).get("daily", 0)
                if amount:
                    change.append(conditional([check(source_var(gid, modifier["id"], "active"), 1)], addv("psf_daily_attribute", amount, True)))
            change += [addv(gv(gid, field), "psf_daily_attribute"), clamp(gv(gid, field), *bounds(field))]
            drift += change
        # Inactive organizations do not accumulate political activity. Calendar
        # duration still expires, so suspension does not turn a 30-day source
        # into a permanent bonus.
        out.append(conditional([check(gv(gid, "status"), 0, "greater_than")], drift))
        for modifier in sources:
            active, days = source_var(gid, modifier["id"], "active"), source_var(gid, modifier["id"], "days")
            out.append(conditional([check(active, 1), check(days, 0, "greater_than")],
                                   subv(days, 1), conditional([check(days, 0, "less_than_or_equals")], setv(active, 0), setv(days, 0))))
    out += ["psf_refresh = yes", "psf_export_popularity = yes"]
    return block("psf_daily_modifiers_" + profile["id"], conditional(["has_country_flag = psf_profile_" + profile["id"]], out))


def effects(manifest: dict) -> list[Block]:
    out = []
    groups = [(p, g) for p in profiles(manifest) for g in p["groups"]]
    for p in profiles(manifest):
        out.append(daily_effect(manifest, p))
        for g in p["groups"]:
            out.extend(group_effects(manifest, p, g))
    out.append(block("psf_daily_modifiers", conditional(["has_country_flag = psf_initialized"],
        [conditional(["has_country_flag = psf_profile_" + p["id"]], "psf_daily_modifiers_" + p["id"] + " = yes", kind="if" if i == 0 else "else_if")
         for i, p in enumerate(profiles(manifest))])))
    for action in ("add", "add_timed", "remove"):
        branches = []
        for p, g in groups:
            for m in applicable(manifest, g["id"]):
                branches.append(conditional(["has_country_flag = psf_profile_" + p["id"], check("psf_group", g["_index"]), check("psf_modifier", m["_index"])],
                                           f"psf_{action}_{g['id']}_modifier_{m['id']} = yes"))
        if branches:
            out.append(block("psf_" + action + "_group_modifier", branches))
    return out


def triggers(manifest: dict) -> list[Block]:
    out = []
    generic = []
    for p in profiles(manifest):
        for g in p["groups"]:
            guard = "has_country_flag = psf_profile_" + p["id"]
            for modifier in applicable(manifest, g["id"]):
                active = check(source_var(g["id"], modifier["id"], "active"), 1)
                out.append(block(f"psf_{g['id']}_has_modifier_{modifier['id']}", guard, active))
                generic.append(block("AND", guard, check("psf_group", g["_index"]), check("psf_modifier", modifier["_index"]), active))
    out.append(block("psf_group_has_modifier", block("OR", generic) if generic else "always = no"))
    return out


def localizations(manifest: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {"english": {}, "simp_chinese": {}}
    axes = {a["id"]: a for a in manifest["axes"]}
    metric_labels = {"support": ("support", "支持率"), "influence": ("influence", "影响力"), "satisfaction": ("government satisfaction", "对政府满意度")}
    for p in profiles(manifest):
        for g in p["groups"]:
            gid = g["id"]
            for field in fields(manifest):
                for kind in KINDS:
                    for index, lang in enumerate(out):
                        attribute = axes[field.removeprefix("position_")]["name"][lang] if field.startswith("position_") else metric_labels[field][index]
                        suffix = {"add": ("", ""), "factor": (" factor", "系数"), "daily": (" daily change", "每日变化")}[kind][index]
                        out[lang][native_key(gid, field, kind)] = g["short_name"][lang] + (": " if index == 0 else "：") + attribute + suffix
            for m in applicable(manifest, gid):
                mid = m["id"]
                for lang in out:
                    out[lang]["psf_modifier_" + mid + "_name"] = m["name"][lang]
                    out[lang]["psf_modifier_" + mid + "_desc"] = m["description"][lang]
                    group_name = g["short_name"][lang]
                    name = m["name"][lang]
                    duration = m["duration_days"]
                    details = []
                    for field in fields(manifest):
                        attribute = (axes[field.removeprefix("position_")]["name"][lang]
                                     if field.startswith("position_") else metric_labels[field][0 if lang == "english" else 1])
                        for kind, amount in values(m, field).items():
                            if not amount:
                                continue
                            suffix = ({"add": "", "factor": " factor", "daily": " per day"}[kind]
                                      if lang == "english" else {"add": "", "factor": "系数", "daily": "每日变化"}[kind])
                            number = f"{amount * 100:+g}%" if kind == "factor" else f"{amount:+g}"
                            details.append(f"{attribute}{suffix}: {number}")
                    impact = "\n" + "\n".join(details) if details else ""
                    if lang == "english":
                        timing = "until removed" if duration == -1 else f"for {duration} days"
                        out[lang][f"psf_effect_add_{gid}_modifier_{mid}"] = f"{group_name}: gain {name} {timing}." + impact
                        out[lang][f"psf_effect_add_timed_{gid}_modifier_{mid}"] = f"{group_name}: gain {name} for [?psf_modifier_days|0] days." + impact
                        out[lang][f"psf_effect_remove_{gid}_modifier_{mid}"] = f"{group_name}: remove {name}; previous daily changes remain."
                    else:
                        timing = "直到撤销" if duration == -1 else f"持续{duration}天"
                        out[lang][f"psf_effect_add_{gid}_modifier_{mid}"] = f"{group_name}：获得{name}（{timing}）。" + impact
                        out[lang][f"psf_effect_add_timed_{gid}_modifier_{mid}"] = f"{group_name}：获得{name}，持续[?psf_modifier_days|0]天。" + impact
                        out[lang][f"psf_effect_remove_{gid}_modifier_{mid}"] = f"{group_name}：移除{name}，已累积的每日变化保留。"
            for axis in manifest["axes"]:
                aid = axis["id"]
                out["english"][f"psf_effect_add_position_{gid}_{aid}"] = g["short_name"]["english"] + ": " + axis["name"]["english"] + " changes by [?psf_amount|1]."
                out["simp_chinese"][f"psf_effect_add_position_{gid}_{aid}"] = g["short_name"]["simp_chinese"] + "：" + axis["name"]["simp_chinese"] + "立场变动[?psf_amount|1]。"
    return out


def registry(manifest: dict) -> dict:
    groups = [g for p in profiles(manifest) for g in p["groups"]]
    return {
        "formula": "clamp((base + sum(add)) * max(0, 1 + sum(factor)), attribute_bounds)",
        "daily_effect": "psf_daily_modifiers",
        "sources": {m["id"]: {"numeric_id": m["_index"], "duration_days": m["duration_days"],
                    "groups": m.get("groups", [g["id"] for g in groups]),
                    "attributes": m.get("attributes", {}), "positions": m.get("positions", {})}
                    for m in manifest.get("modifiers", [])},
        "native": {g["id"]: {field: {kind: native_key(g["id"], field, kind) for kind in KINDS}
                              for field in fields(manifest)} for g in groups},
        "effective_variables": {g["id"]: {field: modified_var(g["id"], field) for field in fields(manifest)} for g in groups},
    }
