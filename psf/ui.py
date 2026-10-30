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

from . import charts


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
               body: str = "", *, scroll: bool = False, background: bool | str = False) -> str:
    extra = '\nverticalScrollbar = "right_vertical_slider"\nscroll_wheel_factor = 32\nsmooth_scrolling = yes' if scroll else ""
    bg_sprite = "GFX_tiled_window_1b_border" if background is True else background
    bg = f'\nbackground = {{ name = "Background" quadTextureSprite = "{bg_sprite}" }}' if bg_sprite else ""
    return (f'containerWindowType = {{\nname = "{name}"\n'
            f'position = {{ x = {x} y = {y} }}\nsize = {{ width = {width} height = {height} }}\n'
            f'clipping = {"yes" if scroll else "no"}{extra}{bg}\n{body}\n}}\n')


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


def patch_native(source: Path, output: Path) -> dict[str, Any]:
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

        def add(parent: Node, body: str) -> None:
            changes.append((parent.end - 1, parent.end - 1, "\n# PSF extension: native siblings above remain intact.\n" + body + "\n"))

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
        else:
            hide("political_pie_chart", "gamesetup_country_details")
            hide("pol_faction_icon", "gamesetup_country_details")
            for parent_name in ("gamesetup_country_details", "gamesetup_interesting_countries_window"):
                for name in ("ideology_label", "ideology", "government_label", "government", "elections_label", "elections", "party_label", "party"):
                    hide(name, parent_name)
            root = pick("gamesetup_country_details")
            add(root, _container("psf_pregame_badge", 108, 25, 130, 76,
                _text("psf_pregame_title", "psf_ui_title_short", 0, 0, 128, 28, font="hoi_18mbs") +
                _text("psf_pregame_summary", "psf_ui_pregame_short", 0, 30, 130, 46,
                      tip="psf_ui_pregame_tooltip", transparent=False)))
            add(pick("info", "gamesetup_country_details"),
                _text("psf_pregame_explanation", "psf_ui_pregame_description", 6, 30, 370, 104,
                      tip="psf_ui_pregame_tooltip", transparent=False))
            add(pick("info", "gamesetup_interesting_countries_window"),
                _text("psf_interesting_pregame_explanation", "psf_ui_pregame_description", 0, 35, 225, 160,
                      font="hoi4_typewriter16", tip="psf_ui_pregame_tooltip", transparent=False))
            # The native bookmark history binding supplies the selected
            # country/date.  It can display compiled text-icon charts without
            # attaching a campaign-only scripted GUI to the frontend.
            history = pick("history", "gamesetup_interesting_countries_window")
            height = history.properties["maxheight"]
            changes.append((height[0], height[1], "maxHeight = 160"))
            changes.append((history.end - 1, history.end - 1,
                            '\nmultiline = yes\nscrollbartype = "standardtext_slider"\n'))
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
    for mode, width, height in (("political", 512, 80), ("diplomatic", 376, 86)):
        sprite(f"GFX_psf_{mode}_summary_background", f"{mode}_summary_background", width, height,
               lambda x, y, w=width, h=height: (105, 105, 82, 255) if x in (0, w-1) or y in (0, h-1) else (39, 45, 42, 255))
    for group in groups:
        gid = group["id"]
        color = charts.color(group)
        kind = group.get("icon", group.get("kind", "party"))
        for size, suffix in ((24, "small"), (64, "large")):
            def badge(x: int, y: int, size: int = size, color: tuple[int, ...] = color, kind: str = kind) -> tuple[int, int, int, int]:
                c = (size - 1) / 2
                radius = size * .47
                d = (x - c) ** 2 + (y - c) ** 2
                if d > radius ** 2:
                    return 0, 0, 0, 0
                if d > (radius - max(1, size * .055)) ** 2:
                    return 215, 203, 155, 255
                # Geometric badges distinguish organization types; color distinguishes groups.
                xx, yy = (x - c) / size, (y - c) / size
                mark = False
                if kind in ("union", "trade_union"):
                    mark = abs(xx) < .24 and abs(yy) < .09 or abs(xx) < .06 and -.24 < yy < .24
                elif kind in ("business", "industrial_association", "corporation", "industrial"):
                    mark = abs(yy - .2) < .05 and abs(xx) < .28 or abs(xx) < .22 and -.2 < yy < .2 and int((xx+.24)*size/5) % 2 == 0
                elif kind in ("military", "military_clique"):
                    mark = abs(abs(xx) - (yy + .22) * .6) < .055 and -.24 < yy < .22
                elif kind in ("religious", "church", "religious_body"):
                    mark = abs(xx) < .05 and abs(yy) < .28 or abs(yy + .08) < .05 and abs(xx) < .2
                elif kind == "civic":
                    mark = .12 ** 2 < xx * xx + yy * yy < .24 ** 2
                elif kind == "faction":
                    mark = abs(xx) < .25 and (abs(yy + .17) < .045 or abs(yy) < .045 or abs(yy - .17) < .045)
                else:
                    mark = abs(xx) + abs(yy) < .26 and abs(xx) + abs(yy) > .12
                return (245, 241, 217, 255) if mark else (*color, 255)
            sprite(f"GFX_psf_group_{gid}_{suffix}", f"{gid}_{suffix}", size, size, badge)
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
        "alliances": ("Alliances", "政治联盟"),
        "none": ("None", "无"),
        "empty": ("", ""),
        "close": ("Close", "关闭"),
        "back": ("Organizations", "返回团体"),
        "legal": ("Legal", "合法活动"),
        "underground": ("Underground", "地下活动"),
        "underground_prohibited": ("Underground; legally prohibited", "地下活动（依法查禁）"),
        "banned": ("Banned", "已被查禁"),
        "inactive": ("Inactive", "尚未活动"),
        "government": ("Government", "执政"),
        "opposition": ("Opposition", "反对派"),
        "electoral": ("Electoral pact", "选举联盟"),
        "dissolved": ("Dissolved", "已解散"),
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
        "legitimacy_tip": ("Legitimacy: [?psf_legitimacy|1]/100\\nInstitutional mismatch: [?psf_alignment_gap|1]\\nGovernment support: [?psf_government_support|1]\\nGovernment influence: [?psf_government_influence|1]\\n\\nThe government has a political program; the actual institutions remain a separate property. A mismatch reduces legitimacy, while political actions can compensate.", "合法性：[?psf_legitimacy|1]/100\\n制度偏离：[?psf_alignment_gap|1]\\n政府支持：[?psf_government_support|1]\\n政府影响力：[?psf_government_influence|1]\\n\\n执政团体的政治主张与国家的实际制度分别记录。两者偏离会降低合法性，而政治行动可以弥补这种损失。"),
        "regime_line": ("[PSFUIRegime]", "[PSFUIRegime]"),
        "regime_tip": ("§Y[PSFUIRegime]§!\\n[PSFUIRegimeDescription]\\n\\n$psf_ui_legitimacy_tip$", "§Y[PSFUIRegime]§!\\n[PSFUIRegimeDescription]\\n\\n$psf_ui_legitimacy_tip$"),
        "government_tip": ("§Y[PSFUIGovernment]§!\\nPolitical tendency: [PSFUIGovIdeology]\\nGovernment satisfaction: [?psf_government_satisfaction|1]\\nMonthly legitimacy change: [?psf_legitimacy_change|2]", "§Y[PSFUIGovernment]§!\\n政治倾向：[PSFUIGovIdeology]\\n执政团体满意度：[?psf_government_satisfaction|1]\\n每月合法性变化：[?psf_legitimacy_change|2]"),
        "government_line": ("Government: [PSFUIGovernment]", "执政联盟：[PSFUIGovernment]"),
        "summary_metrics": ("Support [?psf_government_support|0]   Influence [?psf_government_influence|0]", "支持 [?psf_government_support|0]   影响力 [?psf_government_influence|0]"),
        "summary_legitimacy": ("Legitimacy [?psf_legitimacy|0]/100   Organizations [?psf_group_count|0]", "合法性 [?psf_legitimacy|0]/100   政治团体 [?psf_group_count|0]"),
        "side_title": ("[This.GetName]: political society", "[This.GetName]：政治社会"),
        "list_help": ("Support / influence / satisfaction", "支持率 / 影响力 / 满意度"),
        "axes_help": ("Each marker is an organization. Hover for its position and click for details.", "图标代表政治团体；悬停查看立场，点击查看详情。"),
        "axis_zero": ("0", "0"),
        "pregame_short": ("Political society", "政治社会"),
        "pregame_description": ("Organizations and alliances replace the vanilla party wheel.\\nPolitical institutions and issue positions are tracked separately.\\nOpen the politics view after starting to inspect this country.", "政治团体与政治联盟取代原版政党饼图。\\n国家制度与各议题立场分别记录。\\n开始游戏后，在政治界面查看该国的完整总览。"),
        "pregame_tooltip": ("The country-selection history shows support and influence for the selected starting date. The politics view shows live organization details after the campaign starts.", "国家选择页的历史栏展示所选开局日期的支持率与影响力。开始战役后，在政治界面查看实时团体详情。"),
    }
    for key, values in strings.items():
        add_loc(f"psf_ui_{key}", *values)

    definitions: list[str] = []
    definitions.append(_defined("PSFUIRegime", [(f"check_variable = {{ psf_regime = {r.get('_index', i+1)} }}", f"psf_regime_{r['id']}_name") for i, r in enumerate(manifest.get("regimes", []))]))
    definitions.append(_defined("PSFUIRegimeDescription", [(f"check_variable = {{ psf_regime = {r.get('_index', i+1)} }}", f"psf_regime_{r['id']}_desc") for i, r in enumerate(manifest.get("regimes", []))]))
    definitions.append(_defined("PSFUIGovIdeology", [(f"check_variable = {{ psf_government_ideology = {ideology.get('_index', i+1)} }}", f"psf_ideology_{ideology['id']}_name") for i, ideology in enumerate(manifest.get("ideologies", []))]))
    definitions.append(_defined("PSFUIGovernment", [(f"check_variable = {{ psf_governing_alliance = {alliance_indices[a['id']]} }}", f"psf_alliance_{a['id']}_name") for a in alliances]))
    for group in groups:
        gid = group["id"]
        definitions.append(_defined(f"PSFUIStatus_{gid}", [(f"check_variable = {{ psf_g_{gid}_status = 2 }} check_variable = {{ psf_g_{gid}_prohibited = 1 }}", "psf_ui_underground_prohibited")] + [(f"check_variable = {{ psf_g_{gid}_status = {n} }}", f"psf_ui_{label}") for n, label in enumerate(("inactive", "legal", "underground", "banned"))]))
        definitions.append(_defined(f"PSFUIIdeology_{gid}", [(f"check_variable = {{ psf_g_{gid}_ideology = {ideology.get('_index', i+1)} }}", f"psf_ideology_{ideology['id']}_name") for i, ideology in enumerate(manifest.get("ideologies", []))]))
        add_loc(f"psf_ui_row_{gid}",
                f"[?psf_g_{gid}_modified_support|0] / [?psf_g_{gid}_effective_influence|0] / [?psf_g_{gid}_modified_satisfaction|0]")
        definitions.append(_defined(f"PSFUIRowStatus_{gid}", [(f"check_variable = {{ psf_g_{gid}_status = {n} }}", f"psf_ui_{label}") for n, label in enumerate(("inactive", "legal", "underground", "banned"))]))
        add_loc(f"psf_ui_row_status_{gid}", f"[PSFUIRowStatus_{gid}]")
        add_loc(f"psf_ui_detail_metrics_{gid}",
                f"Support: [?psf_g_{gid}_modified_support|1]\\nInfluence: [?psf_g_{gid}_effective_influence|1]\\nSatisfaction: [?psf_g_{gid}_modified_satisfaction|1]",
                f"支持率：[?psf_g_{gid}_modified_support|1]\\n影响力：[?psf_g_{gid}_effective_influence|1]\\n满意度：[?psf_g_{gid}_modified_satisfaction|1]")
        add_loc(f"psf_ui_detail_status_{gid}", f"[PSFUIStatus_{gid}]    [PSFUIIdeology_{gid}]")
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
                add_loc(key, f"$psf_group_{gid}_short_name$: [?psf_g_{gid}_{metric}_share|1]%\\n")
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
                            sprite="GFX_tiled_button", size=(370, 44))
            rows += _icon(f"psf_row_icon_{gid}", group.get("small_icon", f"GFX_psf_group_{gid}_small"), 16, y + 10)
            rows += _icon(f"psf_row_color_{gid}", f"GFX_psf_color_{gid}", 42, y + 28)
            rows += _text(f"psf_row_name_{gid}", f"psf_group_{gid}_short_name", 54, y + 2, 315, 20, font="hoi_18mbs")
            rows += _text(f"psf_row_values_{gid}", f"psf_ui_row_{gid}", 54, y + 23, 184, 20)
            rows += _text(f"psf_row_status_{gid}", f"psf_ui_row_status_{gid}", 242, y + 23, 128, 20)
            row_effects.append(f"psf_select_{gid}_click = {{ set_variable = {{ ROOT.psf_ui_group = {index} }} set_variable = {{ ROOT.psf_ui_page = 1 }} }}")
            detail_triggers, detail_effects = [], []
            detail = _icon(f"psf_large_icon_{gid}", group.get("large_icon", f"GFX_psf_group_{gid}_large"), 8, 4)
            detail += _text(f"psf_detail_name_{gid}", f"psf_group_{gid}_name", 84, 4, 286, 56, font="hoi_18mbs",
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _icon(f"psf_detail_color_{gid}", f"GFX_psf_color_{gid}", 84, 66)
            detail += _text(f"psf_detail_kind_{gid}", f"psf_ui_kind_{gid}", 98, 61, 272)
            detail += _text(f"psf_detail_status_{gid}", f"psf_ui_detail_status_{gid}", 8, 92, 362, 44,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _text(f"psf_detail_metrics_{gid}", f"psf_ui_detail_metrics_{gid}", 8, 140, 362, 66,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _text(f"psf_detail_description_{gid}", f"psf_group_{gid}_desc", 8, 212, 362, 132,
                            scroll=True, transparent=False)
            detail += _text(f"psf_detail_positions_{gid}", f"psf_ui_positions_{gid}", 8, 352, 362, max(36, len(axes) * 22))
            action_y = 360 + max(36, len(axes) * 22)
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
                          detail_effects, detail_triggers, []))
        pages.append((f"groups_{pid}", rows, f"{_flag(profile)} {list_visible}", row_effects, [], []))
        alliance_rows, ay = "", 0
        for alliance in profile.get("alliances", []):
            aid = alliance["id"]
            definitions.append(_defined(f"PSFUIAllianceRole_{aid}", [(f"check_variable = {{ psf_a_{aid}_active = 0 }}", "psf_ui_dissolved")] + [(f"check_variable = {{ psf_a_{aid}_role = {n} }}", f"psf_ui_{role}") for n, role in ((1, "government"), (2, "opposition"), (3, "electoral"))]))
            add_loc(f"psf_ui_alliance_stats_{aid}", f"[PSFUIAllianceRole_{aid}]    Cohesion [?psf_a_{aid}_cohesion|0]/100", f"[PSFUIAllianceRole_{aid}]    凝聚力 [?psf_a_{aid}_cohesion|0]/100")
            alliance_rows += _text(f"psf_alliance_name_{aid}", f"psf_alliance_{aid}_name", 8, ay, 362, 44,
                                   font="hoi_18mbs", tip=f"psf_alliance_{aid}_desc", transparent=False)
            alliance_rows += _text(f"psf_alliance_stats_{aid}", f"psf_ui_alliance_stats_{aid}", 8, ay + 48, 362)
            for group in profile.get("groups", []):
                gid = group["id"]
                definitions.append(_defined(f"PSFUIMember_{aid}_{gid}", [(f"check_variable = {{ psf_a_{aid}_g_{gid} = 1 }}", f"psf_ui_member_{gid}")], "psf_ui_empty"))
                for lang in LANGUAGES:
                    loc[lang][f"psf_ui_member_{gid}"] = f"$psf_group_{gid}_short_name$  "
            member_text = "".join(f"[PSFUIMember_{aid}_{g['id']}]" for g in profile.get("groups", []))
            add_loc(f"psf_ui_alliance_members_{aid}", member_text)
            alliance_rows += _text(f"psf_alliance_members_{aid}", f"psf_ui_alliance_members_{aid}", 8, ay + 76, 362, 70,
                                   scroll=True, transparent=False)
            ay += 160
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
                                    sprite=group.get("small_icon", f"GFX_psf_group_{gid}_small"), scale=0.666667)
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

    side_body = _text("psf_side_title", "psf_ui_side_title", 14, 12, 336, 44, font="hoi_18mbs")
    side_body += _button("psf_close", "", 375, 10, tip="psf_ui_close", sprite="GFX_closebutton")
    side_effects = ["psf_close_click = { set_variable = { ROOT.psf_ui_open = 0 } }"]
    for name, label, x, page in (("psf_tab_groups", "groups", 12, 0), ("psf_tab_spectrum", "spectrum", 140, 2), ("psf_tab_alliances", "alliances", 268, 3)):
        side_body += _button(name, f"psf_ui_{label}", x, 58)
        side_effects.append(f"{name}_click = {{ set_variable = {{ ROOT.psf_ui_page = {page} }} }}")

    gui_by_mode: dict[str, list[str]] = {mode: [] for mode in ("political", "diplomatic")}
    scripts_by_mode: dict[str, list[str]] = {mode: [] for mode in ("political", "diplomatic")}
    for mode, context, token in (("political", "player_context", "politics_tab"),
                                 ("diplomatic", "selected_country_context", "selected_country_view_diplomacy")):
        def scripted_window(name: str, body: str, x: int, y: int, width: int, height: int,
                            visible: str, *, parent: str | None = None, effects: list[str] = (),
                            triggers: list[str] = (), properties: list[str] = (),
                            scroll: bool = False, background: bool | str = False, dirty: bool = False) -> None:
            window = f"psf_{mode}_{name}"
            gui_by_mode[mode].append(_container(window, x, y, width, height, body, scroll=scroll, background=background))
            attachment = f"parent_scripted_gui = {parent}" if parent else f"parent_window_token = {token}"
            script = (f"{window}_gui = {{\ncontext_type = {context}\n{attachment}\nwindow_name = {window}\n"
                      + ("dirty = psf_ui_revision\n" if dirty else "")
                      + f"visible = {{ {visible} }}\nai_enabled = {{ always = no }}\n")
            for key, values in (("effects", effects), ("triggers", triggers), ("properties", properties)):
                if values:
                    script += key + " = {\n" + "\n".join(values) + "\n}\n"
            scripts_by_mode[mode].append(script + "}\n")

        scripted_window("society_side", side_body, 552, 0, 414, 590, side_visible,
                        effects=side_effects, background=True)
        for name, body, visible, effects, triggers, properties in pages:
            scripted_window(name, body, 8, 100, 396, 478, f"{side_visible} {visible}",
                            parent=f"psf_{mode}_society_side_gui", effects=effects, triggers=triggers,
                            properties=properties, scroll=True)

        # The native tokens supply the correct view origin (including the top
        # bar offset and animation). No ad-hoc *_instance mount is assumed.
        summary, pie_properties = "", []
        for metric, x in (("support", 0), ("influence", 74)):
            summary += _text(f"psf_{mode}_{metric}_label", f"psf_ui_{metric}", x, 0, 72, 17,
                             tip=f"psf_ui_{metric}_chart_tip", transparent=False)
            for index, (left, top, _, _) in enumerate(charts.geometry()):
                name = f"psf_pie_{metric}_{index:03}"
                summary += _icon(name, f"GFX_psf_pie_sector_{index:03}", x + left, 17 + top)
                pie_properties.append(f"{name} = {{ frame = psf_pie_{metric}_frames^{index} }}")
            summary += _button(f"psf_open_{metric}", "", x, 17,
                               sprite="GFX_pol_piechart_overlay_63x63", tip=f"psf_ui_{metric}_chart_tip")
        text_x = 150 if mode == "political" else 146
        text_width = 226 if mode == "political" else 228
        summary += _text(f"psf_{mode}_regime", "psf_ui_regime_line", text_x, 0, text_width, 20,
                         font="hoi_18mbs", tip="psf_ui_regime_tip", transparent=False)
        summary += _text(f"psf_{mode}_government", "psf_ui_government_line", text_x,
                         20 if mode == "political" else 23, text_width, 20,
                         tip="psf_ui_government_tip", transparent=False)
        if mode == "political":
            summary += _text(f"psf_{mode}_metrics", "psf_ui_summary_metrics", text_x, 40, text_width, 20,
                             tip="psf_ui_influence_tip", transparent=False)
            summary += _text(f"psf_{mode}_legitimacy", "psf_ui_summary_legitimacy", text_x, 60, text_width, 19,
                             tip="psf_ui_legitimacy_tip", transparent=False)
            summary += _button("psf_open_groups", "psf_ui_groups", 382, 0)
            summary += _button("psf_open_spectrum", "psf_ui_spectrum", 382, 36)
        else:
            summary += _button("psf_open_groups", "psf_ui_groups", 146, 50,
                               sprite="GFX_tiled_button", size=(110, 30))
            summary += _button("psf_open_spectrum", "psf_ui_spectrum", 262, 50,
                               sprite="GFX_tiled_button", size=(110, 30))
        summary_effects = [f"psf_open_{name}_click = {{ set_variable = {{ ROOT.psf_ui_open = 1 }} set_variable = {{ ROOT.psf_ui_page = {page} }} }}"
                           for name, page in (("groups", 0), ("spectrum", 2), ("support", 0), ("influence", 0))]
        scripted_window("summary", summary, 18 if mode == "political" else 144,
                        302 if mode == "political" else 160, 512 if mode == "political" else 376,
                        80 if mode == "political" else 86, "has_country_flag = psf_initialized",
                        effects=summary_effects, properties=pie_properties,
                        background=f"GFX_psf_{mode}_summary_background", dirty=True)

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
    patches = patch_native(source, output)
    metadata = {"native_patches": patches, "organizations": len(groups), "axes": len(axes),
                "sidebar": {"width": 414, "height": 590, "offset_from_native_left": 552,
                            "pages_per_context": len(pages), "page_visibility": "independent scripted GUI roots"},
                "attachments": {"political": "politics_tab", "diplomatic": "selected_country_view_diplomacy"},
                "charts": {"sectors": charts.SECTORS, "diameter": charts.SIZE, "neutral_frame": 1,
                           "support": "Active electoral organizations, normalized modified support",
                           "influence": "All active organizations, normalized effective influence"},
                "localization_keys_per_language": len(loc["english"]),
                "scope_policy": "THIS supplies target data; ROOT owns UI state; mutation requires tag = ROOT",
                "pregame": "Native bookmark history supports a compact country/date color-key support/influence table; map-side details retain a notice"}
    write("psf_ui_manifest.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata
