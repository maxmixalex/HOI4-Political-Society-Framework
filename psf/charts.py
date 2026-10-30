"""Native scripted-GUI pie data and exact, pre-oriented pixel sectors.

The vanilla political pie is hardwired to engine ideologies.  PSF instead uses
ordinary sprite frames and country arrays, as in the scripted-GUI pie example
by Yard1, with the game's own 63-pixel overlay.  Every interior pixel belongs to
exactly one sector; rotating a thin antialiased wedge would leave visible seams.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import struct

from .palette import color
from .script import Block, addv, block, check, clamp, conditional, divv, mulv, setv

SECTORS = 180
SIZE = 63
INSET = 4
RADIUS = (SIZE - 1) / 2 - INSET


def groups(manifest: dict) -> list[dict]:
    return [g for p in manifest.get("profiles", []) + manifest.get("fallback_profiles", [])
            for g in p.get("groups", [])]


def sector_pixels() -> list[list[tuple[int, int]]]:
    """Partition the inner disk, leaving the native 63-pixel bezel unobstructed."""
    pixels: list[list[tuple[int, int]]] = [[] for _ in range(SECTORS)]
    center = (SIZE - 1) / 2
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - center, y - center
            if dx * dx + dy * dy <= RADIUS * RADIUS:
                angle = (math.atan2(dy, dx) + math.pi / 2) % math.tau
                pixels[min(SECTORS - 1, int(angle / math.tau * SECTORS))].append((x, y))
    return pixels


def geometry() -> list[tuple[int, int, int, int]]:
    # A few angular sectors are narrower than a pixel at the smaller radius.
    # Keep their frame slots as transparent one-pixel strips, preserving the
    # deterministic 180-step allocation without inventing off-circle pixels.
    return [(min(x for x, _ in pixels), min(y for _, y in pixels),
             max(x for x, _ in pixels) - min(x for x, _ in pixels) + 1,
             max(y for _, y in pixels) - min(y for _, y in pixels) + 1) if pixels
            else (SIZE // 2, SIZE // 2, 1, 1)
            for pixels in sector_pixels()]


def artwork(output: Path, organizations: list[dict]) -> list[str]:
    """Write cropped sector strips; frame 1 is the zero-total neutral color."""
    colors = [(74, 79, 73)] + [color(g) for g in organizations]
    sprites = []
    for index, (pixels, (left, top, width, height)) in enumerate(zip(sector_pixels(), geometry())):
        atlas_width = width * len(colors)
        if atlas_width > 16384:
            raise ValueError("PSF pie atlas exceeds 16384 pixels; split this content registry into smaller packs")
        atlas = bytearray(atlas_width * height * 4)
        for frame, rgb in enumerate(colors):
            rgba = bytes((rgb[2], rgb[1], rgb[0], 255))
            for x, y in pixels:
                offset = ((y - top) * atlas_width + frame * width + x - left) * 4
                atlas[offset:offset + 4] = rgba
        relative = f"gfx/interface/psf/pie/sector_{index:03}.tga"
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
                             atlas_width, height, 32, 0x28)
        path.write_bytes(header + atlas)
        sprites.append(f'spriteType = {{ name = "GFX_psf_pie_sector_{index:03}" '
                       f'texturefile = "{relative}" noOfFrames = {len(colors)} }}')
    # Always emit a separate identity key, including when the author supplies
    # custom icons whose artwork does not contain the organization's color.
    for organization, rgb in zip(organizations, colors[1:]):
        relative = f"gfx/interface/psf/colors/{organization['id']}.tga"
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, 8, 8, 32, 0x28)
        path.write_bytes(header + bytes((rgb[2], rgb[1], rgb[0], 255)) * 64)
        sprites.append(f'spriteType = {{ name = "GFX_psf_color_{organization["id"]}" '
                       f'texturefile = "{relative}" noOfFrames = 1 }}')
    return sprites


def bookmark_values(manifest: dict, profile: dict, date: str) -> dict:
    """Resolve a bookmark once for both compact native text and optional artwork."""
    organizations = copy.deepcopy(profile["groups"])
    by_id = {g["id"]: g for g in organizations}
    start = tuple(map(int, date.split(".")))
    for override in sorted(profile.get("start_overrides", []), key=lambda item: tuple(map(int, item["date"].split(".")))):
        if tuple(map(int, override["date"].split("."))) <= start:
            for item in override.get("groups", []):
                for field in ("support", "influence", "status"):
                    if field in item:
                        by_id[item["id"]][field] = item[field]
    settings = manifest.get("settings", {})
    shares, totals, weights = {}, {}, {}
    for metric in ("support", "influence"):
        values = []
        for g in organizations:
            status = g.get("status", "legal")
            value = float(g.get(metric, 0)) if status != "inactive" else 0
            if metric == "support" and not g.get("electoral", g.get("kind", "party") == "party"):
                value = 0
            if metric == "influence":
                if status == "underground":
                    value *= settings.get("underground_influence_factor", .35)
                elif status == "banned":
                    value *= settings.get("banned_influence_factor", .12)
            values.append(max(0, min(100, value)))
        # Built-in sum(float) changed in Python 3.12. Keep report hashes and
        # snapshot boundaries identical on every supported Python version.
        total = math.fsum(values)
        totals[metric] = total
        weights[metric] = values
        shares[metric] = {g["id"]: value * 100 / total if total else 0
                          for g, value in zip(organizations, values)}
    return {"organizations": organizations, "weights": weights, "totals": totals, **shares}


def bookmark_artwork(manifest: dict, profile: dict, date: str, output: Path) -> dict:
    """Build a 140×63 dual pie for the reserved frontend political image area.

    The country history textbox never receives this image. ``frontend`` owns
    its independently bounded native party presentation and image spacing.
    """
    snapshot = bookmark_values(manifest, profile, date)
    colors = []
    for metric in ("support", "influence"):
        total = snapshot["totals"][metric]
        segments = [(74, 79, 73)] * SECTORS
        cumulative, begin = 0.0, 0
        if total:
            for g, value in zip(snapshot["organizations"], snapshot["weights"][metric]):
                cumulative += value
                end = min(SECTORS, int(cumulative * SECTORS / total + .5))
                segments[begin:end] = [color(g)] * (end - begin)
                begin = end
        colors.append(segments)
    width = SIZE * 2 + 14
    image = bytearray(width * SIZE * 4)
    for metric_index, palette in enumerate(colors):
        offset_x = metric_index * (SIZE + 14)
        for index, pixels in enumerate(sector_pixels()):
            r, g, b = palette[index]
            for x, y in pixels:
                position = (y * width + x + offset_x) * 4
                image[position:position + 4] = bytes((b, g, r, 255))
    stem = f"psf_bookmark_{profile['id']}_{date.replace('.', '_')}"
    relative = f"gfx/interface/psf/bookmarks/{stem}.tga"
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, SIZE, 32, 0x28)
    target.write_bytes(header + image)
    return {"sprite": "GFX_" + stem, "texture": relative,
            "width": width, "height": SIZE,
            "support": snapshot["support"], "influence": snapshot["influence"]}


def refresh_effect(manifest: dict, profile: dict) -> Block:
    """Cache both pies after runtime modifier and status calculations.

    Rounded cumulative boundaries allocate a complete circle without rounding
    each party independently.  Zero totals retain a neutral disk; civil groups
    are never counted as additional election votes in the support pie.
    """
    frames = {g["id"]: i + 2 for i, g in enumerate(groups(manifest))}
    body: list[Block | str] = []
    for metric in ("support", "influence"):
        array = f"psf_pie_{metric}_frames"
        total = f"psf_pie_{metric}_total"
        field = "modified_support" if metric == "support" else "effective_influence"
        candidates = [g for g in profile["groups"]
                      if metric == "influence" or g.get("electoral", g.get("kind", "party") == "party")]
        body += [f"clear_array = {array}",
                 f"resize_array = {{ array = {array} size = {SECTORS} value = 1 }}",
                 setv(total, 0)]
        for g in profile["groups"]:
            body.append(setv(f"psf_g_{g['id']}_{metric}_share", 0))
        for g in candidates:
            body.append(conditional([check(f"psf_g_{g['id']}_status", 0, "greater_than")],
                                    addv(total, f"psf_g_{g['id']}_{field}")))
        allocation: list[Block | str] = [setv("psf_pie_start", 0, True),
                                        setv("psf_pie_cumulative", 0, True)]
        for g in candidates:
            share = f"psf_g_{g['id']}_{metric}_share"
            allocation.append(conditional([check(f"psf_g_{g['id']}_status", 0, "greater_than")],
                setv(share, f"psf_g_{g['id']}_{field}"), mulv(share, 100), divv(share, total),
                addv("psf_pie_cumulative", f"psf_g_{g['id']}_{field}", True),
                setv("psf_pie_end", "psf_pie_cumulative", True), mulv("psf_pie_end", SECTORS, True),
                divv("psf_pie_end", total, True),
                "round_temp_variable = psf_pie_end", clamp("psf_pie_end", 0, SECTORS, True),
                block("for_loop_effect", "start = psf_pie_start", "end = psf_pie_end",
                      "value = psf_pie_slot", f"set_variable = {{ {array}^psf_pie_slot = {frames[g['id']]} }}"),
                setv("psf_pie_start", "psf_pie_end", True)))
        body.append(conditional([check(total, 0, "greater_than")], allocation))
    return block("psf_update_charts_" + profile["id"], body)
