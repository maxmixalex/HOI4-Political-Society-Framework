"""Native identity artwork and author-supplied sprite overrides.

Each political organization and ideology archetype has a large GUI sprite and
a small texticon. Defaults refer to artwork already shipped with HOI4; no game
texture is copied into the generated mod and no geometric substitute is drawn.
"""
from __future__ import annotations

import math
from pathlib import Path

from .script import quoted


# Verified against the supplied native countrypoliticsview.gfx/texticons.gfx.
IDEOLOGY_LARGE = {engine: f"gfx/interface/ideologies/{engine}_group.dds"
                  for engine in ("democratic", "communism", "fascism", "neutrality")}
IDEOLOGY_SMALL = {
    "democratic": "gfx/texticons/stability_texticon.dds",
    "communism": "gfx/texticons/manpower_texticon.dds",
    "fascism": "gfx/texticons/army_experience_20x20.dds",
    "neutrality": "gfx/texticons/pol_power_20x20.dds",
}
# These are neutral type defaults, not claims to reproduce an organization's
# historical emblem. Authors can supply independent small and large sprites.
CATEGORY_TEXTURES = {
    "union": ("gfx/interface/ideas/generic_manpower_bonus.dds",
              "gfx/texticons/manpower_texticon.dds"),
    "business": ("gfx/interface/ideas/idea_generic_industrial_concern_1.dds",
                 "gfx/texticons/industry.dds"),
    "military": ("gfx/interface/ideas/idea_generic_army_war_college.dds",
                 "gfx/texticons/army_experience_20x20.dds"),
    "religious": ("gfx/interface/ideas/idea_generic_constitutional_guarantee.dds",
                  "gfx/texticons/pol_power_20x20.dds"),
    "civic": ("gfx/interface/ideas/generic_democratic_drift_bonus.dds",
              "gfx/texticons/pol_power_20x20.dds"),
}
CATEGORY_ALIASES = {
    "trade_union": "union", "industrial_association": "business",
    "corporation": "business", "industrial": "business",
    "employers_association": "business", "military_clique": "military",
    "military_organization": "military", "church": "religious",
    "religious_body": "religious", "professional": "civic", "movement": "civic",
}


def sprite(item: dict, kind: str = "group", size: str = "large") -> str:
    if kind not in {"group", "ideology"} or size not in {"small", "large"}:
        raise ValueError("Identity sprites require group/ideology and small/large")
    return item.get(size + "_icon", f"GFX_psf_{kind}_{item['id']}_{size}")


def texticon(item: dict, kind: str = "group") -> str:
    return "£" + sprite(item, kind, "small").removeprefix("GFX_") + "£"


def closest_ideology(manifest: dict, group: dict) -> dict:
    ideologies = manifest.get("ideologies", [])
    if not ideologies:
        return {"id": "unknown", "engine_ideology": "neutrality"}
    def distance(ideology: dict) -> float:
        return math.fsum(abs(group.get("positions", {}).get(axis["id"], 0)
                             - ideology.get("positions", {}).get(axis["id"], 0))
                         * axis.get("weight", 1) for axis in manifest.get("axes", []))
    return min(ideologies, key=distance)


def _textures(manifest: dict, item: dict, kind: str) -> tuple[str, str]:
    ideology = item if kind == "ideology" else closest_ideology(manifest, item)
    engine = ideology.get("engine_ideology", "neutrality")
    if kind == "group":
        category = item.get("icon", item.get("kind", "party"))
        category = CATEGORY_ALIASES.get(category, category)
        if category in CATEGORY_TEXTURES:
            return CATEGORY_TEXTURES[category]
    large = IDEOLOGY_LARGE.get(engine, "gfx/interface/ideologies/unknown.dds")
    if "anarch" in ideology["id"]:
        large = "gfx/interface/ideologies/anarchism.dds"
    return large, IDEOLOGY_SMALL.get(engine, "gfx/texticons/pol_power_20x20.dds")


def generate_icons(manifest: dict, output: Path) -> dict:
    """Write native texture aliases; custom GFX references remain author-owned."""
    definitions = ["spriteTypes = {"]
    report = {"groups": {}, "ideologies": {}, "native_textures": [], "custom_sprites": []}
    native, custom = set(), set()
    groups = [group for profile in manifest.get("profiles", []) + manifest.get("fallback_profiles", [])
              for group in profile.get("groups", [])]
    for kind, items in (("group", groups), ("ideology", manifest.get("ideologies", []))):
        for item in items:
            textures = _textures(manifest, item, kind)
            values = {size: sprite(item, kind, size) for size in ("large", "small")}
            values["texticon"] = texticon(item, kind)
            report["groups" if kind == "group" else "ideologies"][item["id"]] = values
            for size, texture in zip(("large", "small"), textures):
                if size + "_icon" in item:
                    custom.add(values[size])
                    continue
                native.add(texture)
                definitions.append(f"spriteType = {{ name = {quoted(values[size])} "
                                   f"texturefile = {quoted(texture)} noOfFrames = 1 legacy_lazy_load = no }}")
    definitions.append("}")
    target = output / "interface/psf_identity_icons.gfx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(definitions) + "\n", encoding="utf-8")
    report["native_textures"], report["custom_sprites"] = sorted(native), sorted(custom)
    return report
