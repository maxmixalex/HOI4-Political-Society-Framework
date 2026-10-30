"""Regression tests for engine widget contracts and foreign-country UI isolation."""
from __future__ import annotations

import json
from itertools import combinations
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
        "settings": {"mechanics_mode": "strict"},
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

    def test_pregame_both_detail_panels_retain_native_party_binding(self):
        data = (self.root / "interface/frontendgamesetupview.gui").read_text(encoding="utf-8-sig")
        nodes = gui_nodes(data)
        for n in nodes:
            if n.name in ("ideology", "government") and "info" in n.ancestry:
                position = next(child for child in n.children if child.kind == "position")
                self.assertIn("-12000", data[position.start:position.end])
        for parent in ("gamesetup_country_details", "gamesetup_interesting_countries_window"):
            party = next(n for n in nodes if n.name == "party" and parent in n.ancestry)
            # These engine-owned fields have no static text key; the game
            # supplies the selected country's party name via their identity.
            self.assertNotIn("text", party.properties)
            self.assertNotEqual(party.properties.get("hide", (0, 0, "no"))[2], "yes")
            self.assertEqual(party.properties["multiline"][2], "yes")
            info = next(n for n in nodes if n.name == "info" and parent in n.ancestry)
            self.assertEqual(info.properties["clipping"][2], "yes")
            self.assertEqual(sum(n.kind.lower() == "size" for n in info.children), 1)
        self.assertNotIn("psf_pregame_explanation", data)
        self.assertNotIn("psf_interesting_pregame_explanation", data)

    def test_compat_without_history_binding_keeps_the_entire_native_frontend(self):
        original = (ASSETS / "frontendgamesetupview.gui").read_text(encoding="utf-8-sig")
        for settings in ({}, {"mechanics_mode": "compat"}):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as folder:
                manifest = fixture()
                manifest["settings"] = settings
                metadata = generate_ui(manifest, Path(folder))
                generated = (Path(folder) / "interface/frontendgamesetupview.gui").read_text(encoding="utf-8-sig")
                self.assertEqual(generated, original)
                self.assertFalse(metadata["frontend_adapter"])
                self.assertNotIn("psf_pregame_explanation", generated)
                self.assertNotIn("psf_interesting_pregame_explanation", generated)

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
        self.assertIn("x = ROOT.psf_g_alpha_ui_position_economy", self.script)
        self.assertIn("x = THIS.psf_g_beta_ui_position_economy", self.script)
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
        identity = (self.root / "interface/psf_identity_icons.gfx").read_text()
        for suffix in ("small", "large"):
            self.assertIn(f'"GFX_psf_group_alpha_{suffix}"', identity)
            self.assertFalse((self.root / f"gfx/interface/psf/alpha_{suffix}.tga").exists())
        self.assertIn("gfx/interface/ideologies/neutrality_group.dds", identity)
        self.assertNotIn('name = "GFX_custom_beta_large"', identity)

    def test_native_and_custom_icons_fit_reserved_lanes(self):
        from tools.ui.audit_layout import point, size
        nodes = gui_nodes(self.gui)
        for mode in ("political", "diplomatic"):
            spectrum = next(n for n in nodes if n.name == f"psf_{mode}_spectrum_test")
            markers = {n.name: n for n in spectrum.children if n.name.startswith("psf_axis_marker_")}
            self.assertAlmostEqual(float(markers["psf_axis_marker_alpha_economy"].properties["scale"][2]) * 20, 16)
            self.assertAlmostEqual(float(markers["psf_axis_marker_beta_economy"].properties["scale"][2]) * 24, 16, places=4)
            for gid in ("alpha", "beta"):
                detail = next(n for n in nodes if n.name == f"psf_{mode}_detail_{gid}")
                frame = next(n for n in detail.children if n.name == f"psf_detail_icon_frame_{gid}")
                status = next(n for n in detail.children if n.name == f"psf_detail_status_{gid}")
                name = next(n for n in detail.children if n.name == f"psf_detail_name_{gid}")
                self.assertEqual(frame.properties["clipping"][2], "yes")
                self.assertGreaterEqual(size(frame)[0], 60)
                self.assertGreaterEqual(size(frame)[1], 68)
                self.assertLessEqual(point(frame)[0] + size(frame)[0], point(name)[0])
                self.assertLessEqual(point(frame)[1] + size(frame)[1], point(status)[1])

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
                self.assertEqual(hitbox.properties["pdx_tooltip"][2], f'"psf_ui_{mode}_{metric}_chart_tip"')
                self.assertIn("GFX_pol_piechart_overlay_63x63", hitbox.properties["quadtexturesprite"][2])
        self.assertIn("frame = ROOT.psf_pie_support_frames^179", self.script)
        self.assertIn("frame = THIS.psf_pie_influence_frames^179", self.script)

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

    def test_selected_tab_and_regular_tab_are_mutually_exclusive(self):
        scripts = [entry for root in entries(parse(self.script)) for entry in entries(root.value)]
        vm = Interpreter(State())
        for mode in ("political", "diplomatic"):
            root = next(n for n in scripts if n.key == f"psf_{mode}_society_side_gui")
            triggers = mapping(mapping(root.value)["triggers"])
            for page in range(4):
                vm.state.variables["psf_ui_page"] = page
                for tab, expected in (("groups", page < 2), ("spectrum", page == 2), ("alliances", page == 3)):
                    normal = vm.condition(triggers[f"psf_tab_{tab}_visible"])
                    selected = vm.condition(triggers[f"psf_tab_{tab}_selected_visible"])
                    self.assertNotEqual(normal, selected)
                    self.assertEqual(selected, expected)

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

    def test_authored_color_stays_in_swatches_with_native_or_custom_icons(self):
        color = (0x12, 0x34, 0xAB)
        payload = (self.root / "gfx/interface/psf/colors/alpha.tga").read_bytes()[18:]
        pixels = [tuple(payload[i:i+4]) for i in range(0, len(payload), 4)]
        self.assertIn((color[2], color[1], color[0], 255), pixels)
        for mode in ("political", "diplomatic"):
            for view, label in (("groups_test", "row"), ("detail_beta", "detail")):
                window = next(n for n in gui_nodes(self.gui) if n.name == f"psf_{mode}_{view}")
                swatch = next(n for n in window.children if n.name == f"psf_{label}_color_beta")
                self.assertEqual(swatch.properties["spritetype"][2], '"GFX_psf_color_beta"')

    def test_row_text_cells_and_detail_blocks_do_not_overlap(self):
        from tools.ui.audit_layout import point, size
        for mode in ("political", "diplomatic"):
            nodes = gui_nodes(self.gui)
            window = next(n for n in nodes if n.name == f"psf_{mode}_groups_test")
            children = {n.name: n for n in window.children if n.name}
            title, status = (children[f"psf_row_{kind}_alpha"] for kind in ("name", "status"))
            self.assertLessEqual(point(title)[0] + int(title.properties["maxwidth"][2]), point(status)[0])
            values = [children[f"psf_row_{metric}_alpha"] for metric in ("support", "influence", "satisfaction")]
            for value, metric in zip(values, ("support", "influence", "satisfaction")):
                heading = children[f"psf_list_{metric}"]
                self.assertLessEqual(point(title)[1] + int(title.properties["maxheight"][2]), point(value)[1])
                self.assertEqual(point(value)[0], point(heading)[0])
                self.assertEqual(size(value)[0], int(heading.properties["maxwidth"][2]))
                self.assertEqual(value.kind.lower(), "buttontype")
                self.assertEqual(value.properties["quadtexturesprite"][2], '"GFX_tiled_window_transparent"')
                self.assertIn(metric, value.properties["pdx_tooltip"][2])
            for left, right in zip(values, values[1:]):
                self.assertLessEqual(point(left)[0] + size(left)[0], point(right)[0])
            detail = next(n for n in nodes if n.name == f"psf_{mode}_detail_alpha")
            texts = [n for n in detail.children if n.kind == "instantTextboxType"]
            for first, second in combinations(texts, 2):
                x1, y1 = point(first)
                x2, y2 = point(second)
                w1, h1 = (int(first.properties[k][2]) for k in ("maxwidth", "maxheight"))
                w2, h2 = (int(second.properties[k][2]) for k in ("maxwidth", "maxheight"))
                self.assertTrue(x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1,
                                f"{first.name} overlaps {second.name}")
            description = next(n for n in texts if n.name == "psf_detail_description_alpha")
            self.assertEqual(description.properties["scrollbartype"][2], '"standardtext_slider"')
            affiliations = next(n for n in texts if n.name == "psf_detail_affiliations_alpha")
            self.assertEqual(affiliations.properties["scrollbartype"][2], '"standardtext_slider"')
            self.assertEqual(affiliations.properties["alwaystransparent"][2], "no")

    def test_satisfaction_color_and_unknown_ideology_follow_live_values(self):
        definitions = {mapping(node.value).get("name"): node for path in
                       (self.root / "common/scripted_localisation").glob("psf_ui*.txt")
                       for node in entries(parse(path.read_text()))}
        vm = Interpreter(State())

        def evaluate(name):
            for option in entries(definitions[name].value):
                if option.key == "text":
                    fields = mapping(option.value)
                    if "trigger" not in fields or vm.condition(fields["trigger"]):
                        return fields["localization_key"]

        for value, expected in ((0, "low"), (39.999, "low"), (40, "medium"),
                                (59.999, "medium"), (60, "high"), (100, "high")):
            vm.state.variables["psf_g_alpha_modified_satisfaction"] = value
            self.assertEqual(evaluate("PSFUISatisfaction_alpha"), f"psf_ui_satisfaction_alpha_{expected}")
        self.assertEqual(evaluate("PSFUIIdeologyIcon_alpha"), "psf_ui_unknown_ideology_sprite")
        scripts = [entry for root in entries(parse(self.script)) for entry in entries(root.value)]
        for mode in ("political", "diplomatic"):
            detail = next(n for n in scripts if n.key == f"psf_{mode}_detail_alpha_gui")
            visible = mapping(mapping(detail.value)["triggers"])["psf_detail_ideology_icon_alpha_visible"]
            for ideology, expected in ((0, False), (88412, True), (88413, False)):
                vm.state.variables["psf_g_alpha_ideology"] = ideology
                self.assertEqual(vm.condition(visible), expected)
                self.assertEqual(evaluate("PSFUIIdeologyIcon_alpha"),
                                 "psf_ui_ideology_sprite_liberal" if expected else "psf_ui_unknown_ideology_sprite")

    def test_metric_tooltips_keep_every_part_of_the_row_clickable(self):
        scripts = [entry for root in entries(parse(self.script)) for entry in entries(root.value)]
        for mode in ("political", "diplomatic"):
            groups = next(n for n in scripts if n.key == f"psf_{mode}_groups_test_gui")
            effects = mapping(mapping(groups.value)["effects"])
            for name in ("psf_select_alpha", "psf_row_support_alpha", "psf_row_influence_alpha", "psf_row_satisfaction_alpha"):
                vm = Interpreter(State())
                vm.execute(effects[name + "_click"])
                self.assertEqual(vm.state.variables["psf_ui_group"], 90117)
                self.assertEqual(vm.state.variables["psf_ui_page"], 1)

    def test_pie_pixels_cover_the_disk_once_without_rotated_sector_seams(self):
        occupied = set()
        center = (charts.SIZE - 1) / 2
        for pixels in charts.sector_pixels():
            self.assertFalse(occupied.intersection(pixels))
            occupied.update(pixels)
        expected = {(x, y) for x in range(charts.SIZE) for y in range(charts.SIZE)
                    if (x - center) ** 2 + (y - center) ** 2 <= charts.RADIUS ** 2}
        self.assertEqual(occupied, expected)
        self.assertNotIn("rotation =", self.gui)

    def test_compact_organization_rows_use_original_game_chrome(self):
        nodes = gui_nodes(self.gui)
        row = next(n for n in nodes if n.name == "psf_select_alpha")
        self.assertEqual(row.properties["quadtexturesprite"][2], '"GFX_tiled_window_small_small"')
        row_size = next(n for n in row.children if n.kind.lower() == "size")
        self.assertEqual(row_size.properties["y"][2], "44")
        self.assertFalse((self.root / "gfx/interface/psf/group_row.tga").exists())

    def test_political_and_foreign_text_properties_use_explicit_distinct_scopes(self):
        from tools.ui.audit_layout import script_bindings
        locale = (self.root / "localisation/english/psf_ui_l_english.yml").read_text(encoding="utf-8-sig")
        strings = dict(re.findall(r'^ (\w+):0 "(.*)"$', locale, re.M))
        nodes = {n.name: n for n in gui_nodes(self.gui) if n.name and n.kind == "containerWindowType"}
        bindings = script_bindings(self.root)
        for mode, scope in (("political", "ROOT"), ("diplomatic", "THIS")):
            summary = nodes[f"psf_{mode}_summary"]
            binding = bindings[summary.name]
            if mode == "political":
                self.assertEqual(binding.properties["dirty"][2], f"{scope}.psf_ui_revision")
            else:
                self.assertNotIn("dirty", binding.properties)
            regime = next(n for n in summary.children if n.name == f"psf_{mode}_regime")
            key = regime.properties["text"][2].strip('"')
            self.assertEqual(strings[key], f"[{scope}.PSFUIRegime]")
            tooltip_key = regime.properties["pdx_tooltip"][2].strip('"')
            self.assertIn(f"[?{scope}.psf_legitimacy|1]", strings[tooltip_key])
            for window in (nodes[f"psf_{mode}_groups_test"], nodes[f"psf_{mode}_detail_alpha"], summary):
                for child in window.children:
                    for prop in ("text", "pdx_tooltip"):
                        key = child.properties.get(prop, (0, 0, ""))[2].strip('"')
                        if key in strings and "[" in strings[key]:
                            self.assertIsNone(re.search(r"\[(?:\?psf_|PSFUI)", strings[key]), key)
                            self.assertNotIn("\x01", strings[key])
            properties = next(n for n in binding.children if n.kind == "properties")
            for prop in properties.children:
                if "frame" in prop.properties:
                    self.assertTrue(prop.properties["frame"][2].startswith(scope + ".psf_pie_"))
                elif "image" in prop.properties:
                    self.assertTrue(prop.properties["image"][2].startswith('"[' + scope + ".PSFUI"))
            detail_binding = bindings[f"psf_{mode}_detail_alpha"]
            detail_properties = next(n for n in detail_binding.children if n.kind == "properties")
            image = next(n for n in detail_properties.children if n.kind == "psf_detail_ideology_icon_alpha")
            self.assertEqual(image.properties["image"][2], f'"[{scope}.PSFUIIdeologyIcon_alpha]"')

    def test_native_scrollbar_has_background_gutter_and_real_overflow(self):
        from tools.ui.audit_layout import point, size, property_block
        content = fixture()
        content["profiles"][0]["groups"] = [dict(content["profiles"][0]["groups"][0], id=f"row_{i}", _index=1000+i) for i in range(24)]
        with tempfile.TemporaryDirectory() as folder:
            generate_ui(content, Path(folder))
            nodes = [n for path in (Path(folder) / "interface").glob("psf_society*.gui") for n in gui_nodes(path.read_text())]
            for mode in ("political", "diplomatic"):
                window = next(n for n in nodes if n.name == f"psf_{mode}_groups_test")
                self.assertEqual(window.properties["verticalscrollbar"][2], '"right_vertical_slider"')
                self.assertEqual(window.properties["clipping"][2], "yes")
                self.assertTrue(any(n.kind == "background" for n in window.children))
                gutter = int(property_block(window, "margin")["right"])
                self.assertGreaterEqual(gutter, 12)
                rows = [n for n in window.children if n.name.startswith("psf_select_row_")]
                self.assertEqual(len(rows), 24)
                self.assertGreater(max(point(n)[1] + size(n)[1] for n in rows), size(window)[1])
                self.assertTrue(all(point(n)[0] + size(n)[0] <= size(window)[0] - gutter for n in rows))

    def test_diplomacy_offsets_include_its_native_country_info_origin(self):
        from tools.ui.audit_layout import point
        nodes = {n.name: n for n in gui_nodes(self.gui) if n.name and n.kind == "containerWindowType"}
        native = gui_nodes((self.root / "interface/countrydiplomacyview.gui").read_text())
        country_info = next(n for n in native if n.name == "country_info")
        diplomacy = next(n for n in native if n.name == "diplomacy_tab_top")
        self.assertEqual(point(nodes["psf_diplomatic_summary"])[1], point(diplomacy)[1])
        self.assertEqual(point(nodes["psf_diplomatic_society_side"])[1] + point(country_info)[1], 0)

    def test_government_getter_supports_single_group_alliance_and_caretaker(self):
        definitions = [entry for path in (self.root / "common/scripted_localisation").glob("psf_ui*.txt")
                       for entry in entries(parse(path.read_text()))]
        getter = next(node for node in definitions if mapping(node.value).get("name") == "PSFUIGovernment")
        vm = Interpreter(State())
        def evaluate():
            for option in entries(getter.value):
                if option.key == "text":
                    fields = mapping(option.value)
                    if "trigger" not in fields or vm.condition(fields["trigger"]):
                        return fields["localization_key"]
        self.assertEqual(evaluate(), "psf_ui_caretaker")
        vm.state.variables["psf_governing_group"] = 90117
        self.assertEqual(evaluate(), "psf_group_alpha_short_name")
        vm.state.variables.update(psf_governing_group=0, psf_governing_alliance=9753)
        self.assertEqual(evaluate(), "psf_alliance_cabinet_name")

    def test_opening_own_summary_refreshes_data_without_advancing_time(self):
        scripts = [entry for root in entries(parse(self.script)) for entry in entries(root.value)]
        for mode in ("political", "diplomatic"):
            owners = [n for n in scripts if n.key in (f"psf_{mode}_summary_gui", f"psf_{mode}_government_party_gui")]
            effects = {name: value for node in owners for name, value in mapping(mapping(node.value)["effects"]).items()}
            for action in ("groups", "spectrum", "support", "influence"):
                effect = effects[f"psf_open_{action}_click"]
                condition = entries(effect)[0]
                self.assertEqual(condition.key, "if")
                self.assertEqual(mapping(mapping(condition.value)["limit"])["tag"], "ROOT")
                self.assertEqual(mapping(condition.value)["psf_bootstrap"], "yes")

    def test_government_party_and_ideology_large_art_uses_live_scoped_getters(self):
        from tools.ui.audit_layout import script_bindings
        bindings = script_bindings(self.root)
        for mode, scope in (("political", "ROOT"), ("diplomatic", "THIS")):
            for element, getter, owner in (("psf_open_spectrum", "PSFUIGovIdeologyIcon", "summary"),
                                           ("psf_open_groups", "PSFUIGovernmentPartyIcon", "summary" if mode == "political" else "government_party")):
                binding = bindings[f"psf_{mode}_{owner}"]
                properties = next(n for n in binding.children if n.kind == "properties")
                image = next(n for n in properties.children if n.kind == element)
                self.assertEqual(image.properties["image"][2], f'"[{scope}.{getter}]"')
                window = next(n for n in gui_nodes(self.gui) if n.name == f"psf_{mode}_{owner}")
                control = next(n for n in window.children if n.name == element)
                self.assertEqual(control.kind.lower(), "buttontype")
                self.assertEqual(control.properties["quadtexturesprite"][2], '"GFX_ideology_unknown"')
                self.assertEqual(window.properties["clipping"][2], "yes")
        definitions = [node for path in (self.root / "common/scripted_localisation").glob("psf_ui*.txt")
                       for node in entries(parse(path.read_text()))]
        vm = Interpreter(State())
        def evaluate(name):
            getter = next(n for n in definitions if mapping(n.value).get("name") == name)
            for option in entries(getter.value):
                if option.key == "text":
                    fields = mapping(option.value)
                    if "trigger" not in fields or vm.condition(fields["trigger"]):
                        return fields["localization_key"]
        self.assertEqual(evaluate("PSFUIGovernmentPartyIcon"), "psf_ui_unknown_ideology_sprite")
        vm.state.variables.update(psf_government_leader_group=90117, psf_governing_alliance=9753,
                                  psf_g_alpha_status=1, psf_g_alpha_governing=1, psf_government_ideology=88412)
        self.assertEqual(evaluate("PSFUIGovernmentParty"), "psf_group_alpha_short_name")
        self.assertEqual(evaluate("PSFUIGovernmentPartyIcon"), "psf_ui_government_party_sprite_alpha")
        self.assertEqual(evaluate("PSFUIGovIdeologyIcon"), "psf_ui_government_ideology_sprite_liberal")
        vm.state.variables["psf_g_alpha_status"] = 2
        self.assertEqual(evaluate("PSFUIGovernmentPartyIcon"), "psf_ui_unknown_ideology_sprite")
        vm.state.variables["psf_caretaker"] = 1
        self.assertEqual(evaluate("PSFUIGovIdeologyIcon"), "psf_ui_unknown_ideology_sprite")

    def test_foreign_country_switch_does_not_depend_on_distinct_revision_numbers(self):
        from tools.ui.audit_layout import script_bindings
        bindings = script_bindings(self.root)
        # Two initialized countries commonly both have revision 1. A dirty
        # value alone cannot distinguish them, and viewing must not mutate
        # either foreign country just to force the UI to refresh.
        for name, binding in bindings.items():
            if name.startswith("psf_diplomatic_"):
                self.assertNotIn("dirty", binding.properties, name)
        self.assertIn("dirty", bindings["psf_political_summary"].properties)

    def test_memberships_and_governing_role_remain_independent(self):
        content = fixture()
        content["profiles"][0]["alliances"].append({"id": "pact", "_index": 234,
                                                   "members": ["alpha", "beta"]})
        with tempfile.TemporaryDirectory() as folder:
            generate_ui(content, Path(folder))
            definitions = {mapping(node.value).get("name"): node for path in
                           (Path(folder) / "common/scripted_localisation").glob("psf_ui*.txt")
                           for node in entries(parse(path.read_text()))}
            vm = Interpreter(State())
            def evaluate(name):
                for option in entries(definitions[name].value):
                    if option.key == "text":
                        fields = mapping(option.value)
                        if "trigger" not in fields or vm.condition(fields["trigger"]):
                            return fields["localization_key"]
            self.assertEqual(evaluate("PSFUIAffiliations_alpha"), "psf_ui_none")
            vm.state.variables.update(psf_g_alpha_status=1, psf_g_alpha_governing=1,
                                      psf_a_cabinet_active=1, psf_a_cabinet_g_alpha=1,
                                      psf_a_pact_active=1, psf_a_pact_g_alpha=1)
            self.assertEqual(evaluate("PSFUIAffiliation_alpha_cabinet"), "psf_ui_affiliation_alpha_cabinet")
            self.assertEqual(evaluate("PSFUIAffiliation_alpha_pact"), "psf_ui_affiliation_alpha_pact")
            self.assertEqual(evaluate("PSFUIAffiliations_alpha"), "psf_ui_affiliations_alpha")
            self.assertEqual(evaluate("PSFUIRole_alpha"), "psf_ui_government")
            self.assertEqual(evaluate("PSFUIRowStatus_alpha"), "psf_ui_government")
            vm.state.variables.update(psf_a_cabinet_active=0, psf_g_alpha_governing=0)
            self.assertEqual(evaluate("PSFUIAffiliation_alpha_cabinet"), "psf_ui_empty")
            self.assertEqual(evaluate("PSFUIAffiliation_alpha_pact"), "psf_ui_affiliation_alpha_pact")
            self.assertEqual(evaluate("PSFUIRole_alpha"), "psf_ui_outside_government")
            self.assertEqual(evaluate("PSFUIRowStatus_alpha"), "psf_ui_legal")
            vm.state.variables["psf_a_pact_g_alpha"] = 0
            self.assertEqual(evaluate("PSFUIAffiliations_alpha"), "psf_ui_none")

    def test_spectrum_reference_lanes_read_current_country_and_hide_missing_values(self):
        from tools.ui.audit_layout import point, script_bindings
        bindings = script_bindings(self.root)
        scripts = {entry.key: entry for root in entries(parse(self.script)) for entry in entries(root.value)}
        vm = Interpreter(State())
        for mode, scope in (("political", "ROOT"), ("diplomatic", "THIS")):
            window = next(n for n in gui_nodes(self.gui) if n.name == f"psf_{mode}_spectrum_test")
            properties = next(n for n in bindings[window.name].children if n.kind == "properties")
            triggers = mapping(mapping(scripts[window.name + "_gui"].value)["triggers"])
            values = []
            for reference in ("institution", "government"):
                name = f"psf_axis_reference_{reference}_economy"
                marker = next(n for n in window.children if n.name == name)
                prop = next(n for n in properties.children if n.kind == name)
                self.assertEqual(prop.properties["x"][2], f"{scope}.psf_ui_{reference}_economy")
                self.assertEqual(marker.kind, "iconType")
                values.append(point(marker)[1])
            first_group = next(n for n in window.children if n.name == "psf_axis_marker_alpha_economy")
            self.assertGreaterEqual(values[1] - values[0], 18)
            self.assertGreaterEqual(point(first_group)[1] - values[1], 18)
            for defined in (0, 1):
                for caretaker in (0, 1):
                    vm.state.variables.update(psf_ui_institution_defined_economy=defined, psf_caretaker=caretaker)
                    for suffix in ("", "_track", "_label", "_value"):
                        self.assertEqual(vm.condition(triggers[f"psf_axis_reference_institution_economy{suffix}_visible"]), bool(defined))
                        self.assertEqual(vm.condition(triggers[f"psf_axis_reference_government_economy{suffix}_visible"]), not caretaker)


if __name__ == "__main__":
    unittest.main()
