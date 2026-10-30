#!/usr/bin/env python3
"""Check native/PSF layout boundaries; optionally draw a geometric SVG projection.

This reads the emitted .gui files. The SVG is a coordinate audit, not an HOI4
render: native textures, fonts, clipping behavior and input need an engine run.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psf.ui import Node, gui_nodes


def property_block(node: Node, key: str) -> dict[str, str]:
    child = next((n for n in node.children if n.kind.lower() == key.lower()), None)
    return {} if child is None else {k: v[2].strip('"') for k, v in child.properties.items()}


def point(node: Node) -> tuple[int, int]:
    p = property_block(node, "position")
    return int(p.get("x", "0")), int(p.get("y", "0"))


def size(node: Node) -> tuple[int, int]:
    p = property_block(node, "size")
    return int(p.get("width", p.get("x", "0"))), int(p.get("height", p.get("y", "0")))


def named(nodes: list[Node], name: str, ancestor: str | None = None) -> Node:
    items = [n for n in nodes if n.name == name and (ancestor is None or ancestor in n.ancestry)]
    if len(items) != 1:
        raise ValueError(f"Expected one {ancestor or ''}/{name}, found {len(items)}")
    return items[0]


def society_nodes(mod: Path) -> list[Node]:
    return [node for path in sorted((mod / "interface").glob("psf_society*.gui"))
            for node in gui_nodes(path.read_text(encoding="utf-8"))]


def script_bindings(mod: Path) -> dict[str, Node]:
    return {node.properties["window_name"][2].strip('"'): node
            for path in sorted((mod / "common/scripted_guis").glob("psf_society*.txt"))
            for node in gui_nodes(path.read_text(encoding="utf-8"))
            if "window_name" in node.properties}


def audit(mod: Path) -> dict:
    politics = gui_nodes((mod / "interface/countrypoliticsview.gui").read_text(encoding="utf-8-sig"))
    diplomacy = gui_nodes((mod / "interface/countrydiplomacyview.gui").read_text(encoding="utf-8-sig"))
    society = society_nodes(mod)
    bindings = script_bindings(mod)
    windows = {n.name: n for n in society if n.kind == "containerWindowType" and n.parent and n.parent.kind == "guiTypes"}
    pol_summary = windows["psf_political_summary"]
    dip_summary = windows["psf_diplomatic_summary"]
    pol_bottom = point(pol_summary)[1] + size(pol_summary)[1]
    native_bottom_start = point(named(politics, "politics_bottom"))[1]
    diplomacy_token_y = point(named(diplomacy, "country_info"))[1]
    dip_bottom = diplomacy_token_y + point(dip_summary)[1] + size(dip_summary)[1]
    focus_start = (point(named(diplomacy, "country_info"))[1]
                   + point(named(diplomacy, "diplomacy_tab_top"))[1]
                   + point(named(diplomacy, "active_national_focus_info", "diplomacy_tab_top"))[1])
    checks = {
        "political_summary_precedes_native_management_strip": pol_bottom <= native_bottom_start,
        "diplomatic_summary_precedes_native_focus": dip_bottom <= focus_start,
        "diplomatic_summary_starts_at_native_party_region": point(dip_summary)[1] == point(named(diplomacy, "diplomacy_tab_top"))[1],
        "every_script_owns_one_top_level_window": set(bindings) == set(windows),
    }
    frontend_nodes = gui_nodes((mod / "interface/frontendgamesetupview.gui").read_text(encoding="utf-8-sig"))
    for parent in ("gamesetup_country_details", "gamesetup_interesting_countries_window"):
        icon = named(frontend_nodes, "pol_faction_icon", parent)
        if icon.properties.get("hide", (0, 0, ""))[2] != "yes":
            continue  # Compat mode deliberately retains the native lobby.
        panel, party, label = (named(frontend_nodes, name, parent) for name in ("info", "party", "party_label"))
        pw, ph = size(panel)
        checks[parent + "_native_ideology_icon_hidden"] = point(icon)[0] == -12000
        checks[parent + "_politics_clipped_separately_from_history"] = panel.properties["clipping"][2] == "yes"
        checks[parent + "_party_label_precedes_value"] = point(label)[1] + int(label.properties["maxheight"][2]) <= point(party)[1]
        checks[parent + "_identity_and_dual_pie_width"] = int(party.properties["maxwidth"][2]) >= 286
        for field in ("party_label", "party", "leader_label", "leader"):
            child = named(frontend_nodes, field, parent)
            x, y = point(child)
            checks[parent + "/" + field + "_inside_info"] = (x >= 0 and y >= 0 and
                x + int(child.properties["maxwidth"][2]) <= pw and y + int(child.properties["maxheight"][2]) <= ph)
        if parent == "gamesetup_interesting_countries_window":
            fields = [named(frontend_nodes, field, parent) for field in ("leader_label", "leader", "party_label", "party")]
            checks[parent + "_text_rows_do_not_overlap"] = all(point(a)[1] + int(a.properties["maxheight"][2]) <= point(b)[1]
                                                                  for a, b in zip(fields, fields[1:]))
            checks[parent + "_politics_before_portrait"] = point(panel)[0] + pw <= point(named(frontend_nodes, "minor_portrait_overlay", parent))[0]
            checks[parent + "_politics_inside_native_window"] = point(panel)[1] + ph <= size(named(frontend_nodes, parent))[1]
    for mode, token in (("political", "politics_tab"), ("diplomatic", "selected_country_view_diplomacy")):
        sidebar = windows[f"psf_{mode}_society_side"]
        sw, sh = size(sidebar)
        checks[mode + "_sidebar_outside_native_panel"] = point(sidebar)[0] >= 550
        token_y = 0 if mode == "political" else diplomacy_token_y
        checks[mode + "_sidebar_header_aligned_to_native_top"] = point(sidebar)[1] + token_y == 0
        fixed = {n.name for n in sidebar.children if n.name}
        checks[mode + "_header_close_and_tabs_do_not_scroll"] = {"psf_header_chrome", "psf_side_title", "psf_close",
            "psf_tab_groups", "psf_tab_spectrum", "psf_tab_alliances"}.issubset(fixed) and "verticalscrollbar" not in sidebar.properties
        native_views = ("summary", "society_side", "government_party") if mode == "diplomatic" else ("summary", "society_side")
        for view in native_views:
            binding = bindings[f"psf_{mode}_{view}"]
            checks[mode + "_" + view + "_native_token"] = binding.properties.get("parent_window_token", (0, 0, ""))[2] == token
            checks[mode + "_" + view + "_no_fabricated_instance"] = "parent_window_name" not in binding.properties
        summary = windows[f"psf_{mode}_summary"]
        width, height = size(summary)
        for child in summary.children:
            x, y = point(child)
            if child.kind.lower() == "instanttextboxtype":
                w = int(child.properties["maxwidth"][2]); h = int(child.properties["maxheight"][2])
            elif child.kind.lower() == "buttontype":
                if child.name.startswith("psf_open_"):
                    w, h = 63, 63
                else:
                    w, h = size(child) if any(n.kind.lower() == "size" for n in child.children) else (123, 34)
            else:
                continue
            checks[f"{mode}/{child.name}_in_summary"] = 0 <= x and 0 <= y and x + w <= width and y + h <= height
        for name, node in windows.items():
            if not name.startswith(f"psf_{mode}_") or name in tuple(f"psf_{mode}_{view}" for view in native_views):
                continue
            x, y = point(node); w, h = size(node)
            checks[name + "_viewport_inside_sidebar"] = x >= 0 and y >= 0 and x + w <= sw and y + h <= sh
            checks[name + "_native_scrollbar"] = node.properties.get("verticalscrollbar", (0, 0, ""))[2] == '"right_vertical_slider"'
            checks[name + "_clips_to_viewport"] = node.properties.get("clipping", (0, 0, ""))[2] == "yes"
            checks[name + "_native_scroll_background"] = any(n.kind == "background" for n in node.children)
            margin = property_block(node, "margin")
            checks[name + "_scrollbar_gutter"] = int(margin.get("right", "0")) >= 12
            binding = bindings[name]
            checks[name + "_explicit_parent"] = binding.properties.get("parent_scripted_gui", (0, 0, ""))[2] == f"psf_{mode}_society_side_gui"
            checks[name + "_own_visibility"] = any(n.kind == "visible" for n in binding.children)
            checks[name + "_reacts_to_ui_state"] = "dirty" not in binding.properties
            checks[name + "_scrolling_begins_below_fixed_tabs"] = y >= 49 + 34
            content_width = w - int(margin.get("right", "0"))
            for child in node.children:
                if child.kind.lower() == "instanttextboxtype":
                    child_width = int(child.properties["maxwidth"][2])
                elif child.name and any(n.kind.lower() == "size" for n in child.children):
                    child_width = size(child)[0]
                else:
                    continue
                checks[f"{name}/{child.name}_leaves_scrollbar_gutter"] = (
                    point(child)[0] >= 0 and point(child)[0] + child_width <= content_width)
        if mode == "diplomatic":
            party_window = windows["psf_diplomatic_government_party"]
            native_icon = named(diplomacy, "ideology_icon", "country_info")
            # Hidden native widget retains Y=0, while X is moved off-screen.
            px, py = point(party_window); pw, ph = size(party_window)
            leader_x = point(named(diplomacy, "leader_name", "country_info"))[0]
            tabs_y = point(named(diplomacy, "relations_tab_button", "country_info"))[1]
            checks["diplomatic_party_icon_keeps_native_header_slot"] = px == 158 and py == point(native_icon)[1]
            checks["diplomatic_party_icon_precedes_leader_text_and_tabs"] = px + pw <= leader_x and py + ph <= tabs_y
            checks["diplomatic_party_icon_clips_artwork"] = party_window.properties.get("clipping", (0, 0, ""))[2] == "yes"
        for name, binding in bindings.items():
            if not name.startswith(f"psf_{mode}_"):
                continue
            if mode == "diplomatic":
                checks[name + "_refreshes_on_equal_revision_country_switch"] = "dirty" not in binding.properties
            window = windows[name]
            direct_names = {n.name for n in window.children if n.name}
            for section in binding.children:
                if section.kind not in ("triggers", "effects", "properties"):
                    continue
                for entry in section.children:
                    element = entry.kind
                    for suffix in ("_click_enabled", "_visible", "_click"):
                        if element.endswith(suffix):
                            element = element[:-len(suffix)]
                            break
                    checks[f"{name}/{entry.kind}_is_direct_control"] = element in direct_names
    for filename, nodes in (("politics", politics), ("diplomacy", diplomacy)):
        for node in nodes:
            if node.properties.get("hide", (0, 0, ""))[2] == "yes":
                x, y = point(node)
                if x == -12000:
                    checks[f"{filename}/{node.name}_preserves_vertical_extents"] = y > -1000
    return {
        "passed": all(checks.values()), "checks": checks,
        "political_summary_bottom": pol_bottom, "native_management_top": native_bottom_start,
        "diplomatic_summary_bottom": dip_bottom, "native_focus_top": focus_start,
        "sidebar_logical_size": [414, 590], "minimum_logical_resolution": [966, 668],
        "scripted_windows": len(windows),
        "limitation": "Geometric and binding audit only. Engine rendering, native fonts and input are not executed.",
    }


def projection(mod: Path, destination: Path) -> None:
    society = society_nodes(mod)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="2160" viewBox="0 0 1280 2160">',
             '<style>text{font-family:Arial,sans-serif;font-size:14px;fill:#e8e8e0}.small{font-size:11px;fill:#b8c5c5}.title{font-size:20px;font-weight:bold}</style>',
             '<rect width="1280" height="2160" fill="#171e22"/>',
             '<text class="title" x="24" y="30">PSF: audit of generated GUI coordinates</text>',
             '<text class="small" x="24" y="52">Geometric projection, not an HOI4 screenshot. All colored PSF rectangles use emitted .gui coordinates.</text>']

    def rect(x, y, w, h, fill, label="", border="#82918b"):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{border}"/>')
        if label:
            parts.append(f'<text class="small" x="{x+7}" y="{y+17}">{html.escape(label)}</text>')

    for row, mode in enumerate(("political", "diplomatic")):
        ox, oy = 24, 94 + row * 655
        filename = "countrypoliticsview.gui" if mode == "political" else "countrydiplomacyview.gui"
        native = gui_nodes((mod / "interface" / filename).read_text(encoding="utf-8-sig"))
        parts.append(f'<text class="title" x="{ox}" y="{oy-12}">{mode.title()} view</text>')
        rect(ox, oy, 550, 590, "#242e32", "Existing native view (widgets and ancestry retained)")
        if mode == "political":
            rect(ox+10, oy+44, 520, 245, "#303b3e", "Existing leader, national focus, spirits, faction and BOP controls")
            rect(ox, oy+383, 550, 42, "#564b32", "Existing occupation / exiles / subject controls")
            rect(ox, oy+430, 550, 160, "#303b3e", "Existing ideas, laws, advisers, autonomy")
            sx, sy = point(named(society, "psf_political_summary"))
        else:
            rect(ox+13, oy+160, 125, 138, "#303b3e", "Native leader")
            rect(ox+144, oy+248, 376, 76, "#564b32", "Existing national focus")
            party_window = named(society, "psf_diplomatic_government_party")
            px, py = point(party_window); pw, ph = size(party_window)
            rect(ox+px, oy+py+point(named(native,"country_info"))[1], pw, ph,
                 "#426354", "Party icon")
            sx, sy = point(named(society, "psf_diplomatic_summary"))
            sy += point(named(native, "country_info"))[1]
        summary = named(society, f"psf_{mode}_summary")
        w, h = size(summary)
        rect(ox+sx, oy+sy, w, h, "#273e34", "")
        labels = {"regime": "Actual regime", "government": "Governing party", "metrics": "Support / influence", "legitimacy": "Legitimacy / groups",
                  "party_label": "Government", "ideology_label": "Ideology", "support_label": "Support", "influence_label": "Influence"}
        for child in summary.children:
            x, y = point(child)
            if child.kind.lower() == "instanttextboxtype":
                width = int(child.properties["maxwidth"][2]);height = int(child.properties["maxheight"][2])
                label = next((v for k, v in labels.items() if child.name.endswith("_"+k)), child.name)
                rect(ox+sx+x, oy+sy+y, width, height, "#304e40", label, "#456250")
            elif child.kind.lower() == "buttontype":
                if child.name.endswith(("support", "influence")):
                    rect(ox+sx+x, oy+sy+y, 63, 63, "#426354", child.name.removeprefix("psf_open_").title())
                else:
                    rect(ox+sx+x, oy+sy+y, 63,63, "#5b5b43", "Party icon" if child.name.endswith("groups") else "Ideology")
        side_name = f"psf_{mode}_society_side"
        mx, my = point(named(society, side_name))
        if mode == "diplomatic":
            my += point(named(native, "country_info"))[1]
        side = named(society, side_name)
        sw, sh = size(side)
        rect(ox+mx, oy+my, sw, sh, "#273331", "")
        header=named(society,"psf_header_chrome",side_name);hx,hy=point(header);hw,hh=size(header)
        rect(ox+mx+hx,oy+my+hy,hw,hh,"#3a4743","Country title and close button — fixed")
        for name in ("psf_tab_groups", "psf_tab_spectrum", "psf_tab_alliances"):
            n=named(society,name,side_name);x,y=point(n)
            rect(ox+mx+x,oy+my+y,123,34,"#5b5b43",name.removeprefix("psf_tab_").title())
        page=next(n for n in society if n.name.startswith(f"psf_{mode}_groups_") and n.kind == "containerWindowType");px,py=point(page);pw,ph=size(page)
        rect(ox+mx+px,oy+my+py,pw,ph,"#202b29","")
        rect(ox+mx+px+pw-15,oy+my+py+24,10,ph-30,"#44524a","")
        rect(ox+mx+px+pw-15,oy+my+py+24,10,115,"#b4b29a","")
        children={n.name:n for n in page.children if n.name}
        for metric in ("support","influence","satisfaction"):
            heading=children[f"psf_list_{metric}"];x,y=point(heading)
            parts.append(f'<text class="small" x="{ox+mx+px+x+5}" y="{oy+my+py+y+16}">{metric.title()}</text>')
        for row_control in (n for n in page.children if n.name.startswith("psf_select_")):
            x,y=point(row_control);rw,rh=size(row_control)
            if y+rh > ph:
                continue
            gid=row_control.name.removeprefix("psf_select_")
            rect(ox+mx+px+x,oy+my+py+y,rw,rh,"#354138","")
            for field,label in (("name",gid),("status","Status")):
                child=children[f"psf_row_{field}_{gid}"];cx,cy=point(child)
                parts.append(f'<text class="small" x="{ox+mx+px+cx+2}" y="{oy+my+py+cy+15}">{html.escape(label[:27])}</text>')
            for metric,label in (("support","Support value"),("influence","Influence value"),("satisfaction","Satisfaction")):
                child=children[f"psf_row_{metric}_{gid}"];cx,cy=point(child);cw,ch=size(child)
                rect(ox+mx+px+cx,oy+my+py+cy,cw,ch,"#304a3b",label,"#456250")
    frontend=gui_nodes((mod / "interface/frontendgamesetupview.gui").read_text(encoding="utf-8-sig"))
    for parent,ox,oy,crop_y in (("gamesetup_interesting_countries_window",24,1450,433),
                                ("gamesetup_country_details",24,1830,0)):
        parts.append(f'<text class="title" x="{ox}" y="{oy-20}">{"Interesting countries: lower information area" if crop_y else "Map selection: selected country"}</text>')
        native=named(frontend,parent);width,height=size(native)
        rect(ox,oy,width,height-crop_y,"#273331","")
        panel=named(frontend,"info",parent);px,py=point(panel);pw,ph=size(panel)
        rect(ox+px,oy+py-crop_y,pw,ph,"#202b29","")
        for field,label in (("leader_label","Leader"),("leader","Selected leader"),
                            ("party_label","Ruling party"),("party","Party / regime / identity art / two pies")):
            child=named(frontend,field,parent);x,y=point(child)
            w=int(child.properties["maxwidth"][2]);h=int(child.properties.get("maxheight",(0,0,"20"))[2])
            rect(ox+px+x,oy+py-crop_y+y,w,h,"#304e40",label)
        if crop_y:
            history=named(frontend,"history",parent);x,y=point(history)
            rect(ox+x,oy+y-crop_y,int(history.properties["maxwidth"][2]),int(history.properties["maxheight"][2]),"#564b32","Original history; separate text and scrollbar")
            portrait=named(frontend,"minor_portrait_overlay",parent);x,y=point(portrait)
            parts.append(f'<text class="small" x="{ox+x}" y="{oy+y-crop_y+16}">Native portrait starts here</text>')
    parts.append('<text class="small" x="550" y="1840">Native textures and font baselines are not reproduced.</text>')
    parts.append('<text class="small" x="550" y="1860">Lobby values share the engine party binding, with separate visual rows.</text>')
    parts.append('<text class="small" x="550" y="1880">Lobby labels use a conservative CJK and wide-Latin width budget.</text>')
    parts.append('</svg>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts), encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod",type=Path)
    parser.add_argument("--svg",type=Path)
    parser.add_argument("--report",type=Path,help="Write the complete per-control report without printing it")
    args=parser.parse_args()
    result=audit(args.mod)
    if args.svg:
        projection(args.mod,args.svg)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    failures = [name for name, passed in result["checks"].items() if not passed]
    print(f"UI audit: {len(result['checks'])} checks, {result['scripted_windows']} windows; "
          f"{len(failures)} failures")
    print(f"Politics bottom {result['political_summary_bottom']} / native management {result['native_management_top']}; "
          f"diplomacy bottom {result['diplomatic_summary_bottom']} / native focus {result['native_focus_top']}")
    for name in failures:
        print("FAIL:",name)
    print(result["limitation"])
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
