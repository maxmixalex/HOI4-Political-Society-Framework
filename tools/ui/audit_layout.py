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


def audit(mod: Path) -> dict:
    politics = gui_nodes((mod / "interface/countrypoliticsview.gui").read_text(encoding="utf-8-sig"))
    diplomacy = gui_nodes((mod / "interface/countrydiplomacyview.gui").read_text(encoding="utf-8-sig"))
    society = society_nodes(mod)
    pol_mount = named(politics, "psf_political_summary_mount")
    pol_summary = named(society, "psf_political_summary")
    pol_bottom = point(pol_mount)[1] + size(pol_summary)[1]
    native_bottom_start = point(named(politics, "politics_bottom"))[1]
    dip_mount = named(diplomacy, "psf_diplomatic_summary_mount")
    dip_summary = named(society, "psf_diplomatic_summary")
    dip_bottom = point(dip_mount)[1] + size(dip_summary)[1]
    focus_start = point(named(diplomacy, "active_national_focus_info", "diplomacy_tab_top"))[1]
    checks = {
        "political_summary_precedes_native_management_strip": pol_bottom <= native_bottom_start,
        "diplomatic_summary_precedes_native_focus": dip_bottom <= focus_start,
    }
    for mode, nodes in (("political", politics), ("diplomatic", diplomacy)):
        checks[mode + "_sidebar_outside_native_panel"] = point(named(nodes, f"psf_{mode}_side_mount"))[0] >= 550
        summary = named(society, f"psf_{mode}_summary")
        width, height = size(summary)
        for child in summary.children:
            x, y = point(child)
            if child.kind.lower() == "instanttextboxtype":
                w = int(child.properties["maxwidth"][2])
                h = int(child.properties["maxheight"][2])
                checks[child.name + "_in_summary"] = 0 <= x and 0 <= y and x + w <= width and y + h <= height
            elif child.kind.lower() == "buttontype":
                w, h = size(child) if any(n.kind.lower() == "size" for n in child.children) else (123, 34)
                checks[mode + child.name + "_in_summary"] = x + w <= width and y + h <= height
            elif child.kind.lower() == "containerwindowtype":
                w, h = size(child)
                checks[child.name + "_in_summary"] = 0 <= x and 0 <= y and x + w <= width and y + h <= height
    sidebar = named(society, "psf_society_side")
    sw, sh = size(sidebar)
    for page in ("psf_groups_page", "psf_detail_page", "psf_spectrum_page", "psf_alliances_page"):
        node = named(society, page, "psf_society_side")
        x, y = point(node)
        w, h = size(node)
        checks[page + "_viewport_inside_sidebar"] = x + w <= sw and y + h <= sh
        checks[page + "_has_native_scrollbar"] = node.properties.get("verticalscrollbar", (0, 0, ""))[2] == '"right_vertical_slider"'
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
        "sidebar_logical_size": [sw, sh],
        "limitation": "Geometric audit only. Engine rendering, native fonts and input are not executed.",
    }


def projection(mod: Path, destination: Path) -> None:
    society = society_nodes(mod)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="1410" viewBox="0 0 1040 1410">',
             '<style>text{font-family:Arial,sans-serif;font-size:14px;fill:#e8e8e0}.small{font-size:11px;fill:#b8c5c5}.title{font-size:20px;font-weight:bold}</style>',
             '<rect width="1040" height="1410" fill="#171e22"/>',
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
            sx, sy = point(named(native, "psf_political_summary_mount"))
        else:
            rect(ox+13, oy+160, 125, 138, "#303b3e", "Native leader")
            rect(ox+144, oy+248, 376, 76, "#564b32", "Existing national focus")
            sx, sy = point(named(native, "psf_diplomatic_summary_mount"))
            # The mount is inside diplomacy_tab_top inside country_info.
            sy += point(named(native, "diplomacy_tab_top"))[1] + point(named(native, "country_info"))[1]
        summary = named(society, f"psf_{mode}_summary")
        w, h = size(summary)
        rect(ox+sx, oy+sy, w, h, "#273e34", "")
        labels = {"regime": "Actual regime", "government": "Governing alliance", "metrics": "Support / effective influence", "legitimacy": "Legitimacy / active groups"}
        for child in summary.children:
            x, y = point(child)
            if child.kind.lower() == "instanttextboxtype":
                width = int(child.properties["maxwidth"][2]);height = int(child.properties["maxheight"][2])
                label = next((v for k, v in labels.items() if child.name.endswith("_"+k)), child.name)
                rect(ox+sx+x, oy+sy+y, width, height, "#304e40", label, "#456250")
            elif child.kind.lower() == "buttontype":
                rect(ox+sx+x, oy+sy+y, 123, 34, "#5b5b43", "Groups" if child.name.endswith("groups") else "Spectrum")
        mx, my = point(named(native, f"psf_{mode}_side_mount"))
        side_name = "psf_society_side" if mode == "political" else "psf_society_side_diplomatic"
        side = named(society, side_name)
        sw, sh = size(side)
        rect(ox+mx, oy+my, sw, sh, "#273331", "Optional sidebar; opens on request")
        for name in ("psf_tab_groups", "psf_tab_spectrum", "psf_tab_alliances"):
            n=named(society,name,side_name);x,y=point(n)
            rect(ox+mx+x,oy+my+y,123,34,"#5b5b43",name.removeprefix("psf_tab_").title())
        page=named(society,"psf_groups_page",side_name);px,py=point(page);pw,ph=size(page)
        rect(ox+mx+px,oy+my+py,pw,ph,"#202b29","Native scroll viewport; one page visible")
        rect(ox+mx+px+pw-15,oy+my+py+24,10,ph-30,"#44524a","")
        rect(ox+mx+px+pw-15,oy+my+py+24,10,115,"#b4b29a","")
        for idx in range(9):
            y=oy+my+py+28+idx*46
            rect(ox+mx+px+8,y,370,44,"#354138",f"Group {idx+1}: name, support / influence / satisfaction")
    parts.append('</svg>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts), encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod",type=Path)
    parser.add_argument("--svg",type=Path)
    args=parser.parse_args()
    result=audit(args.mod)
    if args.svg:
        projection(args.mod,args.svg)
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
