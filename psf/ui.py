"""Generate native HOI4 political society views and conservative stock GUI patches.

The engine still owns the stock widgets.  They are retained, in their original
parents, with the obsolete politics-only widgets positioned off-screen.  This
avoids the missing-child crashes caused by replacing an engine window with a
minimal scripted-GUI stub.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
from dataclasses import dataclass, field
from typing import Any

from . import charts, frontend, icons


ASSETS = Path(__file__).resolve().parent / "assets" / "native_gui"
LANGUAGES = ("english", "simp_chinese")


@dataclass
class Node:
    kind: str
    start: int
    opening: int
    end: int = 0
    name: str = ""
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    properties: dict[str, tuple[int, int, str]] = field(default_factory=dict)

    @property
    def ancestry(self) -> tuple[str, ...]:
        values: list[str] = []
        node = self.parent
        while node is not None:
            if node.name:
                values.append(node.name)
            node = node.parent
        return tuple(reversed(values))


TOKEN = re.compile(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')


def gui_nodes(text: str) -> list[Node]:
    """Find actual GUI nodes, ignoring comments, strings and nested properties."""
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith("#")]
    nodes: list[Node] = []
    stack: list[Node] = []
    i = 0
    while i < len(tokens):
        if tokens[i].group() == "}":
            if not stack:
                raise ValueError("Unbalanced GUI closing brace")
            stack.pop().end = tokens[i].end()
            i += 1
            continue
        if i + 2 < len(tokens) and tokens[i + 1].group() == "=":
            key, value = tokens[i].group(), tokens[i + 2].group()
            if value == "{":
                node = Node(key, tokens[i].start(), tokens[i + 2].start(),
                            parent=stack[-1] if stack else None)
                if stack:
                    stack[-1].children.append(node)
                nodes.append(node)
                stack.append(node)
                i += 3
                continue
            if stack:
                stack[-1].properties[key.lower()] = (
                    tokens[i].start(), tokens[i + 2].end(), value)
                if key.lower() == "name":
                    stack[-1].name = value.strip('"')
            i += 3
            continue
        i += 1
    if stack:
        raise ValueError("Unbalanced GUI opening brace")
    return nodes


def _move(node: Node, changes: list[tuple[int, int, str]], x: int, y: int) -> None:
    position = next((n for n in node.children if n.kind.lower() == "position"), None)
    value = f"position = {{ x = {x} y = {y} }} # PSF: preserve engine widget identity"
    if position:
        changes.append((position.start, position.end, value))
    else:
        changes.append((node.opening + 1, node.opening + 1, "\n\t\t" + value + "\n"))


def _container(name: str, x: int, y: int, width: int, height: int,
               body: str = "", *, scroll: bool = False, clip: bool = False,
               background: bool | str = False) -> str:
    extra = ('\nverticalScrollbar = "right_vertical_slider"\nscroll_wheel_factor = 46\nsmooth_scrolling = yes'
             '\nmargin = { top = 0 bottom = 8 left = 0 right = 14 }') if scroll else ""
    # Native scrolling containers require a background, even if transparent.
    # KR intro_screen.gui and TNO doctrines_view.gui document this explicitly.
    if scroll and not background:
        background = "GFX_tiled_window_transparent"
    bg_sprite = "GFX_tiled_window_1b_border" if background is True else background
    bg = f'\nbackground = {{ name = "Background" quadTextureSprite = "{bg_sprite}" }}' if bg_sprite else ""
    return (f'containerWindowType = {{\nname = "{name}"\n'
            f'position = {{ x = {x} y = {y} }}\nsize = {{ width = {width} height = {height} }}\n'
            f'clipping = {"yes" if scroll or clip else "no"}{extra}{bg}\n{body}\n}}\n')


def _text(name: str, key: str, x: int, y: int, width: int, height: int = 22,
          *, font: str = "hoi_16mbs", tip: str | None = None,
          transparent: bool = True, scroll: bool = False) -> str:
    tooltip = f'\npdx_tooltip = "{tip}"' if tip else ""
    scrollbar = ' scrollbartype = "standardtext_slider"' if scroll else ""
    return (f'instantTextboxType = {{ name = "{name}" position = {{ x = {x} y = {y} }} '
            f'font = "{font}" text = "{key}" maxWidth = {width} maxHeight = {height} '
            f'fixedsize = yes multiline = {"yes" if height > 24 else "no"} '
            f'alwaystransparent = {"yes" if transparent else "no"}{tooltip}{scrollbar} }}\n')


def _icon(name: str, sprite: str, x: int, y: int, *, tip: str | None = None,
          scale: float | None = None) -> str:
    extra = f' pdx_tooltip = "{tip}"' if tip else ""
    extra += f" scale = {scale:g}" if scale is not None else ""
    return (f'iconType = {{ name = "{name}" spriteType = "{sprite}" '
            f'position = {{ x = {x} y = {y} }} alwaystransparent = {"no" if tip else "yes"}{extra} }}\n')


def _button(name: str, label: str, x: int, y: int, *, tip: str | None = None,
            sprite: str = "GFX_button_123x34", scale: float | None = None,
            size: tuple[int, int] | None = None) -> str:
    extra = f' pdx_tooltip = "{tip}"' if tip else ""
    extra += f" scale = {scale:g}" if scale is not None else ""
    extra += f" size = {{ x = {size[0]} y = {size[1]} }}" if size else ""
    return (f'buttonType = {{ name = "{name}" position = {{ x = {x} y = {y} }} '
            f'quadTextureSprite = "{sprite}" buttonText = "{label}" buttonFont = "hoi_16mbs" '
            f'clicksound = click_default{extra} }}\n')


def patch_native(source: Path, output: Path, *, frontend_adapter: bool = True) -> dict[str, Any]:
    """Patch exact stock nodes; fail loudly if an updated game changes the tree."""
    patches: dict[str, Any] = {}
    for filename in ("countrypoliticsview.gui", "countrydiplomacyview.gui", "frontendgamesetupview.gui"):
        data = (source / filename).read_text(encoding="utf-8-sig")
        nodes = gui_nodes(data)
        changes: list[tuple[int, int, str]] = []
        moved: list[str] = []

        def pick(name: str, ancestor: str | None = None) -> Node:
            found = [n for n in nodes if n.name == name and (ancestor is None or ancestor in n.ancestry)]
            if len(found) != 1:
                raise ValueError(f"{filename}: expected one {ancestor or ''}/{name}, found {len(found)}")
            return found[0]

        def hide(name: str, ancestor: str | None = None) -> None:
            node = pick(name, ancestor)
            old_position = next((n for n in node.children if n.kind.lower() == "position"), None)
            old_y = old_position.properties.get("y", (0, 0, "0"))[2] if old_position else "0"
            # Preserve vertical extents: diplomacy has a native vertical scrollbar.
            _move(node, changes, -12000, old_y)
            old_hide = node.properties.get("hide")
            if old_hide:
                changes.append((old_hide[0], old_hide[1], "hide = yes"))
            else:
                changes.append((node.opening + 1, node.opening + 1, "\nhide = yes # PSF obsolete party/ideology widget\n"))
            moved.append("/".join(node.ancestry + (node.name,)))

        def unclipped(parent: Node) -> None:
            existing = parent.properties.get("clipping")
            if existing:
                changes.append((existing[0], existing[1], "clipping = no"))
            else:
                changes.append((parent.opening + 1, parent.opening + 1, "\nclipping = no # PSF sidebar extends beyond the native view width.\n"))

        if filename == "countrypoliticsview.gui":
            for name in ("chart_explanation", "political_pie_chart", "pol_faction_icon"):
                hide(name, "countrypoliticsview")
            for name in ("ideology", "elections"):
                hide(name, "ruling_party_info")
            root = pick("countrypoliticsview")
            unclipped(root)
        elif filename == "countrydiplomacyview.gui":
            for name in ("political_pie_chart", "ruling_party_info"):
                hide(name, "diplomacy_tab_top")
            hide("ideology_icon", "country_info")
            unclipped(pick("countrydiplomacyview"))
        elif frontend_adapter:
            frontend.patch_native(pick, hide, _move, changes)
        for start, end, replacement in sorted(changes, reverse=True):
            data = data[:start] + replacement + data[end:]
        # Assert every engine-owned name and original ancestry is retained.
        original_identity = [(n.kind.lower(), n.ancestry, n.name) for n in nodes if n.name]
        patched_identity = {(n.kind.lower(), n.ancestry, n.name) for n in gui_nodes(data) if n.name}
        if any(identity not in patched_identity for identity in original_identity):
            raise AssertionError(f"Native widget identity changed in {filename}")
        path = output / "interface" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        # The GUI reader treats a UTF-8 BOM as part of guiTypes.  Unlike YML
        # localization, interface files MUST NOT receive the BOM prefix.
        path.write_text(data, encoding="utf-8")
        patches[filename] = {"source_sha256": hashlib.sha256((source / filename).read_bytes()).hexdigest(),
                             "preserved_named_widgets": len(original_identity), "hidden_nodes": moved}
    return patches


def _tga(path: Path, width: int, height: int, pixel: Any) -> None:
    """Write lossless 32-bit original UI artwork without an imaging dependency."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x28)
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixel(x, y)
            pixels.extend((b, g, r, a))
    path.write_bytes(header + pixels)


def _artwork(output: Path, groups: list[dict[str, Any]]) -> str:
    sprites: list[str] = []

    def sprite(name: str, filename: str, width: int, height: int, pixel: Any, button: bool = False) -> None:
        path = f"gfx/interface/psf/{filename}.tga"
        _tga(output / path, width, height, pixel)
        effect = ' effectFile = "gfx/FX/buttonstate.lua"' if button else ""
        sprites.append(f'spriteType = {{ name = "{name}" texturefile = "{path}" noOfFrames = 1{effect} }}')

    # Rows use the original game's cornered tile/button-state shader, rather
    # than imitating native list chrome with a flat generated rectangle.
    sprite("GFX_psf_axis_track", "axis_track", 202, 6,
           lambda x, y: (166, 157, 120, 255) if y in (2, 3) else ((210, 199, 152, 255) if x in (0, 100, 200) else (0, 0, 0, 0)))
    sprites.extend(charts.artwork(output, groups))
    return "spriteTypes = {\n" + "\n".join(sprites) + "\n}\n"


def _defined(name: str, choices: list[tuple[str, str]], fallback: str = "psf_ui_none") -> str:
    body = "".join(f"text = {{ trigger = {{ {trigger} }} localization_key = {key} }}\n" for trigger, key in choices)
    return f"defined_text = {{ name = {name}\n{body}text = {{ localization_key = {fallback} }}\n}}\n"


def _exact_comparisons(content: str) -> str:
    """Normalize before byte budgeting as well as writing; this is idempotent."""
    return re.sub(
        r"check_variable\s*=\s*\{\s*([A-Za-z0-9_.]+)\s*=\s*([A-Za-z0-9_.-]+)\s*\}",
        lambda match: f"check_variable = {{ var = {match[1]} value = {match[2]} compare = equals }}",
        content,
    )


def _flag(profile: dict[str, Any]) -> str:
    return f"has_country_flag = psf_profile_{profile['id']}"


def _value(obj: Any, language: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(language, obj.get("english", default)))
    return str(obj) if obj is not None else default


def _resolve_ui_localizations(manifest: dict[str, Any], loc: dict[str, dict[str, str]]) -> None:
    """Resolve static PSF text aliases before the engine evaluates live text.

    The engine can expose literal $key$ aliases inside otherwise dynamic
    tooltips. These references are compile-time content; variable and scripted
    localisation expressions remain untouched for the selected-country scope.
    """
    profiles = list(manifest.get("profiles", [])) + list(manifest.get("fallback_profiles", []))
    kinds = (("axis", manifest.get("axes", [])), ("ideology", manifest.get("ideologies", [])),
             ("regime", manifest.get("regimes", [])), ("modifier", manifest.get("modifiers", [])),
             ("group", [g for p in profiles for g in p.get("groups", [])]),
             ("alliance", [a for p in profiles for a in p.get("alliances", [])]))
    for language, entries in loc.items():
        values = dict(entries)
        for kind, items in kinds:
            for item in items:
                for field, suffix in (("name", "name"), ("short_name", "short_name"), ("description", "desc"),
                                      ("left", "left"), ("right", "right")):
                    fallback = "" if field == "description" else _value(item.get("name"), language, item["id"])
                    value = _value(item.get(field), language, fallback)
                    # Generated YML uses a literal backslash-n for line breaks.
                    values[f"psf_{kind}_{item['id']}_{suffix}"] = value.replace("\n", "\\n")
        cache: dict[str, str] = {}

        def resolve(key: str, stack: tuple[str, ...] = ()) -> str:
            if key in cache:
                return cache[key]
            if key in stack:
                raise ValueError("Cyclic UI localisation reference: " + " -> ".join(stack + (key,)))
            def reference(match: re.Match[str]) -> str:
                target = match[1]
                if target not in values:
                    raise ValueError(f"Unknown UI localisation reference {target!r} in {key!r}; provide localized text in the manifest")
                return resolve(target, stack + (key,))

            value = re.sub(r"\$([A-Za-z0-9_]+)\$", reference, values[key])
            cache[key] = value
            return value

        loc[language] = {key: resolve(key) for key in entries}


def generate_ui(manifest: dict[str, Any], output: Path, vanilla_path: Path | None = None) -> dict[str, Any]:
    """Write native views, scripted GUI, original textures and bilingual UI text."""
    output = Path(output)
    icon_report = icons.generate_icons(manifest, output)
    profiles = list(manifest.get("profiles", [])) + list(manifest.get("fallback_profiles", []))
    groups = [group for profile in profiles for group in profile.get("groups", [])]
    axes = manifest.get("axes", [])
    alliances = [alliance for profile in profiles for alliance in profile.get("alliances", [])]
    group_indices = {g["id"]: g.get("_index", i + 1) for i, g in enumerate(groups)}
    alliance_indices = {a["id"]: a.get("_index", i + 1) for i, a in enumerate(alliances)}
    loc: dict[str, dict[str, str]] = {lang: {} for lang in LANGUAGES}

    def add_loc(key: str, english: str, chinese: str | None = None) -> None:
        loc["english"][key] = english
        loc["simp_chinese"][key] = chinese if chinese is not None else english

    strings = {
        "title": ("Political society", "政治社会"),
        "title_short": ("PSF", "PSF"),
        "groups": ("Organizations", "政治团体"),
        "support": ("Support", "支持率"),
        "influence": ("Influence", "影响力"),
        "spectrum": ("Spectrum", "政治光谱"),
        "ideology": ("Ideology", "意识形态"),
        "government_party_label": ("Government", "执政团体"),
        "alliances": ("Alliances", "政治联盟"),
        "none": ("None", "无"),
        "empty": ("", ""),
        "close": ("Close", "关闭"),
        "back": ("Organizations", "返回团体"),
        "legal": ("§GLegal§!", "§G合法活动§!"),
        "underground": ("§YUnderground§!", "§Y地下活动§!"),
        "underground_prohibited": ("§YUnderground; legally prohibited§!", "§Y地下活动（依法查禁）§!"),
        "banned": ("§RBanned§!", "§R已被查禁§!"),
        "inactive": ("Inactive", "尚未活动"),
        "government": ("§GGovernment§!", "§G执政§!"),
        "opposition": ("Opposition", "反对派"),
        "caretaker": ("Caretaker government", "看守政府"),
        "electoral": ("§YElectoral pact§!", "§Y选举联盟§!"),
        "dissolved": ("§RDissolved§!", "§R已解散§!"),
        "ban": ("Ban (50 PP)", "查禁（50 政治点）"),
        "legalize": ("Legalize (25 PP)", "解禁（25 政治点）"),
        "activate": ("Activate (25 PP)", "开始活动（25 政治点）"),
        "ban_tip": ("Ban this organization for 50 political power. It loses influence and may continue underground. A governing organization cannot be banned. Available only in your own country.", "花费 50 政治点查禁该团体，降低其影响力；它仍可能转入地下活动。不能查禁执政团体。只能操作本国团体。"),
        "legalize_tip": ("Restore this organization's legal status for 25 political power, restoring legal access to institutions. Popular support remains independently recorded. Available only in your own country.", "花费 25 政治点恢复该团体的合法地位及制度资源。民众支持率仍单独记录。只能操作本国团体。"),
        "activate_tip": ("Start this organization's political activity for 25 political power. Available only in your own country.", "花费 25 政治点，使该团体开始政治活动。只能操作本国团体。"),
        "support_tip": ("Support measures popular backing for an organization. Nonparty organizations can overlap in their supporters; their values are not extra slices of an election vote.", "支持率表示民众对团体的支持。非政党团体的支持者可能互相重叠，其数值不是额外的选票份额。"),
        "support_chart_tip": ("§YPopular support§!\\n[PSFUIPieSupport]\\n\\nActive electoral organizations, normalized to 100%. Civil organizations' overlapping approval is listed separately in their details.", "§Y民众支持率§!\\n[PSFUIPieSupport]\\n\\n活动中的参选团体按支持权重归一化为 100%。非参选社会团体的重叠支持单独列于详情。"),
        "influence_chart_tip": ("§YPolitical influence§!\\n[PSFUIPieInfluence]\\n\\nEach organization's effective influence after modifiers and legal-status restrictions, normalized to 100%.", "§Y政治影响力§!\\n[PSFUIPieInfluence]\\n\\n各团体施加修正与活动状态限制后的有效影响力，归一化为 100%。"),
        "no_support": ("No active electoral support", "暂无活动中的参选团体支持"),
        "no_influence": ("No effective political influence", "暂无有效政治影响力"),
        "influence_tip": ("Effective influence measures current access to political power and institutions. Bans and underground status suppress institutional influence. A small elite can wield high influence with little popular support.", "有效影响力表示团体当前掌握政治力量和制度资源的程度。查禁和地下活动会压制制度影响力。寡头团体即使民众支持率不高，也可能具有很高的影响力。"),
        "satisfaction_tip": ("Satisfaction measures this organization's approval of the current government. Low satisfaction can weaken an alliance and encourage withdrawal.", "满意度表示该团体对当前政府的认可程度。低满意度会削弱联盟，并可能促使团体退出。"),
        "legitimacy_tip": ("§YLegitimacy§!: [?psf_legitimacy|1]/100\\nInstitutional mismatch: [?psf_alignment_gap|1]\\nGovernment support: §Y[?psf_government_support|1]%§!\\nGovernment influence: §Y[?psf_government_influence|1]%§!\\n\\nThe government has a political program; the actual institutions remain a separate property. A mismatch reduces legitimacy, while political actions can compensate.", "§Y合法性§!：[?psf_legitimacy|1]/100\\n制度偏离：[?psf_alignment_gap|1]\\n政府支持：§Y[?psf_government_support|1]%§!\\n政府影响力：§Y[?psf_government_influence|1]%§!\\n\\n执政团体的政治主张与国家的实际制度分别记录。两者偏离会降低合法性，而政治行动可以弥补这种损失。"),
        "regime_line": ("[PSFUIRegime]", "[PSFUIRegime]"),
        "regime_tip": ("§Y[PSFUIRegime]§!\\n[PSFUIRegimeDescription]\\n\\n$psf_ui_legitimacy_tip$", "§Y[PSFUIRegime]§!\\n[PSFUIRegimeDescription]\\n\\n$psf_ui_legitimacy_tip$"),
        "government_tip": ("§Y[PSFUIGovernmentParty]§!\\nCabinet: [PSFUIGovernment]\\nPolitical tendency: [PSFUIGovIdeology]\\nGovernment satisfaction: §Y[?psf_government_satisfaction|1]§!\\nMonthly legitimacy change: §Y[?psf_legitimacy_change|2]§!\\n\\nClick to inspect political organizations.", "§Y[PSFUIGovernmentParty]§!\\n政府：[PSFUIGovernment]\\n政治倾向：[PSFUIGovIdeology]\\n执政团体满意度：§Y[?psf_government_satisfaction|1]§!\\n每月合法性变化：§Y[?psf_legitimacy_change|2]§!\\n\\n点击查看政治团体。"),
        "government_ideology_tip": ("§Y[PSFUIGovIdeology]§!\\nGovernment: [PSFUIGovernmentParty]\\n\\nThe governing program is classified from the legal government's current issue positions. The country's actual institutions are shown separately. Click to inspect the spectrum.", "§Y[PSFUIGovIdeology]§!\\n执政团体：[PSFUIGovernmentParty]\\n\\n政治倾向根据合法执政团体的实时议题立场判定，与国家实际制度分开记录。点击查看政治光谱。"),
        "government_line": ("Government: [PSFUIGovernment]", "执政：[PSFUIGovernment]"),
        "government_party_line": ("[PSFUIGovernmentParty]", "[PSFUIGovernmentParty]"),
        "summary_metrics": ("Support [?psf_government_support|0]   Influence [?psf_government_influence|0]", "支持 [?psf_government_support|0]   影响力 [?psf_government_influence|0]"),
        "summary_legitimacy": ("Legitimacy [?psf_legitimacy|0]   Groups [?psf_group_count|0]", "合法性 [?psf_legitimacy|0]   团体 [?psf_group_count|0]"),
        "side_title": ("[This.GetName]", "[This.GetName]"),
        "list_help": ("Support / influence / satisfaction", "支持率 / 影响力 / 满意度"),
        "axes_help": ("Each marker is an organization. Hover for its position and click for details.", "图标代表政治团体；悬停查看立场，点击查看详情。"),
        "axis_zero": ("0", "0"),
    }
    for key, values in strings.items():
        add_loc(f"psf_ui_{key}", *values)

    definitions: list[str] = []
    definitions.append(_defined("PSFUIRegime", [(f"check_variable = {{ psf_regime = {r.get('_index', i+1)} }}", f"psf_regime_{r['id']}_name") for i, r in enumerate(manifest.get("regimes", []))]))
    definitions.append(_defined("PSFUIRegimeDescription", [(f"check_variable = {{ psf_regime = {r.get('_index', i+1)} }}", f"psf_regime_{r['id']}_desc") for i, r in enumerate(manifest.get("regimes", []))]))
    definitions.append(_defined("PSFUIGovIdeology", [(f"check_variable = {{ psf_caretaker = 0 }} check_variable = {{ psf_government_ideology = {ideology.get('_index', i+1)} }}", f"psf_ideology_{ideology['id']}_name") for i, ideology in enumerate(manifest.get("ideologies", []))]))
    definitions.append(_defined("PSFUIGovernment",
        [(f"check_variable = {{ psf_governing_group = {group_indices[g['id']]} }}", f"psf_group_{g['id']}_short_name") for g in groups]
        + [(f"check_variable = {{ psf_governing_alliance = {alliance_indices[a['id']]} }}", f"psf_alliance_{a['id']}_name") for a in alliances],
        "psf_ui_caretaker"))
    add_loc("psf_ui_unknown_ideology_sprite", "GFX_ideology_unknown")
    party_conditions = [(f"check_variable = {{ psf_caretaker = 0 }} check_variable = {{ psf_government_leader_group = {group_indices[g['id']]} }} check_variable = {{ psf_g_{g['id']}_status = 1 }} check_variable = {{ psf_g_{g['id']}_governing = 1 }}", g) for g in groups]
    definitions.append(_defined("PSFUIGovernmentParty", [(condition, f"psf_group_{g['id']}_short_name") for condition, g in party_conditions], "psf_ui_caretaker"))
    for g in groups:
        add_loc(f"psf_ui_government_party_sprite_{g['id']}", icons.sprite(g, "group", "large"))
    definitions.append(_defined("PSFUIGovernmentPartyIcon", [(condition, f"psf_ui_government_party_sprite_{g['id']}") for condition, g in party_conditions], "psf_ui_unknown_ideology_sprite"))
    definitions.append(_defined("PSFUIGovIdeologyIcon", [(f"check_variable = {{ psf_caretaker = 0 }} check_variable = {{ psf_government_ideology = {ideology.get('_index', i+1)} }}", f"psf_ui_government_ideology_sprite_{ideology['id']}") for i, ideology in enumerate(manifest.get("ideologies", []))], "psf_ui_unknown_ideology_sprite"))
    for ideology in manifest.get("ideologies", []):
        add_loc(f"psf_ui_ideology_sprite_{ideology['id']}", icons.sprite(ideology, "ideology", "small"))
        add_loc(f"psf_ui_government_ideology_sprite_{ideology['id']}", icons.sprite(ideology, "ideology", "large"))
    for group in groups:
        gid = group["id"]
        definitions.append(_defined(f"PSFUIStatus_{gid}", [(f"check_variable = {{ psf_g_{gid}_status = 2 }} check_variable = {{ psf_g_{gid}_prohibited = 1 }}", "psf_ui_underground_prohibited")] + [(f"check_variable = {{ psf_g_{gid}_status = {n} }}", f"psf_ui_{label}") for n, label in enumerate(("inactive", "legal", "underground", "banned"))]))
        definitions.append(_defined(f"PSFUIIdeology_{gid}", [(f"check_variable = {{ psf_g_{gid}_ideology = {ideology.get('_index', i+1)} }}", f"psf_ideology_{ideology['id']}_name") for i, ideology in enumerate(manifest.get("ideologies", []))]))
        add_loc(f"psf_ui_row_{gid}",
                f"[?psf_g_{gid}_modified_support|0] / [?psf_g_{gid}_effective_influence|0] / [?psf_g_{gid}_modified_satisfaction|0]")
        definitions.append(_defined(f"PSFUIRowStatus_{gid}", [(f"check_variable = {{ psf_g_{gid}_status = {n} }}", f"psf_ui_{label}") for n, label in enumerate(("inactive", "legal", "underground", "banned"))]))
        add_loc(f"psf_ui_row_status_{gid}", f"[PSFUIRowStatus_{gid}]")
        add_loc(f"psf_ui_detail_metrics_{gid}",
                f"Support: §Y[?psf_g_{gid}_modified_support|1]§!\\nInfluence: §Y[?psf_g_{gid}_effective_influence|1]§!\\nSatisfaction: §Y[?psf_g_{gid}_modified_satisfaction|1]§!",
                f"支持率：§Y[?psf_g_{gid}_modified_support|1]§!\\n影响力：§Y[?psf_g_{gid}_effective_influence|1]§!\\n满意度：§Y[?psf_g_{gid}_modified_satisfaction|1]§!")
        add_loc(f"psf_ui_detail_status_{gid}", f"[PSFUIStatus_{gid}]")
        add_loc(f"psf_ui_detail_ideology_{gid}", f"[PSFUIIdeology_{gid}]")
        definitions.append(_defined(f"PSFUIIdeologyIcon_{gid}",
            [(f"check_variable = {{ psf_g_{gid}_ideology = {ideology.get('_index', i+1)} }}", f"psf_ui_ideology_sprite_{ideology['id']}") for i, ideology in enumerate(manifest.get("ideologies", []))],
            f"psf_ui_ideology_sprite_{manifest['ideologies'][0]['id']}"))
        kinds = {"party": ("Political party", "政党"), "trade_union": ("Trade union", "工会"), "union": ("Trade union", "工会"), "business": ("Business association", "工商团体"), "industrial_association": ("Industrial association", "产业联合会"), "corporation": ("Corporation", "法团"), "military": ("Military organization", "军人团体"), "military_clique": ("Military organization", "军人团体"), "religious": ("Religious organization", "宗教团体"), "church": ("Religious organization", "宗教团体"), "movement": ("Political movement", "政治运动"), "professional": ("Professional association", "职业团体"), "employers_association": ("Employers' association", "雇主协会"), "civic": ("Civic organization", "公民团体"), "faction": ("Political faction", "政治派系")}
        kind_en, kind_zh = kinds.get(group.get("kind", "party"), (group.get("kind", "Organization").replace("_", " "), "政治团体"))
        add_loc(f"psf_ui_kind_{gid}", kind_en, kind_zh)
        add_loc(f"psf_ui_group_tooltip_{gid}",
                f"§Y$psf_group_{gid}_name$§!\\n$psf_ui_kind_{gid}$ — [PSFUIStatus_{gid}]\\n[PSFUIIdeology_{gid}]\\n\\n$psf_ui_detail_metrics_{gid}$\\nBase support / influence / satisfaction: [?psf_g_{gid}_support|1] / [?psf_g_{gid}_influence|1] / [?psf_g_{gid}_satisfaction|1]\\nInfluence after modifiers: [?psf_g_{gid}_modified_influence|1]\\n\\nActive modifier sources ([?psf_g_{gid}_modifier_count|0]):\\n[PSFUIModifiers_{gid}]\\n\\n$psf_group_{gid}_desc$",
                f"§Y$psf_group_{gid}_name$§!\\n$psf_ui_kind_{gid}$　[PSFUIStatus_{gid}]\\n[PSFUIIdeology_{gid}]\\n\\n$psf_ui_detail_metrics_{gid}$\\n基础支持率 / 影响力 / 满意度：[?psf_g_{gid}_support|1] / [?psf_g_{gid}_influence|1] / [?psf_g_{gid}_satisfaction|1]\\n施加修正后的影响力：[?psf_g_{gid}_modified_influence|1]\\n\\n活动修正来源（[?psf_g_{gid}_modifier_count|0]）：\\n[PSFUIModifiers_{gid}]\\n\\n$psf_group_{gid}_desc$")
        source_names = []
        for modifier in manifest.get("modifiers", []):
            if "groups" in modifier and gid not in modifier["groups"]:
                continue
            mid = modifier["id"]
            active = f"psf_m_{gid}_{mid}_active"
            days = f"psf_m_{gid}_{mid}_days"
            stem = f"psf_ui_source_{gid}_{mid}"
            name = f"PSFUISource_{gid}_{mid}"
            add_loc(stem + "_timed", f"$psf_modifier_{mid}_name$: [?{days}|0] days remaining\\n",
                    f"$psf_modifier_{mid}_name$：剩余 [?{days}|0] 天\\n")
            add_loc(stem + "_permanent", f"$psf_modifier_{mid}_name$: until removed\\n",
                    f"$psf_modifier_{mid}_name$：持续至被移除\\n")
            definitions.append(_defined(name, [
                (f"check_variable = {{ {active} = 1 }} check_variable = {{ {days} > 0 }}", stem + "_timed"),
                (f"check_variable = {{ {active} = 1 }}", stem + "_permanent")
            ], "psf_ui_empty"))
            source_names.append(f"[{name}]")
        source_key = f"psf_ui_modifier_sources_{gid}"
        add_loc(source_key, "".join(source_names))
        definitions.append(_defined(f"PSFUIModifiers_{gid}", [
            (f"check_variable = {{ psf_g_{gid}_modifier_count > 0 }}", source_key)
        ]))
        position_en, position_zh = [], []
        for axis in axes:
            aid = axis["id"]
            position_en.append(f"$psf_axis_{aid}_name$: [?psf_g_{gid}_modified_position_{aid}|0]")
            position_zh.append(f"$psf_axis_{aid}_name$：[?psf_g_{gid}_modified_position_{aid}|0]")
            add_loc(f"psf_ui_marker_{gid}_{aid}",
                    f"§Y$psf_group_{gid}_name$§!\\n$psf_axis_{aid}_name$: [?psf_g_{gid}_modified_position_{aid}|0]\\nBase position: [?psf_g_{gid}_position_{aid}|0]\\n$psf_axis_{aid}_left$ (-100) — $psf_axis_{aid}_right$ (+100)\\n\\n$psf_axis_{aid}_desc$\\n\\nClick to inspect this organization.",
                    f"§Y$psf_group_{gid}_name$§!\\n$psf_axis_{aid}_name$：[?psf_g_{gid}_modified_position_{aid}|0]\\n基础立场：[?psf_g_{gid}_position_{aid}|0]\\n$psf_axis_{aid}_left$（-100）— $psf_axis_{aid}_right$（+100）\\n\\n$psf_axis_{aid}_desc$\\n\\n点击查看该团体。")
        add_loc(f"psf_ui_positions_{gid}", "\\n".join(position_en), "\\n".join(position_zh))

    for metric in ("support", "influence"):
        choices = []
        for profile in profiles:
            lines = []
            for group in profile.get("groups", []):
                gid = group["id"]
                if metric == "support" and not group.get("electoral", group.get("kind", "party") == "party"):
                    continue
                key = f"psf_ui_pie_{metric}_{gid}"
                name = f"PSFUIPie_{metric}_{gid}"
                add_loc(key, f"£psf_color_{gid}£ §Y$psf_group_{gid}_short_name$§!: [?psf_g_{gid}_{metric}_share|1]%\\n")
                definitions.append(_defined(name, [
                    (f"check_variable = {{ psf_g_{gid}_{metric}_share > 0 }}", key)
                ], "psf_ui_empty"))
                lines.append(f"[{name}]")
            key = f"psf_ui_pie_{metric}_profile_{profile['id']}"
            add_loc(key, "".join(lines))
            choices.append((f"{_flag(profile)} check_variable = {{ psf_pie_{metric}_total > 0 }}", key))
        definitions.append(_defined("PSFUIPie" + metric.title(), choices, "psf_ui_no_" + metric))

    selection_condition = "OR = { " + " ".join(
        f"AND = {{ {_flag(profile)} check_variable = {{ ROOT.psf_ui_group = {group_indices[group['id']]} }} }}"
        for profile in profiles for group in profile.get("groups", [])
    ) + " }"
    list_visible = "OR = { check_variable = { ROOT.psf_ui_page = 0 } AND = { check_variable = { ROOT.psf_ui_page = 1 } NOT = { psf_ui_selection_is_current = yes } } }"
    side_visible = "has_country_flag = psf_initialized check_variable = { ROOT.psf_ui_open = 1 }"
    # Each page is a separately owned scripted GUI. Native container visibility
    # callbacks do not reliably recurse through arbitrary child containers.
    # Controls with effects, visibility or live properties are direct children
    # of the window that owns the corresponding scripted GUI.
    pages: list[tuple[str, str, str, list[str], list[str], list[str]]] = []
    for profile in profiles:
        pid = profile["id"]
        rows = _text("psf_list_help", "psf_ui_list_help", 10, 0, 366,
                     tip="psf_ui_support_tip", transparent=False)
        row_effects = []
        for row, group in enumerate(profile.get("groups", [])):
            gid = group["id"]
            index = group_indices[gid]
            y = 28 + row * 46
            rows += _button(f"psf_select_{gid}", "", 8, y, tip=f"psf_ui_group_tooltip_{gid}",
                            sprite="GFX_tiled_window_small_small", size=(370, 44))
            rows += _icon(f"psf_row_icon_{gid}", icons.sprite(group, "group", "small"), 16, y + 10)
            rows += _icon(f"psf_row_color_{gid}", f"GFX_psf_color_{gid}", 42, y + 28)
            rows += _text(f"psf_row_name_{gid}", f"psf_group_{gid}_short_name", 54, y + 2, 315, 20, font="hoi_18mbs")
            rows += _text(f"psf_row_values_{gid}", f"psf_ui_row_{gid}", 54, y + 23, 184, 20)
            rows += _text(f"psf_row_status_{gid}", f"psf_ui_row_status_{gid}", 242, y + 23, 128, 20)
            row_effects.append(f"psf_select_{gid}_click = {{ set_variable = {{ ROOT.psf_ui_group = {index} }} set_variable = {{ ROOT.psf_ui_page = 1 }} }}")
            detail_triggers, detail_effects = [], []
            detail_properties = [f'psf_detail_ideology_icon_{gid} = {{ image = "[PSFUIIdeologyIcon_{gid}]" }}']
            # Vanilla idea entries reserve 60×68 (frontend spirit_idea_entry).
            # A separate clipped frame also bounds author-supplied artwork.
            detail = _container(f"psf_detail_icon_frame_{gid}", 8, 4, 72, 76,
                                _icon(f"psf_large_icon_{gid}", icons.sprite(group, "group", "large"), 0, 0), clip=True)
            detail += _text(f"psf_detail_name_{gid}", f"psf_group_{gid}_name", 84, 4, 286, 56, font="hoi_18mbs",
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _icon(f"psf_detail_color_{gid}", f"GFX_psf_color_{gid}", 84, 66)
            detail += _text(f"psf_detail_kind_{gid}", f"psf_ui_kind_{gid}", 98, 61, 272)
            detail += _text(f"psf_detail_status_{gid}", f"psf_ui_detail_status_{gid}", 8, 92, 362, 22,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _icon(f"psf_detail_ideology_icon_{gid}", icons.sprite(icons.closest_ideology(manifest, group), "ideology", "small"), 8, 116)
            detail += _text(f"psf_detail_ideology_{gid}", f"psf_ui_detail_ideology_{gid}", 38, 116, 332, 22,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _text(f"psf_detail_metrics_{gid}", f"psf_ui_detail_metrics_{gid}", 8, 148, 362, 66,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _text(f"psf_detail_description_{gid}", f"psf_group_{gid}_desc", 8, 220, 362, 132,
                            scroll=True, transparent=False)
            detail += _text(f"psf_detail_positions_{gid}", f"psf_ui_positions_{gid}", 8, 360, 362, max(36, len(axes) * 22))
            action_y = 368 + max(36, len(axes) * 22)
            for action, cost, guard in (("ban", 50, f"check_variable = {{ psf_g_{gid}_status = 1 }} check_variable = {{ psf_g_{gid}_governing = 0 }}"),
                                        ("legalize", 25, f"OR = {{ check_variable = {{ psf_g_{gid}_status = 2 }} check_variable = {{ psf_g_{gid}_status = 3 }} }}"),
                                        ("activate", 25, f"check_variable = {{ psf_g_{gid}_status = 0 }}")):
                condition = f"tag = ROOT {guard} has_political_power > {cost - 1}"
                detail_triggers.append(f"psf_{action}_{gid}_click_enabled = {{ {condition} }}")
                detail_triggers.append(f"psf_{action}_{gid}_visible = {{ tag = ROOT {guard} }}")
                detail_effects.append(f"psf_{action}_{gid}_click = {{ if = {{ limit = {{ {condition} }} add_political_power = -{cost} psf_{action}_{gid} = yes }} }}")
                detail += _button(f"psf_{action}_{gid}", f"psf_ui_{action}", 8, action_y,
                                  tip=f"psf_ui_{action}_tip", sprite="GFX_button_238x38")
            pages.append((f"detail_{gid}", detail,
                          f"{_flag(profile)} check_variable = {{ ROOT.psf_ui_page = 1 }} check_variable = {{ ROOT.psf_ui_group = {index} }}",
                          detail_effects, detail_triggers, detail_properties))
        pages.append((f"groups_{pid}", rows, f"{_flag(profile)} {list_visible}", row_effects, [], []))
        alliance_rows, ay = "", 0
        for alliance in profile.get("alliances", []):
            aid = alliance["id"]
            definitions.append(_defined(f"PSFUIAllianceRole_{aid}", [(f"check_variable = {{ psf_a_{aid}_active = 0 }}", "psf_ui_dissolved")] + [(f"check_variable = {{ psf_a_{aid}_role = {n} }}", f"psf_ui_{role}") for n, role in ((1, "government"), (2, "opposition"), (3, "electoral"))]))
            add_loc(f"psf_ui_alliance_stats_{aid}", f"[PSFUIAllianceRole_{aid}]    Cohesion §Y[?psf_a_{aid}_cohesion|0]§!", f"[PSFUIAllianceRole_{aid}]    凝聚力 §Y[?psf_a_{aid}_cohesion|0]§!")
            add_loc(f"psf_ui_alliance_metrics_{aid}",
                    f"Members §Y[?psf_a_{aid}_member_count|0]§!    Influence §Y[?psf_a_{aid}_influence|0]§!",
                    f"成员 §Y[?psf_a_{aid}_member_count|0]§!    影响力 §Y[?psf_a_{aid}_influence|0]§!")
            add_loc(f"psf_ui_alliance_tooltip_{aid}",
                    f"§Y$psf_alliance_{aid}_name$§!\\n[PSFUIAllianceRole_{aid}]\\nCohesion: §Y[?psf_a_{aid}_cohesion|1]/100§!\\nMembers: §Y[?psf_a_{aid}_member_count|0]§!\\nInfluence: §Y[?psf_a_{aid}_influence|1]§!\\nSatisfaction: §Y[?psf_a_{aid}_satisfaction|1]/100§!\\n\\n$psf_alliance_{aid}_desc$\\n\\n$psf_ui_alliance_members_{aid}$",
                    f"§Y$psf_alliance_{aid}_name$§!\\n[PSFUIAllianceRole_{aid}]\\n凝聚力：§Y[?psf_a_{aid}_cohesion|1]/100§!\\n成员：§Y[?psf_a_{aid}_member_count|0]§!\\n影响力：§Y[?psf_a_{aid}_influence|1]§!\\n满意度：§Y[?psf_a_{aid}_satisfaction|1]/100§!\\n\\n$psf_alliance_{aid}_desc$\\n\\n$psf_ui_alliance_members_{aid}$")
            alliance_rows += _container(f"psf_alliance_chrome_{aid}", 8, ay, 370, 126, background="GFX_tiled_window_small_small")
            alliance_rows += _text(f"psf_alliance_name_{aid}", f"psf_alliance_{aid}_name", 20, ay + 8, 342, 22,
                                   font="hoi_18mbs", tip=f"psf_ui_alliance_tooltip_{aid}", transparent=False)
            alliance_rows += _text(f"psf_alliance_stats_{aid}", f"psf_ui_alliance_stats_{aid}", 20, ay + 34, 342,
                                   tip=f"psf_ui_alliance_tooltip_{aid}", transparent=False)
            alliance_rows += _text(f"psf_alliance_metrics_{aid}", f"psf_ui_alliance_metrics_{aid}", 20, ay + 56, 342,
                                   tip=f"psf_ui_alliance_tooltip_{aid}", transparent=False)
            for group in profile.get("groups", []):
                gid = group["id"]
                definitions.append(_defined(f"PSFUIMember_{aid}_{gid}", [(f"check_variable = {{ psf_a_{aid}_g_{gid} = 1 }}", f"psf_ui_member_{gid}")], "psf_ui_empty"))
                for lang in LANGUAGES:
                    loc[lang][f"psf_ui_member_{gid}"] = f"$psf_group_{gid}_short_name$  "
            member_text = "".join(f"[PSFUIMember_{aid}_{g['id']}]" for g in profile.get("groups", []))
            add_loc(f"psf_ui_alliance_members_{aid}", member_text)
            alliance_rows += _text(f"psf_alliance_members_{aid}", f"psf_ui_alliance_members_{aid}", 20, ay + 80, 342, 40,
                                   tip=f"psf_ui_alliance_tooltip_{aid}", transparent=False)
            ay += 134
        if not alliance_rows:
            alliance_rows = _text(f"psf_no_alliances_{pid}", "psf_ui_none", 8, 0, 362)
        pages.append((f"alliances_{pid}", alliance_rows,
                      f"{_flag(profile)} check_variable = {{ ROOT.psf_ui_page = 3 }}", [], [], []))

        spectrum = _text("psf_axes_help", "psf_ui_axes_help", 8, 0, 362, 44)
        spectrum_effects, spectrum_triggers, spectrum_properties = [], [], []
        axis_height = 66 + len(profile.get("groups", [])) * 18
        for i, axis in enumerate(axes):
            aid = axis["id"]
            y = 50 + i * axis_height
            spectrum += _text(f"psf_axis_label_{aid}", f"psf_axis_{aid}_name", 8, y, 362,
                              font="hoi_18mbs", tip=f"psf_axis_{aid}_desc", transparent=False)
            spectrum += _text(f"psf_axis_left_{aid}", f"psf_axis_{aid}_left", 8, y + 24, 178)
            spectrum += _text(f"psf_axis_right_{aid}", f"psf_axis_{aid}_right", 198, y + 24, 172)
            for gi, group in enumerate(profile.get("groups", [])):
                gid = group["id"]
                name = f"psf_axis_marker_{gid}_{aid}"
                my = y + 48 + gi * 18
                spectrum += _icon(f"psf_axis_track_{gid}_{aid}", "GFX_psf_axis_track", 92, my + 5)
                spectrum += _text(f"psf_axis_group_{gid}_{aid}", f"psf_group_{gid}_short_name", 8, my, 76, 18,
                                  tip=f"psf_ui_marker_{gid}_{aid}", transparent=False)
                spectrum += _button(name, "", 184, my, tip=f"psf_ui_marker_{gid}_{aid}",
                                    sprite=icons.sprite(group, "group", "small"),
                                    scale=0.666667 if "small_icon" in group else 0.8)
                key = f"psf_ui_axis_value_{gid}_{aid}"
                add_loc(key, f"[?psf_g_{gid}_modified_position_{aid}|0]")
                spectrum += _text(f"psf_axis_value_{gid}_{aid}", key, 310, my, 60, 18)
                spectrum_properties.append(f"{name} = {{ x = psf_g_{gid}_ui_position_{aid} }}")
                for element in (name, f"psf_axis_track_{gid}_{aid}", f"psf_axis_group_{gid}_{aid}", f"psf_axis_value_{gid}_{aid}"):
                    spectrum_triggers.append(f"{element}_visible = {{ check_variable = {{ psf_g_{gid}_status > 0 }} }}")
                spectrum_effects.append(f"{name}_click = {{ set_variable = {{ ROOT.psf_ui_group = {group_indices[gid]} }} set_variable = {{ ROOT.psf_ui_page = 1 }} }}")
        pages.append((f"spectrum_{pid}", spectrum,
                      f"{_flag(profile)} check_variable = {{ ROOT.psf_ui_page = 2 }}",
                      spectrum_effects, spectrum_triggers, spectrum_properties))

    side_body = _container("psf_header_chrome", 0, 0, 414, 44, background="GFX_tiled_header_1")
    side_body += _text("psf_side_title", "psf_ui_side_title", 18, 7, 332, 30, font="hoi_24header")
    side_body += _button("psf_close", "", 364, 5, tip="psf_ui_close", sprite="GFX_closebutton")
    side_effects = ["psf_close_click = { set_variable = { ROOT.psf_ui_open = 0 } }"]
    side_triggers = []
    for name, label, x, page in (("psf_tab_groups", "groups", 12, 0), ("psf_tab_spectrum", "spectrum", 140, 2), ("psf_tab_alliances", "alliances", 268, 3)):
        side_body += _button(name, f"psf_ui_{label}", x, 49)
        selected = f"OR = {{ check_variable = {{ ROOT.psf_ui_page = 0 }} check_variable = {{ ROOT.psf_ui_page = 1 }} }}" if page == 0 else f"check_variable = {{ ROOT.psf_ui_page = {page} }}"
        side_body += _button(name + "_selected", f"psf_ui_{label}", x, 49, sprite="GFX_button_123x34_alt")
        side_triggers += [f"{name}_visible = {{ NOT = {{ {selected} }} }}", f"{name}_selected_visible = {{ {selected} }}"]
        side_effects.append(f"{name}_click = {{ set_variable = {{ ROOT.psf_ui_page = {page} }} }}")
        side_effects.append(f"{name}_selected_click = {{ set_variable = {{ ROOT.psf_ui_page = {page} }} }}")

    scoped_loc: dict[str, str] = {}

    def scope_localization(body: str, mode: str) -> str:
        scope = "ROOT" if mode == "political" else "THIS"
        def replace(match: re.Match[str]) -> str:
            key = match[1]
            if key not in loc["english"] or not any("[" in loc[lang][key] for lang in LANGUAGES):
                return match[0]
            scoped = f"psf_ui_{mode}_" + key.removeprefix("psf_ui_")
            for language in LANGUAGES:
                loc[language][scoped] = loc[language][key]
            scoped_loc[scoped] = scope
            return '"' + scoped + '"'
        return re.sub(r'"(psf_ui_[A-Za-z0-9_]+)"', replace, body)

    gui_by_mode: dict[str, list[str]] = {mode: [] for mode in ("political", "diplomatic")}
    scripts_by_mode: dict[str, list[str]] = {mode: [] for mode in ("political", "diplomatic")}
    for mode, context, token in (("political", "player_context", "politics_tab"),
                                 ("diplomatic", "selected_country_context", "selected_country_view_diplomacy")):
        def scripted_window(name: str, body: str, x: int, y: int, width: int, height: int,
                            visible: str, *, parent: str | None = None, effects: list[str] = (),
                            triggers: list[str] = (), properties: list[str] = (),
                            scroll: bool = False, clip: bool = False,
                            background: bool | str = False, dirty: bool = False) -> None:
            window = f"psf_{mode}_{name}"
            gui_by_mode[mode].append(_container(window, x, y, width, height, scope_localization(body, mode), scroll=scroll, clip=clip, background=background))
            data_scope = "ROOT" if mode == "political" else "THIS"
            properties = [re.sub(r"(frame|x|y) = (psf_)", rf"\1 = {data_scope}.\2", value) for value in properties]
            properties = [re.sub(r"\[(PSFUI[A-Za-z0-9_]+)\]", lambda m: f"[{data_scope}.{m[1]}]", value) for value in properties]
            attachment = f"parent_scripted_gui = {parent}" if parent else f"parent_window_token = {token}"
            script = (f"{window}_gui = {{\ncontext_type = {context}\n{attachment}\nwindow_name = {window}\n"
                      + (f"dirty = {data_scope}.psf_ui_revision\n" if dirty else "")
                      + f"visible = {{ {visible} }}\nai_enabled = {{ always = no }}\n")
            for key, values in (("effects", effects), ("triggers", triggers), ("properties", properties)):
                if values:
                    script += key + " = {\n" + "\n".join(values) + "\n}\n"
            scripts_by_mode[mode].append(script + "}\n")

        # The diplomacy-only token is rooted in country_info (Y=50), unlike
        # politics_tab. Cancel that offset for the sidebar header.
        scripted_window("society_side", side_body, 552, 0 if mode == "political" else -50,
                        414, 590, side_visible, effects=side_effects, triggers=side_triggers, background=True)
        for name, body, visible, effects, triggers, properties in pages:
            scripted_window(name, body, 8, 92, 396, 486, f"{side_visible} {visible}",
                            parent=f"psf_{mode}_society_side_gui", effects=effects, triggers=triggers,
                            properties=properties, scroll=True)

        # The native tokens supply the correct view origin (including the top
        # bar offset and animation). No ad-hoc *_instance mount is assumed.
        def open_effect(name: str, page: int) -> str:
            return f"psf_open_{name}_click = {{ if = {{ limit = {{ tag = ROOT }} psf_bootstrap = yes }} set_variable = {{ ROOT.psf_ui_open = 1 }} set_variable = {{ ROOT.psf_ui_page = {page} }} }}"

        summary, pie_properties = "", []
        # Four visual cells fit beside the existing domestic text width. The
        # large icons are also the organization/spectrum entry controls, so
        # separate text buttons do not displace the national summary.
        if mode == "political":
            summary += _text("psf_government_party_label", "psf_ui_government_party_label", 0, 0, 72, 17)
            summary += _button("psf_open_groups", "", 3, 17, sprite="GFX_ideology_unknown", scale=0.9,
                               tip="psf_ui_government_tip")
            pie_properties.append('psf_open_groups = { image = "[PSFUIGovernmentPartyIcon]" }')
        ideology_x = 74 if mode == "political" else 148
        summary += _text("psf_government_ideology_label", "psf_ui_ideology", ideology_x, 0, 72, 17)
        summary += _button("psf_open_spectrum", "", ideology_x + 3, 17,
                           sprite="GFX_ideology_unknown", scale=0.9, tip="psf_ui_government_ideology_tip")
        pie_properties.append('psf_open_spectrum = { image = "[PSFUIGovIdeologyIcon]" }')
        for metric, x in (("support", 148 if mode == "political" else 0),
                          ("influence", 222 if mode == "political" else 74)):
            summary += _text(f"psf_{mode}_{metric}_label", f"psf_ui_{metric}", x, 0, 72, 17,
                             tip=f"psf_ui_{metric}_chart_tip", transparent=False)
            for index, (left, top, _, _) in enumerate(charts.geometry()):
                name = f"psf_pie_{metric}_{index:03}"
                summary += _icon(name, f"GFX_psf_pie_sector_{index:03}", x + left, 17 + top)
                pie_properties.append(f"{name} = {{ frame = psf_pie_{metric}_frames^{index} }}")
            summary += _button(f"psf_open_{metric}", "", x, 17,
                               sprite="GFX_pol_piechart_overlay_63x63", tip=f"psf_ui_{metric}_chart_tip")
        text_x = 298 if mode == "political" else 222
        text_width = 212 if mode == "political" else 152
        summary += _text(f"psf_{mode}_regime", "psf_ui_regime_line", text_x, 0, text_width,
                         20 if mode == "political" else 38,
                         font="hoi_18mbs", tip="psf_ui_regime_tip", transparent=False)
        summary += _text(f"psf_{mode}_government", "psf_ui_government_party_line", text_x,
                         20 if mode == "political" else 42, text_width, 20 if mode == "political" else 40,
                         tip="psf_ui_government_tip", transparent=False)
        if mode == "political":
            summary += _text(f"psf_{mode}_metrics", "psf_ui_summary_metrics", text_x, 40, text_width, 20,
                             tip="psf_ui_influence_tip", transparent=False)
            summary += _text(f"psf_{mode}_legitimacy", "psf_ui_summary_legitimacy", text_x, 60, text_width, 19,
                             tip="psf_ui_legitimacy_tip", transparent=False)
        summary_effects = [open_effect(name, page) for name, page in
                           (("spectrum", 2), ("support", 0), ("influence", 0))]
        if mode == "political":
            summary_effects.append(open_effect("groups", 0))
        scripted_window("summary", summary, 18 if mode == "political" else 144,
                        302 if mode == "political" else 110, 512 if mode == "political" else 376,
                        80 if mode == "political" else 86, "has_country_flag = psf_initialized",
                        effects=summary_effects, properties=pie_properties,
                        background="GFX_tiled_window_small_small", clip=True, dirty=True)
        if mode == "diplomatic":
            # The original ideology-icon slot is clear after the stock patch.
            # It stays above the diplomacy/intelligence tabs and outside the
            # lower national-focus area; the country/faction/leader text stays.
            party_icon = _button("psf_open_groups", "", 4, 1, sprite="GFX_ideology_unknown",
                                 scale=0.9, tip="psf_ui_government_tip")
            scripted_window("government_party", party_icon, 158, 0, 72, 68,
                            "has_country_flag = psf_initialized", effects=[open_effect("groups", 0)],
                            properties=['psf_open_groups = { image = "[PSFUIGovernmentPartyIcon]" }'],
                            clip=True, dirty=True)

    def write(relative: str, content: str, bom: bool = False) -> None:
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith(".txt"):
            # check_variable defaults to >= in the engine.  UI identities need
            # explicit equality, especially with stable hashed numeric IDs.
            content = _exact_comparisons(content)
        if relative in ("interface/psf_society_political.gui", "interface/psf_society_diplomatic.gui"):
            # Keep readable node lines, but remove syntactically redundant
            # padding outside quoted strings so full country registries remain
            # below the validation discovery budget without dropping controls.
            content = re.sub(r'"(?:\\.|[^"\\])*"|[ \t]*([={}])[ \t]*',
                             lambda match: match[0] if match[1] is None else match[1], content)
        path.write_text(content, encoding="utf-8-sig" if bom else "utf-8")

    write("common/scripted_triggers/psf_ui.txt", f"psf_ui_selection_is_current = {{ {selection_condition} }}\n")
    # Split at complete window boundaries, never in the middle of a GUI.
    # Both the engine loader and CWTools must discover the whole registry.
    for mode in ("political", "diplomatic"):
        for folder, extension, root_key, entries in (
            ("interface", "gui", "guiTypes", gui_by_mode[mode]),
            ("common/scripted_guis", "txt", "scripted_gui", scripts_by_mode[mode]),
        ):
            chunks, current, byte_count = [], [], 0
            for entry in entries:
                entry = _exact_comparisons(entry) if extension == "txt" else entry
                size = len(entry.encode("utf-8"))
                if size > 850_000:
                    raise ValueError("One UI window exceeds the safe discovery budget")
                if byte_count + size > 850_000:
                    chunks.append(current)
                    current, byte_count = [], 0
                current.append(entry)
                byte_count += size
            if current:
                chunks.append(current)
            for index, chunk in enumerate(chunks):
                suffix = "" if index == 0 else f"_{index:03}"
                write(f"{folder}/psf_society_{mode}{suffix}.{extension}", root_key + " = {\n" + "\n".join(chunk) + "\n}\n")
    write("interface/psf_society.gfx", _artwork(output, groups))
    definition_chunk = ""
    definition_index = 0
    definition_bytes = 0
    for definition in definitions:
        definition = _exact_comparisons(definition)
        size = len(definition.encode("utf-8"))
        if size > 900_000:
            raise ValueError("One scripted localization definition exceeds 900000 bytes")
        if definition_bytes + size > 900_000:
            suffix = "" if definition_index == 0 else f"_{definition_index:03}"
            write(f"common/scripted_localisation/psf_ui{suffix}.txt", definition_chunk)
            definition_chunk = ""
            definition_index += 1
            definition_bytes = 0
        definition_chunk += definition
        definition_bytes += size
    suffix = "" if definition_index == 0 else f"_{definition_index:03}"
    write(f"common/scripted_localisation/psf_ui{suffix}.txt", definition_chunk)
    _resolve_ui_localizations(manifest, loc)
    # Player-context native textboxes do not supply an implicit selected
    # country. Explicit ROOT is used by KR's politics-tab widgets as well.
    for key, scope in scoped_loc.items():
        for language in LANGUAGES:
            text = loc[language][key]
            text = re.sub(r"\[\?(psf_)", lambda m: f"[?{scope}.{m[1]}", text)
            text = re.sub(r"\[(PSFUI[A-Za-z0-9_]+)\]", lambda m: f"[{scope}.{m[1]}]", text)
            text = re.sub(r"\[This\.", f"[{scope}.", text, flags=re.IGNORECASE)
            loc[language][key] = text
    for lang, keys in loc.items():
        # Literal backslash-n is intentional HOI4 localization syntax.
        header = f"l_{lang}:\n"
        chunk = header
        index = 0
        for key, value in sorted(keys.items()):
            line = f' {key}:0 "{value.replace(chr(34), chr(92)+chr(34))}"\n'
            if len((chunk + line).encode("utf-8-sig")) > 900_000:
                suffix = "" if index == 0 else f"_{index:03}"
                write(f"localisation/{lang}/psf_ui{suffix}_l_{lang}.yml", chunk, True)
                chunk = header
                index += 1
            chunk += line
        suffix = "" if index == 0 else f"_{index:03}"
        write(f"localisation/{lang}/psf_ui{suffix}_l_{lang}.yml", chunk, True)
    source = Path(vanilla_path) if vanilla_path else ASSETS
    if (source / "interface").is_dir():
        source = source / "interface"
    frontend_adapter = manifest.get("settings", {}).get("mechanics_mode", "compat") == "strict"
    patches = patch_native(source, output, frontend_adapter=frontend_adapter)
    metadata = {"native_patches": patches, "organizations": len(groups), "axes": len(axes),
                "sidebar": {"width": 414, "height": 590, "offset_from_native_left": 552,
                            "pages_per_context": len(pages), "page_visibility": "independent scripted GUI roots"},
                "attachments": {"political": "politics_tab", "diplomatic": "selected_country_view_diplomacy"},
                "charts": {"sectors": charts.SECTORS, "diameter": charts.SIZE, "neutral_frame": 1,
                           "inset": charts.INSET, "radius": charts.RADIUS,
                           "support": "Active electoral organizations, normalized modified support",
                           "influence": "All active organizations, normalized effective influence"},
                "localization_keys_per_language": len(loc["english"]), "identity_artwork": icon_report,
                "localization_scope": {"political": "ROOT", "diplomatic": "THIS"},
                "scope_policy": "Player context reads ROOT; diplomacy reads THIS; ROOT owns UI state; mutation requires tag = ROOT",
                "government_identity": "Large governing-party and ideology icons; party uses psf_government_leader_group and requires a legal governing member",
                "frontend_adapter": frontend_adapter,
                "pregame": ("Native party history binding supplies country/date political snapshots on both selection routes; historical prose remains separate"
                            if frontend_adapter else "Native country-selection layout retained because compat mode has no automatic history presentation binding")}
    write("psf_ui_manifest.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata
