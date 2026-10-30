"""Selected-country politics follows profile dates and restores campaign names."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unicodedata
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import frontend, icons, model
from psf.script import emit

ROOT = Path(__file__).resolve().parents[1]


class FrontendPoliticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load(ROOT / "examples/vanilla/manifest.json")
        cls.profiles = {p["id"]: p for p in model.profiles(cls.manifest)}
        cls.effects = {node.key: node.value for node in entries(parse(emit(frontend.runtime_effects(cls.manifest))))}

    def test_native_party_binding_switches_profiles_dates_and_both_name_forms(self):
        for pid, profile in self.profiles.items():
            for day in ((1936, 1, 1), (1939, 8, 14)):
                with self.subTest(profile=pid, date=day):
                    vm = Interpreter(State(tag=profile.get("tag", "ZZZ"), date=day,
                                           flags={"psf_initialized", "psf_profile_" + pid}))
                    vm.effects = self.effects
                    vm.run_effect("psf_prepare_frontend")
                    boundary = None
                    for candidate in frontend.states(profile)[1:]:
                        if tuple(map(int, candidate.split("."))) <= day:
                            boundary = candidate
                    suffix = frontend.state_id(profile, boundary)
                    self.assertIn("psf_frontend_preview_active", vm.state.flags)
                    for engine in model.ENGINE_IDEOLOGIES:
                        self.assertEqual(vm.state.party_names[engine], {
                            "name": "psf_frontend_panel_" + suffix,
                            "long_name": "psf_frontend_panel_" + suffix})
                    vm.run_effect("psf_finish_frontend")
                    self.assertNotIn("psf_frontend_preview_active", vm.state.flags)
                    for engine in model.ENGINE_IDEOLOGIES:
                        key = "psf_native_" + suffix + "_" + engine
                        self.assertEqual(vm.state.party_names[engine], {"name": key, "long_name": key + "_long"})
                    before = copy.deepcopy(vm.state)
                    vm.run_effect("psf_finish_frontend")
                    self.assertEqual(vm.state, before)

    def test_uninitialized_countries_are_never_given_an_unresolved_presentation(self):
        vm = Interpreter(State(flags={"psf_profile_ger"}))
        vm.effects = self.effects
        vm.run_effect("psf_prepare_frontend")
        self.assertEqual(vm.state.party_names, {})
        self.assertNotIn("psf_frontend_preview_active", vm.state.flags)

    def test_unknown_profile_does_not_claim_or_discard_a_pending_presentation(self):
        vm = Interpreter(State(flags={"psf_initialized", "psf_profile_removed_content"}))
        vm.effects = self.effects
        vm.state.party_names["neutrality"] = {"name": "external_party", "long_name": "external_party_long"}
        before = copy.deepcopy(vm.state)
        vm.run_effect("psf_prepare_frontend")
        self.assertEqual(vm.state, before)
        vm.state.flags.add("psf_frontend_preview_active")
        vm.run_effect("psf_finish_frontend")
        self.assertIn("psf_frontend_preview_active", vm.state.flags)
        self.assertEqual(vm.state.party_names, before.party_names)
        # A temporarily unavailable profile must still be able to complete
        # its restoration once the correct content profile is selected.
        vm.state.flags.add("psf_profile_ger")
        vm.run_effect("psf_finish_frontend")
        self.assertNotIn("psf_frontend_preview_active", vm.state.flags)
        self.assertEqual(vm.state.party_names["neutrality"]["name"], "psf_native_ger_base_neutrality")

    def test_governing_party_is_preferred_to_a_more_influential_court_or_army(self):
        profile = copy.deepcopy(self.profiles["jap"])
        alliance = next(a for a in profile["alliances"] if a["id"] == profile["government"]["alliance"])
        members = [g for g in profile["groups"] if g["id"] in alliance["members"]]
        party = next(g for g in members if g["kind"] == "party" or g["electoral"])
        other = next(g for g in members if g["kind"] != "party" and not g["electoral"])
        for group in members:
            group["influence"] = 0
        other["influence"] = 100
        result = frontend.snapshot(self.manifest, profile, None)
        self.assertEqual(result["ruling_group"]["id"], party["id"])
        party["status"] = "banned"
        result = frontend.snapshot(self.manifest, profile, None)
        self.assertEqual(result["ruling_group"]["id"], other["id"])
        other["influence"] = 0
        self.assertIsNone(frontend.snapshot(self.manifest, profile, None)["ruling_group"])

    def test_direct_government_needs_no_alliance_and_caretakers_have_no_invented_party(self):
        profile = copy.deepcopy(next(iter(self.manifest["fallback_profiles"])))
        self.assertEqual(profile["alliances"], [])
        chosen = profile["government"]["group"]
        result = frontend.snapshot(self.manifest, profile, None)
        self.assertEqual(result["ruling_group"]["id"], chosen)
        profile["government"] = None
        result = frontend.snapshot(self.manifest, profile, None)
        self.assertIsNone(result["ruling_group"])
        self.assertIsNone(result["ideology"])

    def test_date_override_changes_government_regime_and_archetype_without_mutating_source(self):
        profile = copy.deepcopy(self.profiles["eng"])
        chosen = next(g for g in profile["groups"] if g["id"] == "eng_labour")
        profile["start_overrides"] = [{"date": "1939.1.1", "government": {"group": chosen["id"]},
                                      "regime": self.manifest["regimes"][-1]["id"],
                                      "groups": [{"id": chosen["id"], "influence": 80,
                                                  "positions": {axis["id"]: -100 for axis in self.manifest["axes"]}}]}]
        original = copy.deepcopy(profile)
        early = frontend.snapshot(self.manifest, profile, None)
        late = frontend.snapshot(self.manifest, profile, "1939.1.1")
        self.assertNotEqual(early["ruling_group"]["id"], late["ruling_group"]["id"])
        self.assertEqual(late["ruling_group"]["id"], chosen["id"])
        self.assertEqual(late["regime"]["id"], profile["start_overrides"][0]["regime"])
        self.assertEqual(late["ideology"], icons.closest_ideology(self.manifest, late["ruling_group"]))
        self.assertEqual(profile, original)

    def test_text_payload_contains_both_large_identities_regime_and_two_pies(self):
        state = frontend.snapshot(self.manifest, self.profiles["ger"], None)
        image = {"sprite": "GFX_actual_snapshot"}
        for language in ("english", "simp_chinese"):
            lines = frontend.panel_text(state, image, language).split("\n")
            self.assertEqual(len(lines), 6)
            self.assertIn(icons.texticon(state["ruling_group"]), lines[0])
            self.assertIn(state["regime"]["name"][language][:5], lines[1])
            self.assertEqual(lines[3:5], ["", ""])
            self.assertIn(icons.sprite(state["ruling_group"]).removeprefix("GFX_"), lines[5])
            self.assertIn(icons.sprite(state["ideology"], "ideology").removeprefix("GFX_"), lines[5])
            self.assertIn("£actual_snapshot£", lines[5])
            self.assertNotIn("PSF", "\n".join(lines))
            self.assertNotIn("$", "\n".join(lines))
        custom = copy.deepcopy(state)
        custom["ideology"]["large_icon"] = "GFX_author_large_archetype"
        custom["ruling_group"]["small_icon"] = "GFX_author_small_party"
        custom["ruling_group"]["large_icon"] = "GFX_author_large_party"
        text = frontend.panel_text(custom, image, "english")
        self.assertIn("£author_large_archetype£", text)
        self.assertIn("£author_small_party£", text)
        self.assertIn("£author_large_party£", text)
        self.assertEqual(text.count("§Y"), text.count("§!"))

    def test_native_information_columns_fit_both_large_icons_without_covering_the_portrait(self):
        from psf.ui import gui_nodes, patch_native
        source = ROOT / "psf/assets/native_gui"
        with tempfile.TemporaryDirectory() as folder:
            patch_native(source, Path(folder), frontend_adapter=True)
            text = (Path(folder) / "interface/frontendgamesetupview.gui").read_text()
        nodes = gui_nodes(text)

        def node(name, parent):
            return next(item for item in nodes if item.name == name and parent in item.ancestry)

        def coordinate(item, key, field):
            child = next(child for child in item.children if child.kind.lower() == key)
            return int(child.properties[field][2])

        for parent in ("gamesetup_country_details", "gamesetup_interesting_countries_window"):
            party = node("party", parent)
            width = int(party.properties["maxwidth"][2])
            self.assertGreaterEqual(width, 64 + 64 + 140 + 18)
            self.assertEqual(node("party_label", parent).properties["text"][2].strip('"'), "RULING_PARTY")
            native_icon = node("pol_faction_icon", parent)
            self.assertEqual(native_icon.properties["hide"][2], "yes")
            label = node("party_label", parent)
            self.assertLessEqual(coordinate(label, "position", "y") + int(label.properties["maxheight"][2]),
                                 coordinate(party, "position", "y"))
            self.assertEqual(label.properties["multiline"][2], "no")
            self.assertEqual(node("leader", parent).properties["multiline"][2], "no")
        parent = "gamesetup_interesting_countries_window"
        info = node("info", parent)
        panel = next(item for item in nodes if item.name == parent)
        self.assertLessEqual(coordinate(info, "position", "y") + coordinate(info, "size", "height"),
                             coordinate(panel, "size", "height"))
        fields = [node(name, parent) for name in ("leader_label", "leader", "party_label", "party")]
        for previous, following in zip(fields, fields[1:]):
            self.assertLessEqual(coordinate(previous, "position", "y") + int(previous.properties["maxheight"][2]),
                                 coordinate(following, "position", "y"))
        right = coordinate(info, "position", "x") + coordinate(info, "size", "width")
        self.assertLessEqual(right, coordinate(node("minor_portrait_overlay", parent), "position", "x"))
        self.assertLess(coordinate(node("minor_country_leader", parent), "position", "x"),
                        coordinate(node("nation_title", parent), "position", "x"))
        # The country title retains its original right edge; the historical
        # description and native focus/spirit anchors remain untouched.
        self.assertEqual(coordinate(node("nation_title", parent), "position", "x") +
                         int(node("nation_title", parent).properties["maxwidth"][2]), 782)
        self.assertEqual(coordinate(node("history", parent), "position", "x"), 810)
        self.assertEqual(coordinate(node("spirit", parent), "position", "x"), 451)

    def test_extreme_names_cannot_grow_the_native_text_rows(self):
        for label in ("Very long organization " * 20, "政治团体名称" * 20, "WWMW" * 20, "A\nB\tC"):
            short = frontend._limit_label(label)
            columns = sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in short)
            self.assertLessEqual(columns, 22)
            self.assertNotIn("\n", short)
            self.assertNotIn("\t", short)
        # Proportional fonts give W/M much more width than a typical letter.
        # Their shortened line must reserve the same room as double-width CJK.
        self.assertLessEqual(len(frontend._limit_label("W" * 80)), 11)

    def test_all_frontend_files_are_reproducible(self):
        manifest = model.load(ROOT / "examples/minimal/manifest.json")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reports = [frontend.generate(manifest, root / name) for name in ("a", "b")]
            self.assertEqual(*reports)
            a = {p.relative_to(root / "a"): p.read_bytes() for p in (root / "a").rglob("*") if p.is_file()}
            b = {p.relative_to(root / "b"): p.read_bytes() for p in (root / "b").rglob("*") if p.is_file()}
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
