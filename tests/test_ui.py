"""Regression tests for engine widget contracts and foreign-country UI isolation."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import struct
import tempfile
import unittest

from psf.ui import ASSETS, generate_ui, gui_nodes, patch_native
from psf import charts


def fixture():
    return {
        "axes": [{"id": "economy", "name": {"english": "Economy"},
                  "left": {"english": "Public"}, "right": {"english": "Private"}}],
        "ideologies": [{"id": "liberal", "_index": 88412}],
        "regimes": [{"id": "republic", "_index": 3389}],
        "profiles": [{"id": "test", "tag": "GER", "groups": [
            {"id": "alpha", "_index": 90117, "kind": "party", "positions": {"economy": 0}},
            {"id": "beta", "_index": 3074, "kind": "trade_union", "positions": {"economy": 0},
             "small_icon": "GFX_custom_beta_small", "large_icon": "GFX_custom_beta_large"}
        ], "alliances": [{"id": "cabinet", "_index": 9753, "members": ["alpha"]}]}],
        "fallback_profiles": []
    }


class UIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.metadata = generate_ui(fixture(), cls.root)
        cls.script = "\n".join(p.read_text() for p in sorted((cls.root / "common/scripted_guis").glob("psf_society*.txt")))
        cls.gui = "\n".join(p.read_text(encoding="utf-8") for p in sorted((cls.root / "interface").glob("psf_society*.gui")))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_widget_identities_and_ancestries_survive(self):
        """Engine child lookups must keep working after replacing the pie area."""
        for source in ASSETS.glob("*.gui"):
            before = gui_nodes(source.read_text(encoding="utf-8-sig"))
            after = gui_nodes((self.root / "interface" / source.name).read_text(encoding="utf-8-sig"))
            identities = {(node.kind.lower(), node.ancestry, node.name) for node in after if node.name}
            for node in before:
                if node.name:
                    self.assertIn((node.kind.lower(), node.ancestry, node.name), identities)

    def test_hidden_politics_do_not_move_faction_and_balance_controls(self):
        data = (self.root / "interface/countrypoliticsview.gui").read_text(encoding="utf-8-sig")
        nodes = gui_nodes(data)
        names = {node.name: node for node in nodes if node.name in ("ruling_party_info", "political_pie_chart", "chart_explanation", "power_balance_button")}
        for name in ("political_pie_chart", "chart_explanation"):
            position = next(n for n in names[name].children if n.kind == "position")
            self.assertIn("-12000", data[position.start:position.end])
        ruling_position = next(n for n in names["ruling_party_info"].children if n.kind == "position")
        self.assertNotIn("-12000", data[ruling_position.start:ruling_position.end])
        self.assertIn('name = "open_faction_button"', data)
        self.assertIn('name = "show_power_balance"', data)

    def test_pregame_both_detail_panels_are_replaced(self):
        data = (self.root / "interface/frontendgamesetupview.gui").read_text(encoding="utf-8-sig")
        nodes = gui_nodes(data)
        for n in nodes:
            if n.name in ("ideology", "party") and "info" in n.ancestry:
                position = next(child for child in n.children if child.kind == "position")
                self.assertIn("-12000", data[position.start:position.end])
        self.assertIn("psf_interesting_pregame_explanation", data)
        self.assertIn("psf_pregame_explanation", data)

    def test_native_tree_change_requires_explicit_update(self):
        with tempfile.TemporaryDirectory() as folder:
            altered = Path(folder) / "source"
            shutil.copytree(ASSETS, altered)
            path = altered / "countrypoliticsview.gui"
            path.write_text(path.read_text().replace('name = "political_pie_chart"', 'name = "renamed_by_engine"'))
            with self.assertRaisesRegex(ValueError, "expected one"):
                patch_native(altered, Path(folder) / "output")

    def test_foreign_browsing_never_writes_foreign_selection(self):
        self.assertNotRegex(self.script, r"set_variable\s*=\s*\{\s*psf_ui_")
        self.assertIn("ROOT.psf_ui_group = 90117", self.script)
        self.assertIn("ROOT.psf_ui_group = 3074", self.script)
        # Both political and diplomacy contexts enforce the same target guard
        # in the effect, so even a scripted click cannot evade a disabled button.
        for action in ("ban", "legalize", "activate"):
            for gid in ("alpha", "beta"):
                lines = [line for line in self.script.splitlines() if line.startswith(f"psf_{action}_{gid}_click =")]
                self.assertEqual(len(lines), 2)
                for line in lines:
                    self.assertIn("limit = { tag = ROOT", line)
                    self.assertIn("has_political_power >", line)
                    self.assertIn(f"psf_{action}_{gid} = yes", line)
                    self.assertIn("add_political_power = -", line)

    def test_identity_checks_are_exact_not_implicit_greater_equal(self):
        files = list((self.root / "common").rglob("*.txt"))
        combined = "\n".join(p.read_text() for p in files)
        self.assertNotRegex(combined, r"check_variable\s*=\s*\{\s*(?!var\b)[\w.]+\s*=\s*[-\d.]+\s*\}")
        self.assertIn("var = ROOT.psf_ui_group value = 90117 compare = equals", combined)
        self.assertIn("var = psf_regime value = 3389 compare = equals", combined)
        self.assertIn("var = psf_governing_alliance value = 9753 compare = equals", combined)

    def test_live_axes_and_colliding_positions_remain_clickable(self):
        self.assertIn("x = psf_g_alpha_modified_position_economy", self.script)
        self.assertIn("x = psf_g_beta_modified_position_economy", self.script)
        nodes = {n.name: n for n in gui_nodes(self.gui) if n.name}
        first = nodes["psf_axis_marker_alpha_economy"]
        second = nodes["psf_axis_marker_beta_economy"]
        p1 = next(n for n in first.children if n.kind == "position")
        p2 = next(n for n in second.children if n.kind == "position")
        self.assertNotEqual(p1.properties["y"][2], p2.properties["y"][2])
        self.assertIn("psf_ui_selection_is_current = yes", self.script)

    def test_supplied_icon_overrides_are_used_and_default_art_is_valid(self):
        self.assertRegex(self.gui, r'spriteType\s*=\s*"GFX_custom_beta_large"')
        self.assertRegex(self.gui, r'spriteType\s*=\s*"GFX_custom_beta_small"')
        for suffix, size in (("small", 24), ("large", 64)):
            payload = (self.root / f"gfx/interface/psf/alpha_{suffix}.tga").read_bytes()
            self.assertEqual(struct.unpack_from("<HH", payload, 12), (size, size))
            self.assertEqual(len(payload), 18 + size * size * 4)

    def test_compact_summary_and_scroll_layout_bounds(self):
        from tools.ui.audit_layout import audit
        result = audit(self.root)
        self.assertTrue(result["passed"], result["checks"])
        self.assertLessEqual(result["political_summary_bottom"], result["native_management_top"])
        self.assertLessEqual(result["diplomatic_summary_bottom"], result["native_focus_top"])

    def test_bilingual_localization_and_suppression_display(self):
        keys = []
        for language in ("english", "simp_chinese"):
            payload = (self.root / f"localisation/{language}/psf_ui_l_{language}.yml").read_bytes()
            self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
            text = payload.decode("utf-8-sig")
            keys.append(set(re.findall(r"^ (psf_\w+):", text, re.M)))
            self.assertIn("psf_g_alpha_effective_influence", text)
            self.assertIn("psf_g_alpha_influence", text)
        self.assertEqual(keys[0], keys[1])

    def test_interface_bytes_and_root_keywords_are_engine_safe(self):
        for path in (self.root / "interface").iterdir():
            data = path.read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), path.name)
            expected = b"guiTypes" if path.suffix == ".gui" else b"spriteTypes"
            self.assertTrue(data.lstrip().startswith(expected), path.name)

    def test_scripted_contexts_own_distinct_windows_and_use_nested_mount_instances(self):
        windows = re.findall(r"^window_name = (\w+)$", self.script, re.M)
        self.assertEqual(len(windows), len(set(windows)))
        for mode in ("political", "diplomatic"):
            for view in ("summary", "side"):
                self.assertIn(f"parent_window_name = psf_{mode}_{view}_mount_instance", self.script)

    def test_both_native_summaries_contain_two_complete_live_pies(self):
        nodes = gui_nodes(self.gui)
        for mode in ("political", "diplomatic"):
            for metric in ("support", "influence"):
                parent = f"psf_{mode}_{metric}_pie"
                sectors = [n for n in nodes if parent in n.ancestry and n.name.startswith(f"psf_pie_{metric}_")]
                self.assertEqual(len(sectors), charts.SECTORS)
                hitbox = next(n for n in nodes if parent in n.ancestry and n.name == f"psf_open_{metric}")
                self.assertEqual(hitbox.properties["pdx_tooltip"][2], f'"psf_ui_{metric}_chart_tip"')
                self.assertIn("GFX_pol_piechart_overlay_63x63", hitbox.properties["quadtexturesprite"][2])
        self.assertIn("frame = psf_pie_support_frames^179", self.script)
        self.assertIn("frame = psf_pie_influence_frames^179", self.script)

    def test_pie_pixels_cover_the_disk_once_without_rotated_sector_seams(self):
        occupied = set()
        center = (charts.SIZE - 1) / 2
        for pixels in charts.sector_pixels():
            self.assertTrue(pixels)
            self.assertFalse(occupied.intersection(pixels))
            occupied.update(pixels)
        expected = {(x, y) for x in range(charts.SIZE) for y in range(charts.SIZE)
                    if (x - center) ** 2 + (y - center) ** 2 <= center ** 2}
        self.assertEqual(occupied, expected)
        self.assertNotIn("rotation =", self.gui)

    def test_compact_organization_rows_use_original_game_chrome(self):
        nodes = gui_nodes(self.gui)
        row = next(n for n in nodes if n.name == "psf_select_alpha")
        self.assertEqual(row.properties["quadtexturesprite"][2], '"GFX_tiled_button"')
        row_size = next(n for n in row.children if n.kind.lower() == "size")
        self.assertEqual(row_size.properties["y"][2], "44")
        self.assertFalse((self.root / "gfx/interface/psf/group_row.tga").exists())


if __name__ == "__main__":
    unittest.main()
