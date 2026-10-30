"""Strict native adapters preserve script identity and replace mechanics."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import mechanics, model, native_rules
from psf.script import emit
from psf.ui import gui_nodes


ROOT = Path(__file__).resolve().parents[1]


class NativeMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load(ROOT / "examples/vanilla/manifest.json")
        cls.source = (mechanics.ASSETS / "00_ideologies.txt").read_text(encoding="utf-8-sig")

    def test_neutralized_ideologies_keep_every_native_subtype_and_identity_field(self):
        generated = mechanics.neutralize_ideologies(self.source)
        def identities(text):
            return {(n.parent.kind, n.kind): text[n.start:n.end] for n in gui_nodes(text)
                    if n.parent and n.parent.parent and n.parent.parent.kind == "ideologies"
                    and n.kind in {"types", "dynamic_faction_names", "color"}}
        self.assertEqual(identities(generated), identities(self.source))
        root = entries(parse(generated))[0]
        bodies = []
        for group in entries(root.value):
            bodies.append(tuple(n for n in entries(group.value) if n.key not in {"types", "dynamic_faction_names", "color"}))
        self.assertEqual(len(bodies), 4)
        self.assertTrue(all(body == bodies[0] for body in bodies))
        self.assertNotIn("justify_war_goal_when_in_major_war_time", generated)
        self.assertNotIn("drift_defence_factor", generated)

    def test_strict_adapter_writes_real_engine_overrides_and_compat_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            report = mechanics.write_native_mechanics(self.manifest, output)
            self.assertEqual(len(report["files"]), 6)
            self.assertEqual(report["source"], "bundled/native_ideologies/00_ideologies.txt")
            self.assertTrue(all((output / name).is_file() for name in report["files"]))
            definitions = (output / "common/defines/zz_psf_native_politics.lua").read_text()
            self.assertIn("NDefines.NCountry.BASE_STABILITY_PARTY_POPULARITY_FACTOR = 0", definitions)
            self.assertIn("NDefines.NTrade.PARTY_SUPPORT_TRADE_FACTOR = 0", definitions)
            self.assertTrue(report["remaining_native_script_projection"])
        compat = copy.deepcopy(self.manifest)
        compat["settings"]["mechanics_mode"] = "compat"
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(mechanics.write_native_mechanics(compat, Path(folder))["enabled"])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_strict_adapter_rejects_incompatible_custom_native_ideology_system(self):
        altered = self.source.replace("democratic = {", "custom_category = {", 1)
        with self.assertRaisesRegex(model.ManifestError, "exactly the four"):
            mechanics.neutralize_ideologies(altered)
        invalid = copy.deepcopy(self.manifest)
        invalid["settings"]["bridge_mode"] = "bidirectional"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(model.ManifestError, "bridge_mode='export'"):
                mechanics.write_native_mechanics(invalid, Path(folder))

    def test_native_affinity_matrix_and_ally_desires_are_independent_of_ideology(self):
        for action in ("CALL_ALLY", "JOIN_ALLY"):
            for ideology in ("DEMOCRATIC", "NEUTRAL", "FASCIST", "COMMUNIST"):
                self.assertEqual(mechanics.DEFINES[f"NAI.{action}_{ideology}_DESIRE"], 0)
        for source in ("FASCISTS", "DEMOCRACIES", "COMMUNISTS"):
            for action in ("BEFRIEND", "ALLY", "ANTAGONIZE"):
                for target in ("FASCISTS", "DEMOCRACIES", "COMMUNISTS"):
                    self.assertEqual(mechanics.DEFINES[f"NAI.{source}_{action}_{target}"], 0)
        self.assertEqual(mechanics.DEFINES["NOperatives.OPERATIVE_BASE_BOOST_IDEOLOGY"], 0)
        self.assertEqual(mechanics.DEFINES["NDiplomacy.MARKET_ACCESS_ACCEPTANCE_SCRIPTED_IDEOLOGY_ACCEPTANCE"], 0)

    def policy_vm(self, manifest=None):
        manifest = manifest or self.manifest
        vm = Interpreter(State())
        vm.state.flags.add("psf_initialized")
        vm.state.variables.update(psf_elections_enabled=0, psf_regime=0)
        vm.effects = {n.key: n.value for n in entries(parse(emit(mechanics.definitions(manifest))))}
        vm.dynamic_definitions = {n.key: n.value for n in entries(parse(mechanics.dynamic_modifiers(manifest)))}
        return vm

    def test_native_modifier_sources_are_canceled_without_feedback_or_country_leaks(self):
        first, second = self.policy_vm(), self.policy_vm()
        for amount in (.2, .2, .35, 0, -.15, -.15):
            for index, name in enumerate(mechanics.NATIVE_MODIFIER_OFFSETS):
                first.state.modifier_values[name] = amount * (index + 1)
                second.state.modifier_values[name] = -amount * (index + 2)
            for vm in (first, second):
                vm.run_effect("psf_apply_native_policy")
                for name in mechanics.NATIVE_MODIFIER_OFFSETS:
                    self.assertAlmostEqual(vm.number("modifier@" + name), 0, msg=name)
                # Repeated refreshes must not manufacture a new source.
                vm.run_effect("psf_apply_native_policy")
                for name in mechanics.NATIVE_MODIFIER_OFFSETS:
                    self.assertAlmostEqual(vm.number("modifier@" + name), 0, msg=name)
        self.assertNotEqual(first.state.variables, second.state.variables)

    def test_saved_offsets_recover_when_dynamic_policy_is_removed_or_upgraded(self):
        vm = self.policy_vm()
        vm.state.variables["psf_native_popularity_stability_offset"] = -.3
        vm.state.modifier_values["party_popularity_stability_factor"] = .2
        vm.state.modifier_values["fascism_drift"] = .1
        # An old save has the stability offset but none of the new fields.
        vm.run_effect("psf_apply_native_policy")
        self.assertAlmostEqual(vm.number("modifier@party_popularity_stability_factor"), 0)
        self.assertAlmostEqual(vm.number("modifier@fascism_drift"), 0)
        vm.state.dynamic_modifiers.clear()
        vm.state.applied_dynamic_values.clear()
        vm.state.modifier_values["party_popularity_stability_factor"] = .45
        vm.run_effect("psf_apply_native_policy")
        self.assertAlmostEqual(vm.number("modifier@party_popularity_stability_factor"), 0)
        self.assertAlmostEqual(vm.number("modifier@fascism_drift"), 0)
        self.assertEqual(vm.state.undefined_reads, set())

    def test_compat_does_not_cancel_native_modifier_sources(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["settings"]["mechanics_mode"] = "compat"
        vm = self.policy_vm(manifest)
        vm.state.modifier_values.update(fascism_drift=.12, democratic_acceptance=25)
        vm.run_effect("psf_apply_native_policy")
        self.assertEqual(vm.number("modifier@fascism_drift"), .12)
        self.assertEqual(vm.number("modifier@democratic_acceptance"), 25)
        self.assertEqual(vm.state.dynamic_modifiers, set())

    def test_occupation_adapter_changes_only_four_native_ideology_gates(self):
        source = (native_rules.ASSETS / native_rules.OCCUPATION).read_text(encoding="utf-8-sig")
        converted, changed = native_rules.neutralize(source, native_rules.OCCUPATION)
        self.assertEqual(set(changed), set(native_rules.OCCUPATION_GATES))
        # Exact source-preservation check independent of the adapter's paths.
        import re
        expected, count = re.subn(r"has_government\s*=\s*(?:democratic|communism|fascism)", "always = yes", source)
        self.assertEqual(count, 4)
        self.assertEqual(converted, expected)
        self.assertNotIn("has_government", converted)
        for before, after in zip(entries(parse(source)), entries(parse(converted))):
            self.assertEqual(before.key, after.key)
            if before.key not in native_rules.OCCUPATION_GATES:
                self.assertEqual(before, after)
        for altered in (source.replace("liberate_workers_occupation = {", "renamed_law = {"),
                        source.replace("has_government = communism", "has_government = neutrality"),
                        source + "\nnew_law = { visible = { has_government = fascism } }\n"):
            with self.assertRaises(model.ManifestError):
                native_rules.neutralize(altered, native_rules.OCCUPATION)

    def test_regime_policy_executes_and_clears_previous_overrides_on_transition(self):
        manifest = copy.deepcopy(self.manifest)
        custom = next(r for r in manifest["regimes"] if r.get("elections"))
        ordinary = next(r for r in manifest["regimes"] if not r.get("elections"))
        custom["native_policy"] = {"generate_wargoal_tension": .72,
                                   "send_volunteers_tension": .18,
                                   "can_create_collaboration_government": True}
        vm = Interpreter(State())
        vm.state.flags.add("psf_initialized")
        vm.effects = {n.key: n.value for n in entries(parse(emit(mechanics.definitions(manifest))))}
        vm.state.variables.update(psf_regime=custom["_index"], psf_elections_enabled=1)
        vm.run_effect("psf_apply_native_policy")
        self.assertEqual(vm.state.variables["psf_native_generate_wargoal_tension"], .72)
        self.assertEqual(vm.state.variables["psf_native_send_volunteers_tension"], .18)
        self.assertEqual(vm.state.variables["psf_native_join_faction_tension"], .8)
        self.assertTrue(vm.state.rules["can_create_collaboration_government"])
        vm.state.variables.update(psf_regime=ordinary["_index"], psf_elections_enabled=0)
        vm.run_effect("psf_apply_native_policy")
        self.assertEqual(vm.state.variables["psf_native_generate_wargoal_tension"], .5)
        self.assertEqual(vm.state.variables["psf_native_send_volunteers_tension"], .4)
        self.assertFalse(vm.state.rules["can_only_justify_war_on_threat_country"])
        vm.state.variables.update(psf_regime=custom["_index"], psf_elections_enabled=1)
        vm.run_effect("psf_apply_native_policy")
        self.assertEqual(vm.state.variables["psf_native_generate_wargoal_tension"], .72)

    def test_native_policy_rejects_unknown_keys_wrong_types_and_nonfraction_thresholds(self):
        import json
        raw = json.loads((ROOT / "examples/vanilla/manifest.json").read_text())
        for override in ({"unknown_tension": .2}, {"generate_wargoal_tension": 72},
                         {"send_volunteers_tension": -.1},
                         {"can_lower_tension": "yes"}, {"join_faction_tension": True}):
            data = copy.deepcopy(raw)
            data["regimes"][0]["native_policy"] = override
            with self.subTest(policy=override), self.assertRaises(model.ManifestError):
                model.validate(data)

    def test_generic_relation_and_peace_adapters_preserve_unrelated_native_statements(self):
        for relative in (native_rules.OPINIONS, native_rules.PEACE):
            source = (native_rules.ASSETS / relative).read_text(encoding="utf-8-sig")
            actual, changed = native_rules.neutralize(source, relative)
            def definitions(text):
                root = next(n for n in gui_nodes(text) if n.parent is None)
                return {n.kind: (n, text[n.start:n.end]) for n in root.children}
            before, after = definitions(source), definitions(actual)
            self.assertEqual(before.keys(), after.keys())
            for key in before.keys() - set(changed):
                self.assertEqual(before[key][1], after[key][1], key)
            if relative == native_rules.OPINIONS:
                self.assertEqual(set(changed), native_rules.PARTY_OPINIONS)
                for key in changed:
                    self.assertEqual(after[key][0].properties["value"][2], "0")
            else:
                expected = {key for key, (node, _) in before.items()
                            if node.properties.get("category", (None, None, None))[2] == "ideology"}
                self.assertEqual(set(changed), expected)
                self.assertEqual(len(changed), 13)
                for key in changed:
                    node = after[key][0]
                    self.assertEqual(node.properties["cost_multiplier"][2], "1.0")
                    enable = next(c for c in node.children if c.kind == "enable")
                    self.assertEqual(enable.properties["always"][2], "no")
                    self.assertNotIn("has_government", actual[enable.start:enable.end])

    def test_generic_adapter_rejects_changed_native_structure(self):
        source = (native_rules.ASSETS / native_rules.OPINIONS).read_text(encoding="utf-8-sig")
        with self.assertRaises(model.ManifestError):
            native_rules.neutralize(source.replace("same_ruling_party", "renamed_native_rule"),
                                    native_rules.OPINIONS)
        peace = (native_rules.ASSETS / native_rules.PEACE).read_text(encoding="utf-8-sig")
        with self.assertRaises(model.ManifestError):
            native_rules.neutralize(peace.replace("category = ideology", "category = unknown"),
                                    native_rules.PEACE)

    def test_generic_adapter_preserves_inline_siblings_and_balanced_blocks(self):
        opinions = ('opinion_modifiers = { same_ruling_party = { value = 25 decay = 1 } '
                    'similar_ruling_party = { value = 15 } different_party_types = { value = -10 } '
                    'unrelated_relation = { value = 27 } }')
        result, changed = native_rules.neutralize(opinions, native_rules.OPINIONS)
        root = next(n for n in gui_nodes(result) if n.parent is None)
        items = {n.kind: n for n in root.children}
        self.assertEqual(set(changed), native_rules.PARTY_OPINIONS)
        self.assertEqual(items["same_ruling_party"].properties["value"][2], "0")
        self.assertEqual(items["same_ruling_party"].properties["decay"][2], "1")
        self.assertIn('unrelated_relation = { value = 27 }', result)
        self.assertEqual(len(items), 4)

        peace = ('peace_action_modifiers = { ideology_cost = { enable = { has_government = fascism } '
                 'cost_multiplier = 0.5 category = ideology } '
                 'unrelated_cost = { enable = { always = yes } cost_multiplier = 0.8 category = distance } }')
        result, changed = native_rules.neutralize(peace, native_rules.PEACE)
        root = next(n for n in gui_nodes(result) if n.parent is None)
        items = {n.kind: n for n in root.children}
        self.assertEqual(changed, ["ideology_cost"])
        self.assertEqual(items["ideology_cost"].properties["cost_multiplier"][2], "1.0")
        self.assertEqual(items["ideology_cost"].properties["category"][2], "ideology")
        enable = next(n for n in items["ideology_cost"].children if n.kind == "enable")
        self.assertEqual(enable.properties["always"][2], "no")
        self.assertIn('unrelated_cost = { enable = { always = yes } cost_multiplier = 0.8 category = distance }', result)
        self.assertEqual(len(items), 2)


if __name__ == "__main__":
    unittest.main()
