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
from hoi4_interpreter import Interpreter, State, entries, mapping, parse


def fixture():
    return {
        "axes": [{"id": "economy", "name": {"english": "Economy"},
                  "left": {"english": "Public"}, "right": {"english": "Private"}}],
        "ideologies": [{"id": "liberal", "_index": 88412}],
        "regimes": [{"id": "republic", "_index": 3389}],
        "profiles": [{"id": "test", "tag": "GER", "groups": [
            {"id": "alpha", "_index": 90117, "kind": "party", "color": "#1234AB", "positions": {"economy": 0}},
            {"id": "beta", "_index": 3074, "kind": "trade_union", "positions": {"economy": 0},
             "small_icon": "GFX_custom_beta_small", "large_icon": "GFX_custom_beta_large"}
        ], "alliances": [{"id": "cabinet", "_index": 9753, "members": ["alpha"]}]}],
        "fallback_profiles": [{"id": "other", "groups": [{"id": "gamma", "_index": 222, "kind": "party", "positions": {"economy": 10}}], "alliances": []}]
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
        self.assertIn("x = psf_g_alpha_ui_position_economy", self.script)
        self.assertIn("x = psf_g_beta_ui_position_economy", self.script)
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

    def test_scripted_contexts_use_native_tokens_and_independent_page_windows(self):
        windows = re.findall(r"^window_name = (\w+)$", self.script, re.M)
        self.assertEqual(len(windows), len(set(windows)))
        self.assertNotIn("parent_window_name =", self.script)
        self.assertIn("parent_window_token = politics_tab", self.script)
        self.assertIn("parent_window_token = selected_country_view_diplomacy", self.script)
        from tools.ui.audit_layout import script_bindings
        bindings = script_bindings(self.root)
        nodes = {n.name: n for n in gui_nodes(self.gui) if n.name and n.kind == "containerWindowType"}
        for mode in ("political", "diplomatic"):
            for page in ("groups_test", "detail_alpha", "detail_beta", "spectrum_test", "alliances_test"):
                name = f"psf_{mode}_{page}"
                self.assertEqual(nodes[name].parent.kind, "guiTypes")
                self.assertEqual(bindings[name].properties["parent_scripted_gui"][2], f"psf_{mode}_society_side_gui")
                self.assertNotIn("dirty", bindings[name].properties)
                self.assertTrue(any(n.kind == "visible" for n in bindings[name].children))

    def test_both_native_summaries_contain_two_complete_live_pies(self):
        nodes = gui_nodes(self.gui)
        for mode in ("political", "diplomatic"):
            parent = next(n for n in nodes if n.name == f"psf_{mode}_summary")
            for metric in ("support", "influence"):
                sectors = [n for n in parent.children if n.name.startswith(f"psf_pie_{metric}_")]
                self.assertEqual(len(sectors), charts.SECTORS)
                hitbox = next(n for n in parent.children if n.name == f"psf_open_{metric}")
                self.assertEqual(hitbox.properties["pdx_tooltip"][2], f'"psf_ui_{metric}_chart_tip"')
                self.assertIn("GFX_pol_piechart_overlay_63x63", hitbox.properties["quadtexturesprite"][2])
        self.assertIn("frame = psf_pie_support_frames^179", self.script)
        self.assertIn("frame = psf_pie_influence_frames^179", self.script)

    def test_rendered_page_visibility_is_exclusive_through_navigation_and_country_changes(self):
        scripts = [entry for root in entries(parse(self.script)) for entry in entries(root.value)]
        vm = Interpreter(State())
        for node in entries(parse((self.root / "common/scripted_triggers/psf_ui.txt").read_text())):
            vm.triggers[node.key] = node.value
        vm.state.flags.update(("psf_initialized", "psf_profile_test"))
        vm.state.variables.update(psf_ui_open=1, psf_ui_page=0, psf_ui_group=0)

        def shown(mode):
            return [node.key for node in scripts
                    if node.key.startswith(f"psf_{mode}_")
                    and "parent_scripted_gui" in mapping(node.value)
                    and vm.condition(mapping(node.value)["visible"])]

        for mode in ("political", "diplomatic"):
            for page, group, expected in ((0, 0, "groups_test"), (1, 90117, "detail_alpha"),
                                          (1, 3074, "detail_beta"), (2, 3074, "spectrum_test"),
                                          (3, 3074, "alliances_test"), (1, 99999, "groups_test")):
                vm.state.variables.update(psf_ui_page=page, psf_ui_group=group)
                self.assertEqual(shown(mode), [f"psf_{mode}_{expected}_gui"])
            vm.state.variables["psf_ui_open"] = 0
            self.assertEqual(shown(mode), [])
            vm.state.variables.update(psf_ui_open=1, psf_ui_page=1, psf_ui_group=90117)
            vm.state.flags.remove("psf_profile_test")
            vm.state.flags.add("psf_profile_other")
            self.assertEqual(shown(mode), [f"psf_{mode}_groups_other_gui"])
            vm.state.flags.remove("psf_profile_other")
            vm.state.flags.add("psf_profile_test")

    def test_localized_control_keys_have_real_translation_wrappers(self):
        texts = [(self.root / f"localisation/{lang}/psf_ui_l_{lang}.yml").read_text(encoding="utf-8-sig")
                 for lang in ("english", "simp_chinese")]
        keys = [set(re.findall(r"^ (psf_ui_\w+):", text, re.M)) for text in texts]
        for node in gui_nodes(self.gui):
            for prop in ("text", "buttontext", "pdx_tooltip"):
                value = node.properties.get(prop, (0, 0, ""))[2].strip('"')
                if value.startswith("psf_ui_"):
                    for language_keys in keys:
                        self.assertIn(value, language_keys)
                self.assertFalse(value.startswith("PSFUI"), "A scripted-localisation function is not a localisation key")
        for text in texts:
            self.assertRegex(text, r'psf_ui_regime_line:0 "\[PSFUIRegime\]"')
            self.assertRegex(text, r'psf_ui_row_status_alpha:0 "\[PSFUIRowStatus_alpha\]"')

    def test_dynamic_tooltips_contain_resolved_static_labels_and_live_values(self):
        for language in ("english", "simp_chinese"):
            text = (self.root / f"localisation/{language}/psf_ui_l_{language}.yml").read_text(encoding="utf-8-sig")
            self.assertIsNone(re.search(r"\$psf_[A-Za-z0-9_]+\$", text))
            tooltip = next(line for line in text.splitlines() if line.startswith(" psf_ui_group_tooltip_alpha:"))
            self.assertIn("alpha", tooltip)
            self.assertIn("[PSFUIStatus_alpha]", tooltip)
            self.assertIn("[?psf_g_alpha_modified_support|1]", tooltip)
            self.assertIn("[?psf_g_alpha_effective_influence|1]", tooltip)

    def test_unknown_static_localization_reference_fails_the_build(self):
        content = fixture()
        content["profiles"][0]["groups"][0]["description"] = {"english": "$psf_missing_name$"}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "Unknown UI localisation reference"):
                generate_ui(content, Path(folder))

    def test_authored_color_reaches_default_badge_and_custom_icon_swatch(self):
        color = (0x12, 0x34, 0xAB)
        payload = (self.root / "gfx/interface/psf/alpha_small.tga").read_bytes()[18:]
        pixels = [tuple(payload[i:i+4]) for i in range(0, len(payload), 4)]
        self.assertIn((color[2], color[1], color[0], 255), pixels)
        for mode in ("political", "diplomatic"):
            for view, label in (("groups_test", "row"), ("detail_beta", "detail")):
                window = next(n for n in gui_nodes(self.gui) if n.name == f"psf_{mode}_{view}")
                swatch = next(n for n in window.children if n.name == f"psf_{label}_color_beta")
                self.assertEqual(swatch.properties["spritetype"][2], '"GFX_psf_color_beta"')

    def test_row_text_cells_and_detail_blocks_do_not_overlap(self):
        from tools.ui.audit_layout import point
        for mode in ("political", "diplomatic"):
            nodes = gui_nodes(self.gui)
            window = next(n for n in nodes if n.name == f"psf_{mode}_groups_test")
            children = {n.name: n for n in window.children if n.name}
            title, values, status = (children[f"psf_row_{kind}_alpha"] for kind in ("name", "values", "status"))
            self.assertLessEqual(point(title)[1] + int(title.properties["maxheight"][2]), point(values)[1])
            self.assertLessEqual(point(values)[0] + int(values.properties["maxwidth"][2]), point(status)[0])
            detail = next(n for n in nodes if n.name == f"psf_{mode}_detail_alpha")
            texts = [n for n in detail.children if n.kind == "instantTextboxType"]
            for first, second in zip(texts, texts[1:]):
                self.assertLessEqual(point(first)[1] + int(first.properties["maxheight"][2]), point(second)[1])
            description = next(n for n in texts if n.name == "psf_detail_description_alpha")
            self.assertEqual(description.properties["scrollbartype"][2], '"standardtext_slider"')

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
