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
               body: str = "", *, scroll: bool = False, background: bool = False) -> str:
    extra = '\nverticalScrollbar = "right_vertical_slider"\nscroll_wheel_factor = 32\nsmooth_scrolling = yes' if scroll else ""
    bg = '\nbackground = { name = "Background" quadTextureSprite = "GFX_tiled_window_1b_border" }' if background else ""
    return (f'containerWindowType = {{\nname = "{name}"\n'
            f'position = {{ x = {x} y = {y} }}\nsize = {{ width = {width} height = {height} }}\n'
            f'clipping = {"yes" if scroll else "no"}{extra}{bg}\n{body}\n}}\n')


def _text(name: str, key: str, x: int, y: int, width: int, height: int = 22,
          *, font: str = "hoi_16mbs", tip: str | None = None,
          transparent: bool = True) -> str:
    tooltip = f'\npdx_tooltip = "{tip}"' if tip else ""
    return (f'instantTextboxType = {{ name = "{name}" position = {{ x = {x} y = {y} }} '
            f'font = "{font}" text = "{key}" maxWidth = {width} maxHeight = {height} '
            f'fixedsize = yes multiline = {"yes" if height > 24 else "no"} '
            f'alwaystransparent = {"yes" if transparent else "no"}{tooltip} }}\n')


def _icon(name: str, sprite: str, x: int, y: int, *, tip: str | None = None,
          scale: float | None = None) -> str:
    extra = f' pdx_tooltip = "{tip}"' if tip else ""
    extra += f" scale = {scale:g}" if scale is not None else ""
    return (f'iconType = {{ name = "{name}" spriteType = "{sprite}" '
            f'position = {{ x = {x} y = {y} }} alwaystransparent = {"no" if tip else "yes"}{extra} }}\n')


def _button(name: str, label: str, x: int, y: int, *, tip: str | None = None,
            sprite: str = "GFX_button_123x34", scale: float | None = None) -> str:
    extra = f' pdx_tooltip = "{tip}"' if tip else ""
    extra += f" scale = {scale:g}" if scale is not None else ""
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
            add(root, _container("psf_political_summary_mount", 18, 302, 512, 80))
            add(root, _container("psf_political_side_mount", 552, 0, 414, 590))
        elif filename == "countrydiplomacyview.gui":
            for name in ("political_pie_chart", "ruling_party_info"):
                hide(name, "diplomacy_tab_top")
            hide("ideology_icon", "country_info")
            add(pick("diplomacy_tab_top"), _container("psf_diplomatic_summary_mount", 144, 0, 376, 86))
            unclipped(pick("countrydiplomacyview"))
            add(pick("countrydiplomacyview"), _container("psf_diplomatic_side_mount", 552, 0, 414, 590))
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
        for start, end, replacement in sorted(changes, reverse=True):
            data = data[:start] + replacement + data[end:]
        # Assert every engine-owned name and original ancestry is retained.
        original_identity = [(n.kind.lower(), n.ancestry, n.name) for n in nodes if n.name]
        patched_identity = {(n.kind.lower(), n.ancestry, n.name) for n in gui_nodes(data) if n.name}
        if any(identity not in patched_identity for identity in original_identity):
            raise AssertionError(f"Native widget identity changed in {filename}")
        path = output / "interface" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8-sig")
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

    def row(x: int, y: int) -> tuple[int, int, int, int]:
        if x in (0, 369) or y in (0, 55):
            return 105, 103, 83, 255
        return (47, 53, 48, 255) if y < 28 else (40, 46, 42, 255)

    sprite("GFX_psf_group_row", "group_row", 370, 56, row, True)
    sprite("GFX_psf_axis_track", "axis_track", 202, 6,
           lambda x, y: (166, 157, 120, 255) if y in (2, 3) else ((210, 199, 152, 255) if x in (0, 100, 200) else (0, 0, 0, 0)))
    for group in groups:
        gid = group["id"]
        digest = hashlib.sha256(gid.encode()).digest()
        color = tuple(86 + b % 140 for b in digest[:3])
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
    return "spriteTypes = {\n" + "\n".join(sprites) + "\n}\n"


def _defined(name: str, choices: list[tuple[str, str]], fallback: str = "psf_ui_none") -> str:
    body = "".join(f"text = {{ trigger = {{ {trigger} }} localization_key = {key} }}\n" for trigger, key in choices)
    return f"defined_text = {{ name = {name}\n{body}text = {{ localization_key = {fallback} }}\n}}\n"


def _flag(profile: dict[str, Any]) -> str:
    return f"has_country_flag = psf_profile_{profile['id']}"


def _value(obj: Any, language: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(language, obj.get("english", default)))
    return str(obj) if obj is not None else default


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
        "pregame_tooltip": ("The vanilla ideology wheel is disabled. PSF initializes its country data when the game starts; the lobby does not display uninitialized runtime values.", "原版意识形态饼图已移除。PSF 在开始游戏时初始化国家数据；开局选国界面不显示尚未初始化的运行时数值。"),
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
                f"[?psf_g_{gid}_support|0] / [?psf_g_{gid}_effective_influence|0] / [?psf_g_{gid}_satisfaction|0]    [PSFUIStatus_{gid}]")
        add_loc(f"psf_ui_detail_metrics_{gid}",
                f"Support [?psf_g_{gid}_support|1]    Influence [?psf_g_{gid}_effective_influence|1]    Satisfaction [?psf_g_{gid}_satisfaction|1]",
                f"支持率 [?psf_g_{gid}_support|1]    影响力 [?psf_g_{gid}_effective_influence|1]    满意度 [?psf_g_{gid}_satisfaction|1]")
        add_loc(f"psf_ui_detail_status_{gid}", f"[PSFUIStatus_{gid}]    [PSFUIIdeology_{gid}]")
        kinds = {"party": ("Political party", "政党"), "trade_union": ("Trade union", "工会"), "union": ("Trade union", "工会"), "business": ("Business association", "工商团体"), "industrial_association": ("Industrial association", "产业联合会"), "corporation": ("Corporation", "法团"), "military": ("Military organization", "军人团体"), "military_clique": ("Military organization", "军人团体"), "religious": ("Religious organization", "宗教团体"), "church": ("Religious organization", "宗教团体"), "movement": ("Political movement", "政治运动"), "professional": ("Professional association", "职业团体"), "employers_association": ("Employers' association", "雇主协会"), "civic": ("Civic organization", "公民团体"), "faction": ("Political faction", "政治派系")}
        kind_en, kind_zh = kinds.get(group.get("kind", "party"), (group.get("kind", "Organization").replace("_", " "), "政治团体"))
        add_loc(f"psf_ui_kind_{gid}", kind_en, kind_zh)
        add_loc(f"psf_ui_group_tooltip_{gid}",
                f"§Y$psf_group_{gid}_name$§!\\n$psf_ui_kind_{gid}$ — [PSFUIStatus_{gid}]\\n[PSFUIIdeology_{gid}]\\n\\n$psf_ui_detail_metrics_{gid}$\\nInstitutional capacity before suppression: [?psf_g_{gid}_influence|1]\\n\\n$psf_group_{gid}_desc$",
                f"§Y$psf_group_{gid}_name$§!\\n$psf_ui_kind_{gid}$　[PSFUIStatus_{gid}]\\n[PSFUIIdeology_{gid}]\\n\\n$psf_ui_detail_metrics_{gid}$\\n查禁前的制度影响力：[?psf_g_{gid}_influence|1]\\n\\n$psf_group_{gid}_desc$")
        position_en, position_zh = [], []
        for axis in axes:
            aid = axis["id"]
            position_en.append(f"$psf_axis_{aid}_name$: [?psf_g_{gid}_position_{aid}|0]")
            position_zh.append(f"$psf_axis_{aid}_name$：[?psf_g_{gid}_position_{aid}|0]")
            add_loc(f"psf_ui_marker_{gid}_{aid}",
                    f"§Y$psf_group_{gid}_name$§!\\n$psf_axis_{aid}_name$: [?psf_g_{gid}_position_{aid}|0]\\n$psf_axis_{aid}_left$ (-100) — $psf_axis_{aid}_right$ (+100)\\n\\n$psf_axis_{aid}_desc$\\n\\nClick to inspect this organization.",
                    f"§Y$psf_group_{gid}_name$§!\\n$psf_axis_{aid}_name$：[?psf_g_{gid}_position_{aid}|0]\\n$psf_axis_{aid}_left$（-100）— $psf_axis_{aid}_right$（+100）\\n\\n$psf_axis_{aid}_desc$\\n\\n点击查看该团体。")
        add_loc(f"psf_ui_positions_{gid}", "\\n".join(position_en), "\\n".join(position_zh))

    triggers: list[str] = []
    effects: list[str] = []
    properties: list[str] = []
    add_effect = lambda name, body: effects.append(f"{name}_click = {{ {body} }}")
    add_trigger = lambda name, body: triggers.append(f"{name} = {{ {body} }}")
    add_effect("psf_close", "set_variable = { ROOT.psf_ui_open = 0 }")
    for name, page in (("psf_tab_groups", 0), ("psf_tab_spectrum", 2), ("psf_tab_alliances", 3)):
        add_effect(name, f"set_variable = {{ ROOT.psf_ui_page = {page} }}")
    selection_condition = "OR = { " + " ".join(
        f"AND = {{ {_flag(profile)} check_variable = {{ ROOT.psf_ui_group = {group_indices[group['id']]} }} }}"
        for profile in profiles for group in profile.get("groups", [])
    ) + " }"
    add_trigger("psf_groups_page_visible", "OR = { check_variable = { ROOT.psf_ui_page = 0 } AND = { check_variable = { ROOT.psf_ui_page = 1 } NOT = { psf_ui_selection_is_current = yes } } }")
    add_trigger("psf_detail_page_visible", "check_variable = { ROOT.psf_ui_page = 1 } psf_ui_selection_is_current = yes")
    for name, page in (("psf_spectrum_page", 2), ("psf_alliances_page", 3)):
        add_trigger(f"{name}_visible", f"check_variable = {{ ROOT.psf_ui_page = {page} }}")

    group_page = _text("psf_list_help", "psf_ui_list_help", 10, 0, 366, tip="psf_ui_support_tip", transparent=False)
    detail_page = ""
    alliance_page = ""
    for profile in profiles:
        pid = profile["id"]
        rows = ""
        for row, group in enumerate(profile.get("groups", [])):
            gid = group["id"]
            index = group_indices[gid]
            row_content = _button(f"psf_select_{gid}", "", 0, 0, tip=f"psf_ui_group_tooltip_{gid}", sprite="GFX_psf_group_row")
            row_content += _icon(f"psf_row_icon_{gid}", group.get("small_icon", f"GFX_psf_group_{gid}_small"), 10, 16)
            row_content += _text(f"psf_row_name_{gid}", f"psf_group_{gid}_short_name", 44, 5, 318, font="hoi_18mbs")
            row_content += _text(f"psf_row_values_{gid}", f"psf_ui_row_{gid}", 44, 31, 318)
            rows += _container(f"psf_row_{gid}", 0, row * 60, 370, 56, row_content)
            select = f"set_variable = {{ ROOT.psf_ui_group = {index} }} set_variable = {{ ROOT.psf_ui_page = 1 }}"
            add_effect(f"psf_select_{gid}", select)
            # Authorization is enforced again in effects, not just disabled appearance.
            for action, cost, guard in (("ban", 50, f"check_variable = {{ psf_g_{gid}_status = 1 }} check_variable = {{ psf_g_{gid}_governing = 0 }}"),
                                        ("legalize", 25, f"OR = {{ check_variable = {{ psf_g_{gid}_status = 2 }} check_variable = {{ psf_g_{gid}_status = 3 }} }}"),
                                        ("activate", 25, f"check_variable = {{ psf_g_{gid}_status = 0 }}")):
                condition = f"tag = ROOT {guard} has_political_power > {cost - 1}"
                add_trigger(f"psf_{action}_{gid}_click_enabled", condition)
                add_trigger(f"psf_{action}_{gid}_visible", f"tag = ROOT {guard}")
                add_effect(f"psf_{action}_{gid}", f"if = {{ limit = {{ {condition} }} add_political_power = -{cost} psf_{action}_{gid} = yes }}")
            detail = _icon(f"psf_large_icon_{gid}", group.get("large_icon", f"GFX_psf_group_{gid}_large"), 0, 4)
            detail += _text(f"psf_detail_name_{gid}", f"psf_group_{gid}_name", 76, 4, 284, 56, font="hoi_18mbs")
            detail += _text(f"psf_detail_kind_{gid}", f"psf_ui_kind_{gid}", 76, 61, 284)
            detail += _text(f"psf_detail_status_{gid}", f"psf_ui_detail_status_{gid}", 0, 92, 365, 44,
                            tip=f"psf_ui_group_tooltip_{gid}", transparent=False)
            detail += _text(f"psf_detail_metrics_{gid}", f"psf_ui_detail_metrics_{gid}", 0, 140, 365, 42,
                            tip="psf_ui_influence_tip", transparent=False)
            detail += _text(f"psf_detail_description_{gid}", f"psf_group_{gid}_desc", 0, 186, 365, 160)
            detail += _text(f"psf_detail_positions_{gid}", f"psf_ui_positions_{gid}", 0, 352, 365, max(36, len(axes) * 22))
            action_y = 360 + max(36, len(axes) * 22)
            for action in ("ban", "legalize", "activate"):
                detail += _button(f"psf_{action}_{gid}", f"psf_ui_{action}", 0, action_y,
                                  tip=f"psf_ui_{action}_tip", sprite="GFX_button_238x38")
            detail_page += _container(f"psf_detail_{gid}", 8, 0, 370, action_y + 50, detail)
            add_trigger(f"psf_detail_{gid}_visible", f"{_flag(profile)} check_variable = {{ ROOT.psf_ui_group = {index} }}")
        group_page += _container(f"psf_profile_rows_{pid}", 8, 28, 370, max(60, len(profile.get("groups", [])) * 60), rows)
        add_trigger(f"psf_profile_rows_{pid}_visible", _flag(profile))
        alliance_rows = ""
        ay = 0
        for alliance in profile.get("alliances", []):
            aid = alliance["id"]
            definitions.append(_defined(f"PSFUIAllianceRole_{aid}", [(f"check_variable = {{ psf_a_{aid}_active = 0 }}", "psf_ui_dissolved")] + [(f"check_variable = {{ psf_a_{aid}_role = {n} }}", f"psf_ui_{role}") for n, role in ((1, "government"), (2, "opposition"), (3, "electoral"))]))
            add_loc(f"psf_ui_alliance_stats_{aid}", f"[PSFUIAllianceRole_{aid}]    Cohesion [?psf_a_{aid}_cohesion|0]/100", f"[PSFUIAllianceRole_{aid}]    凝聚力 [?psf_a_{aid}_cohesion|0]/100")
            alliance_rows += _text(f"psf_alliance_name_{aid}", f"psf_alliance_{aid}_name", 0, ay, 365, 44, font="hoi_18mbs", tip=f"psf_alliance_{aid}_desc", transparent=False)
            alliance_rows += _text(f"psf_alliance_stats_{aid}", f"psf_ui_alliance_stats_{aid}", 0, ay + 48, 365)
            my = ay + 76
            for group in profile.get("groups", []):
                gid = group["id"]
                # All profile groups get a slot: membership can change through scripts.
                # Empty slots intentionally collapse through a dynamic list-free display:
                # all current members are exposed in a compact, wrapping scripted string.
                definitions.append(_defined(f"PSFUIMember_{aid}_{gid}", [(f"check_variable = {{ psf_a_{aid}_g_{gid} = 1 }}", f"psf_ui_member_{gid}")], "psf_ui_empty"))
                for lang in LANGUAGES:
                    loc[lang][f"psf_ui_member_{gid}"] = f"$psf_group_{gid}_short_name$  "
            member_text = "".join(f"[PSFUIMember_{aid}_{g['id']}]" for g in profile.get("groups", []))
            add_loc(f"psf_ui_alliance_members_{aid}", member_text)
            alliance_rows += _text(f"psf_alliance_members_{aid}", f"psf_ui_alliance_members_{aid}", 0, my, 365, 70)
            ay += 160
        alliance_page += _container(f"psf_alliances_{pid}", 8, 0, 370, max(60, ay), alliance_rows)
        add_trigger(f"psf_alliances_{pid}_visible", _flag(profile))

    spectrum = _text("psf_axes_help", "psf_ui_axes_help", 8, 0, 366, 44)
    axis_height = 66 + max((len(p.get("groups", [])) for p in profiles), default=1) * 18
    for i, axis in enumerate(axes):
        aid = axis["id"]
        y = 50 + i * axis_height
        axis_content = _text(f"psf_axis_label_{aid}", f"psf_axis_{aid}_name", 0, 0, 370, font="hoi_18mbs", tip=f"psf_axis_{aid}_desc", transparent=False)
        axis_content += _text(f"psf_axis_left_{aid}", f"psf_axis_{aid}_left", 0, 24, 178)
        axis_content += _text(f"psf_axis_right_{aid}", f"psf_axis_{aid}_right", 192, 24, 178)
        # Each track spans exactly -100..100.  A marker's native x property reads
        # the runtime coordinate directly; changes of position need no GUI rebuild.
        for profile in profiles:
            pid = profile["id"]
            markers = ""
            for gi, group in enumerate(profile.get("groups", [])):
                gid = group["id"]
                name = f"psf_axis_marker_{gid}_{aid}"
                markers += _icon(f"psf_axis_track_{gid}_{aid}", "GFX_psf_axis_track", -93, gi * 18 + 5)
                markers += _button(name, "", 0, gi * 18, tip=f"psf_ui_marker_{gid}_{aid}", sprite=group.get("small_icon", f"GFX_psf_group_{gid}_small"), scale=0.666667)
                properties.append(f"{name} = {{ x = psf_g_{gid}_position_{aid} }}")
                add_trigger(f"{name}_visible", f"check_variable = {{ psf_g_{gid}_status > 0 }}")
                add_effect(name, f"set_variable = {{ ROOT.psf_ui_group = {group_indices[gid]} }} set_variable = {{ ROOT.psf_ui_page = 1 }}")
            marker_parent = f"psf_axis_profile_{pid}_{aid}"
            axis_content += _container(marker_parent, 176, 48, 200, axis_height - 48, markers)
            add_trigger(f"{marker_parent}_visible", _flag(profile))
        spectrum += _container(f"psf_axis_{aid}", 8, y, 370, axis_height - 2, axis_content)

    side_body = _text("psf_side_title", "psf_ui_side_title", 14, 12, 336, 44, font="hoi_18mbs")
    side_body += _button("psf_close", "", 375, 10, tip="psf_ui_close", sprite="GFX_closebutton")
    for name, label, x in (("psf_tab_groups", "groups", 12), ("psf_tab_spectrum", "spectrum", 140), ("psf_tab_alliances", "alliances", 268)):
        side_body += _button(name, f"psf_ui_{label}", x, 58)
    side_body += _container("psf_groups_page", 8, 100, 396, 478, group_page, scroll=True)
    side_body += _container("psf_detail_page", 8, 100, 396, 478, detail_page, scroll=True)
    side_body += _container("psf_spectrum_page", 8, 100, 396, 478, spectrum, scroll=True)
    side_body += _container("psf_alliances_page", 8, 100, 396, 478, alliance_page, scroll=True)
    gui = [_container("psf_society_side", 0, 0, 414, 590, side_body, background=True)]

    # Two compact summary layouts share data and effects, but honor different
    # available rectangles. They do not cover leaders, focuses, laws or advisors.
    for mode, width, button_x in (("political", 512, 382), ("diplomatic", 376, 248)):
        summary = _text(f"psf_{mode}_regime", "psf_ui_regime_line", 0, 0, button_x - 6, 20, font="hoi_18mbs", tip="psf_ui_regime_tip", transparent=False)
        summary += _text(f"psf_{mode}_government", "psf_ui_government_line", 0, 20 if mode == "political" else 22, button_x - 6, 20, tip="psf_ui_government_tip", transparent=False)
        summary += _text(f"psf_{mode}_metrics", "psf_ui_summary_metrics", 0, 40 if mode == "political" else 43, button_x - 6, 20, tip="psf_ui_influence_tip", transparent=False)
        summary += _text(f"psf_{mode}_legitimacy", "psf_ui_summary_legitimacy", 0, 60 if mode == "political" else 65, button_x - 6, 19, tip="psf_ui_legitimacy_tip", transparent=False)
        summary += _button("psf_open_groups", "psf_ui_groups", button_x, 0)
        summary += _button("psf_open_spectrum", "psf_ui_spectrum", button_x, 36)
        gui.append(_container(f"psf_{mode}_summary", 0, 0, width, 80 if mode == "political" else 86, summary))

    scripted: list[str] = []
    for mode, context in (("political", "player_context"), ("diplomatic", "selected_country_context")):
        scripted.append(f'''psf_{mode}_summary_gui = {{
context_type = {context}
parent_window_name = psf_{mode}_summary_mount
window_name = psf_{mode}_summary
visible = {{ has_country_flag = psf_initialized }}
ai_enabled = {{ always = no }}
effects = {{
psf_open_groups_click = {{ set_variable = {{ ROOT.psf_ui_open = 1 }} set_variable = {{ ROOT.psf_ui_page = 0 }} }}
psf_open_spectrum_click = {{ set_variable = {{ ROOT.psf_ui_open = 1 }} set_variable = {{ ROOT.psf_ui_page = 2 }} }}
}}
}}''')
        scripted.append(f'''psf_{mode}_society_gui = {{
context_type = {context}
parent_window_name = psf_{mode}_side_mount
window_name = psf_society_side
visible = {{ has_country_flag = psf_initialized check_variable = {{ ROOT.psf_ui_open = 1 }} }}
ai_enabled = {{ always = no }}
triggers = {{
{chr(10).join(triggers)}
}}
effects = {{
{chr(10).join(effects)}
}}
properties = {{
{chr(10).join(properties)}
}}
}}''')

    def write(relative: str, content: str, bom: bool = False) -> None:
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith(".txt"):
            # check_variable defaults to >= in the engine.  UI identities need
            # explicit equality, especially with stable hashed numeric IDs.
            content = re.sub(
                r"check_variable\s*=\s*\{\s*([A-Za-z0-9_.]+)\s*=\s*([A-Za-z0-9_.-]+)\s*\}",
                lambda m: f"check_variable = {{ var = {m[1]} value = {m[2]} compare = equals }}",
                content,
            )
        path.write_text(content, encoding="utf-8-sig" if bom else "utf-8")

    write("common/scripted_triggers/psf_ui.txt", f"psf_ui_selection_is_current = {{ {selection_condition} }}\n")
    write("interface/psf_society.gui", "guiTypes = {\n" + "\n".join(gui) + "\n}\n", True)
    write("interface/psf_society.gfx", _artwork(output, groups), True)
    write("common/scripted_guis/psf_society.txt", "scripted_gui = {\n" + "\n".join(scripted) + "\n}\n")
    write("common/scripted_localisation/psf_ui.txt", "\n".join(definitions))
    for lang, keys in loc.items():
        # Literal backslash-n is intentional HOI4 localization syntax.
        lines = [f"l_{lang}:"]
        for key, value in sorted(keys.items()):
            lines.append(f' {key}:0 "{value.replace(chr(34), chr(92)+chr(34))}"')
        write(f"localisation/{lang}/psf_ui_l_{lang}.yml", "\n".join(lines) + "\n", True)
    source = Path(vanilla_path) if vanilla_path else ASSETS
    if (source / "interface").is_dir():
        source = source / "interface"
    patches = patch_native(source, output)
    metadata = {"native_patches": patches, "organizations": len(groups), "axes": len(axes),
                "sidebar": {"width": 414, "height": 590, "offset_from_native_left": 552},
                "localization_keys_per_language": len(loc["english"]),
                "scope_policy": "THIS supplies target data; ROOT owns UI state; mutation requires tag = ROOT",
                "pregame": "Static notice only; runtime values initialize at game start"}
    write("psf_ui_manifest.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata
