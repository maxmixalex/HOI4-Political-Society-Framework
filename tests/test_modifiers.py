"""Execute the emitted modifier API, including expiry and base/effective values."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import model, modifiers, runtime

ROOT = Path(__file__).resolve().parents[1]


def source(identifier, *, duration=-1, groups=None, attributes=None, positions=None):
    item = {"id": identifier, "name": {"english": identifier, "simp_chinese": identifier},
            "description": {"english": "Test source", "simp_chinese": "测试来源"}, "duration_days": duration}
    if groups is not None:
        item["groups"] = groups
    if attributes is not None:
        item["attributes"] = attributes
    if positions is not None:
        item["positions"] = positions
    return item


class OrganizationModifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((ROOT / "examples/vanilla/manifest.json").read_text())
        cls.raw["scenarios"] = []
        cls.raw["modifiers"] = [
            source("temporary_campaign", duration=3, groups=["eng_labour"], attributes={"support": {"add": 20, "daily": 2}, "influence": {"factor": 0.1}}),
            source("membership_drive", groups=["eng_labour", "eng_tuc"], attributes={"support": {"add": 5, "factor": 0.2, "daily": 0.5}, "satisfaction": {"add": 10}}),
            source("policy_discussion", duration=2, groups=["eng_labour", "ger_zentrum"], positions={"economy": {"add": -30, "daily": -3}, "authority": {"factor": 0.1}}),
            source("counterpressure", groups=["eng_labour"], attributes={"support": {"factor": -1}}),
        ]
        model.validate(cls.raw)
        cls.manifest = model.normalize(cls.raw)
        cls.effects, cls.triggers = {}, {}
        for text, target in ((runtime.core_effects(), cls.effects), (runtime.effects(cls.manifest), cls.effects),
                             (runtime.core_triggers(), cls.triggers), (runtime.triggers(cls.manifest), cls.triggers)):
            for node in entries(parse(text)):
                if node.key in target:
                    raise AssertionError("Duplicate API " + node.key)
                target[node.key] = node.value

    def vm(self, profile="eng"):
        p = next(p for p in model.profiles(self.manifest) if p["id"] == profile)
        vm = Interpreter(State(tag=p.get("tag", "ZZZ")))
        vm.effects, vm.triggers = self.effects, self.triggers
        vm.run_effect("psf_init_" + profile)
        return vm

    def base(self, vm, field, group="eng_labour"):
        return vm.state.variables[modifiers.gv(group, field)]

    def effective(self, vm, field, group="eng_labour"):
        return vm.state.variables[modifiers.modified_var(group, field)]

    def active(self, vm, modifier, group="eng_labour"):
        return vm.condition(vm.triggers[f"psf_{group}_has_modifier_{modifier}"])

    def test_clamped_bonus_can_be_removed_without_corrupting_base(self):
        vm = self.vm()
        vm.run_effect("psf_set_eng_labour_support", {"psf_amount": 95})
        vm.run_effect("psf_add_eng_labour_modifier_temporary_campaign")
        self.assertEqual(self.base(vm, "support"), 95)
        self.assertEqual(self.effective(vm, "support"), 100)
        vm.run_effect("psf_add_eng_labour_support", {"psf_amount": -10})
        self.assertEqual(self.base(vm, "support"), 85)
        self.assertEqual(self.effective(vm, "support"), 100)
        vm.run_effect("psf_remove_eng_labour_modifier_temporary_campaign")
        self.assertEqual(self.base(vm, "support"), 85)
        self.assertEqual(self.effective(vm, "support"), 85)

    def test_named_and_native_sources_stack_additively_before_bounds(self):
        vm = self.vm()
        vm.run_effect("psf_set_eng_labour_support", {"psf_amount": 20})
        vm.state.modifier_values.update({"psf_eng_labour_support_add": 3, "psf_eng_labour_support_factor": 0.3})
        vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
        self.assertAlmostEqual(self.effective(vm, "support"), (20 + 3 + 5) * (1 + 0.3 + 0.2))
        self.assertEqual(self.base(vm, "support"), 20)
        vm.run_effect("psf_add_eng_labour_modifier_counterpressure")
        self.assertAlmostEqual(self.effective(vm, "support"), (20 + 3 + 5) * 0.5)
        vm.state.modifier_values["psf_eng_labour_support_factor"] = -1
        vm.run_effect("psf_refresh")
        self.assertEqual(self.effective(vm, "support"), 0)
        self.assertEqual(self.base(vm, "support"), 20)

    def test_three_days_applies_three_drifts_then_removes_only_reversible_part(self):
        vm = self.vm()
        before = self.base(vm, "support")
        vm.run_effect("psf_add_eng_labour_modifier_temporary_campaign")
        for day in range(1, 4):
            vm.run_effect("psf_daily_modifiers")
            self.assertAlmostEqual(self.base(vm, "support"), before + day * 2)
            self.assertEqual(self.active(vm, "temporary_campaign"), day < 3)
            self.assertAlmostEqual(self.effective(vm, "support"), min(100, before + day * 2 + (20 if day < 3 else 0)))
        vm.run_effect("psf_daily_modifiers")
        self.assertAlmostEqual(self.base(vm, "support"), before + 6)

    def test_reapplication_refreshes_duration_without_duplicating_source(self):
        vm = self.vm()
        vm.run_effect("psf_add_eng_labour_modifier_temporary_campaign")
        vm.run_effect("psf_daily_modifiers")
        vm.run_effect("psf_add_eng_labour_modifier_temporary_campaign")
        self.assertEqual(vm.state.variables[modifiers.source_var("eng_labour", "temporary_campaign", "days")], 3)
        self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "modifier_count")], 1)
        self.assertAlmostEqual(self.effective(vm, "support"), min(100, self.base(vm, "support") + 20))

    def test_permanent_source_survives_and_removed_drift_is_not_rolled_back(self):
        vm = self.vm()
        before = self.base(vm, "support")
        vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
        for _ in range(8):
            vm.run_effect("psf_daily_modifiers")
        self.assertTrue(self.active(vm, "membership_drive"))
        self.assertAlmostEqual(self.base(vm, "support"), before + 4)
        vm.run_effect("psf_remove_eng_labour_modifier_membership_drive")
        vm.run_effect("psf_daily_modifiers")
        self.assertAlmostEqual(self.base(vm, "support"), before + 4)
        self.assertAlmostEqual(self.effective(vm, "support"), before + 4)

    def test_custom_duration_and_save_state_preserve_expiry(self):
        vm = self.vm()
        vm.run_effect("psf_add_timed_eng_labour_modifier_membership_drive", {"psf_days": 2})
        vm.run_effect("psf_daily_modifiers")
        restored = Interpreter(copy.deepcopy(vm.state))
        restored.effects, restored.triggers = self.effects, self.triggers
        restored.run_effect("psf_init_eng")
        self.assertTrue(self.active(restored, "membership_drive"))
        restored.run_effect("psf_daily_modifiers")
        self.assertFalse(self.active(restored, "membership_drive"))
        self.assertEqual(restored.state.variables[modifiers.source_var("eng_labour", "membership_drive", "days")], 0)

    def test_fractional_duration_cannot_create_unexpiring_source(self):
        vm = self.vm()
        vm.run_effect("psf_add_timed_eng_labour_modifier_membership_drive", {"psf_days": 1.6})
        vm.run_effect("psf_daily_modifiers")
        vm.run_effect("psf_daily_modifiers")
        self.assertFalse(self.active(vm, "membership_drive"))
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_add_timed_eng_labour_modifier_membership_drive", {"psf_days": -1})
        self.assertEqual(vm.state.variables, before)

    def test_all_axes_have_independent_native_add_factor_and_daily_keys(self):
        vm = self.vm()
        vm.run_effect("psf_set_eng_labour_position_economy", {"psf_position": 0})
        vm.state.modifier_values.update({"psf_eng_labour_position_economy_add": 25, "psf_eng_labour_position_economy_factor": 0.2, "psf_eng_labour_position_economy_daily": -2})
        vm.run_effect("psf_daily_modifiers")
        self.assertEqual(self.base(vm, "position_economy"), -2)
        self.assertAlmostEqual(self.effective(vm, "position_economy"), 23 * 1.2)
        for axis in self.manifest["axes"]:
            for kind in modifiers.KINDS:
                self.assertIn(f"psf_eng_labour_position_{axis['id']}_{kind}", modifiers.registry(self.manifest)["native"]["eng_labour"]["position_" + axis["id"]].values())
        old = self.base(vm, "position_economy")
        vm.run_effect("psf_add_eng_labour_position_economy", {"psf_amount": -5})
        self.assertEqual(self.base(vm, "position_economy"), old - 5)

    def test_temporary_position_changes_update_classification_and_restore(self):
        vm = self.vm()
        before = self.base(vm, "position_economy")
        vm.run_effect("psf_add_eng_labour_modifier_policy_discussion")
        self.assertEqual(self.effective(vm, "position_economy"), max(-100, before - 30))
        self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "ui_position_economy")],
                         184 + self.effective(vm, "position_economy"))
        vm.run_effect("psf_daily_modifiers")
        vm.run_effect("psf_daily_modifiers")
        self.assertFalse(self.active(vm, "policy_discussion"))
        self.assertEqual(self.base(vm, "position_economy"), max(-100, before - 6))
        self.assertEqual(self.effective(vm, "position_economy"), self.base(vm, "position_economy"))
        self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "ui_position_economy")],
                         184 + self.base(vm, "position_economy"))

    def test_spectrum_coordinates_follow_modified_values_and_stay_on_track(self):
        vm = self.vm()
        marker = modifiers.gv("eng_labour", "ui_position_economy")
        for value, expected in ((-100, 84), (0, 184), (100, 284)):
            with self.subTest(position=value):
                vm.run_effect("psf_set_eng_labour_position_economy", {"psf_position": value})
                self.assertEqual(vm.state.variables[marker], expected)
        vm.state.modifier_values["psf_eng_labour_position_economy_add"] = -300
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables[marker], 84)
        self.assertEqual(self.base(vm, "position_economy"), 100)
        vm.state.modifier_values["psf_eng_labour_position_economy_add"] = 300
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables[marker], 284)

    def test_suppression_applies_after_modified_influence_once(self):
        vm = self.vm()
        vm.state.modifier_values["psf_eng_labour_influence_add"] = 10
        vm.run_effect("psf_add_eng_labour_modifier_temporary_campaign")
        before = self.base(vm, "influence")
        vm.run_effect("psf_ban_eng_labour")
        self.assertAlmostEqual(vm.state.variables[modifiers.gv("eng_labour", "effective_influence")], min(100, (before + 10) * 1.1) * self.manifest["settings"]["banned_influence_factor"])
        self.assertEqual(self.base(vm, "influence"), before)

    def test_inactive_group_freezes_daily_drift_but_calendar_source_expires(self):
        vm = self.vm("ger")
        before = self.base(vm, "position_economy", "ger_zentrum")
        vm.run_effect("psf_add_ger_zentrum_modifier_policy_discussion")
        vm.run_effect("psf_daily_modifiers")
        vm.run_effect("psf_daily_modifiers")
        self.assertEqual(self.base(vm, "position_economy", "ger_zentrum"), before)
        self.assertFalse(self.active(vm, "policy_discussion", "ger_zentrum"))
        vm.run_effect("psf_activate_ger_zentrum")
        self.assertEqual(self.effective(vm, "position_economy", "ger_zentrum"), before)

    def test_generic_dispatch_and_foreign_guard(self):
        vm = self.vm()
        g = next(g for p in model.profiles(self.manifest) for g in p["groups"] if g["id"] == "eng_labour")
        m = next(m for m in self.manifest["modifiers"] if m["id"] == "membership_drive")
        vm.run_effect("psf_add_group_modifier", {"psf_group": g["_index"], "psf_modifier": m["_index"]})
        self.assertTrue(self.active(vm, "membership_drive"))
        self.assertFalse(self.active(vm, "membership_drive", "eng_tuc"))
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_add_ger_zentrum_modifier_policy_discussion")
        self.assertEqual(vm.state.variables, before)
        vm.run_effect("psf_add_group_modifier", {"psf_group": -1, "psf_modifier": m["_index"]})
        self.assertEqual(vm.state.variables, before)

    def test_unrelated_native_idea_modifiers_are_not_cleared(self):
        vm = self.vm()
        vm.state.modifier_values["psf_eng_labour_support_add"] = 3
        vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
        vm.run_effect("psf_clear_eng_labour_modifiers")
        self.assertFalse(self.active(vm, "membership_drive"))
        self.assertEqual(vm.state.modifier_values["psf_eng_labour_support_add"], 3)
        self.assertEqual(self.effective(vm, "support"), self.base(vm, "support") + 3)

    def test_bridge_does_not_reimport_our_projected_source(self):
        vm = self.vm()
        vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
        before = self.base(vm, "support")
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support"), before)
        vm.run_effect("psf_daily_modifiers")
        before = self.base(vm, "support")
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support"), before)

    def test_native_changes_before_daily_are_imported_before_export(self):
        vm = self.vm()
        classifications = {i["_index"]: i["engine_ideology"] for i in self.manifest["ideologies"]}
        groups = [g for p in model.profiles(self.manifest) if p["id"] == "eng" for g in p["groups"]
                  if g["electoral"] and classifications[vm.state.variables[modifiers.gv(g["id"], "ideology")]] == "democratic"]
        before = sum(self.effective(vm, "support", g["id"]) for g in groups)
        total = vm.state.variables["psf_total_party_support"]
        vm.state.popularities["democratic"] -= 5
        vm.state.popularities["fascism"] += 5
        vm.run_effect("psf_daily_modifiers")
        after = sum(self.effective(vm, "support", g["id"]) for g in groups)
        self.assertAlmostEqual(before - after, total * 0.05)

    def test_bridge_import_inverts_support_factor_without_amplifying_delta(self):
        vm = self.vm()
        vm.state.modifier_values["psf_eng_labour_support_factor"] = 0.5
        vm.run_effect("psf_refresh")
        vm.run_effect("psf_export_popularity")
        classifications = {i["_index"]: i["engine_ideology"] for i in self.manifest["ideologies"]}
        groups = [g for p in model.profiles(self.manifest) if p["id"] == "eng" for g in p["groups"]
                  if g["electoral"] and classifications[vm.state.variables[modifiers.gv(g["id"], "ideology")]] == "democratic"]
        before = sum(self.effective(vm, "support", g["id"]) for g in groups)
        total = vm.state.variables["psf_total_party_support"]
        vm.state.popularities["democratic"] -= 5
        vm.state.popularities["fascism"] += 5
        vm.run_effect("psf_import_popularity")
        after = sum(self.effective(vm, "support", g["id"]) for g in groups)
        self.assertAlmostEqual(before - after, total * 0.05)

    def winning_labour_with_no_influence(self, vm):
        for profile in model.profiles(self.manifest):
            if profile["id"] == "eng":
                for group in profile["groups"]:
                    if group["electoral"]:
                        vm.state.variables[modifiers.gv(group["id"], "support")] = 0
        vm.state.variables[modifiers.gv("eng_labour", "support")] = 100
        vm.state.variables[modifiers.gv("eng_labour", "influence")] = 0
        vm.run_effect("psf_refresh")

    def test_zero_influence_election_winner_recalculates_positive_modifier(self):
        vm = self.vm()
        vm.state.modifier_values["psf_eng_labour_influence_factor"] = 0.5
        self.winning_labour_with_no_influence(vm)
        self.assertEqual(self.effective(vm, "influence"), 0)
        vm.run_effect("psf_hold_election_eng")
        self.assertEqual(self.base(vm, "influence"), 10)
        self.assertEqual(self.effective(vm, "influence"), 15)
        self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "governing")], 1)
        self.assertEqual(vm.state.variables["psf_caretaker"], 0)

    def test_election_mandate_cannot_bypass_zero_or_negative_total_factor(self):
        for factor in (-1, -2):
            with self.subTest(factor=factor):
                vm = self.vm()
                vm.state.modifier_values["psf_eng_labour_influence_factor"] = factor
                self.winning_labour_with_no_influence(vm)
                vm.run_effect("psf_hold_election_eng")
                self.assertEqual(self.base(vm, "influence"), 10)
                self.assertEqual(self.effective(vm, "influence"), 0)
                self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "governing")], 0)
                # Changing a native source does not itself refresh the cache.
                # The public cabinet action must nevertheless use current values.
                vm.state.modifier_values.pop("psf_eng_labour_influence_factor")
                vm.run_effect("psf_form_cabinet_eng")
                self.assertEqual(self.effective(vm, "influence"), 10)
                self.assertEqual(vm.state.variables[modifiers.gv("eng_labour", "governing")], 1)
                self.assertEqual(vm.state.variables["psf_caretaker"], 0)

    def queue_native_support_shift(self, vm, amount=5):
        total = vm.state.variables["psf_total_party_support"]
        groups = [g for p in model.profiles(self.manifest) if p["id"] == "eng" for g in p["groups"] if g["electoral"]]
        mapping = {i["_index"]: i["engine_ideology"] for i in self.manifest["ideologies"]}
        fascist_weight = sum(self.effective(vm, "support", g["id"]) for g in groups
                             if mapping[vm.state.variables[modifiers.gv(g["id"], "ideology")]] == "fascism")
        share = self.effective(vm, "support", "eng_buf") / fascist_weight
        vm.state.popularities["democratic"] -= amount
        vm.state.popularities["fascism"] += amount
        return total * amount / 100 * share

    def test_public_changes_preserve_pending_native_support_exactly_once(self):
        actions = (
            ("psf_add_eng_labour_support", {"psf_amount": 2}),
            ("psf_set_eng_labour_support", {"psf_amount": 25}),
            ("psf_add_eng_labour_influence", {"psf_amount": 2}),
            ("psf_add_eng_labour_satisfaction", {"psf_amount": 2}),
            ("psf_add_eng_labour_position_economy", {"psf_amount": -1}),
            ("psf_set_eng_labour_position_economy", {"psf_position": -10}),
            ("psf_ban_eng_labour", {}),
            ("psf_add_eng_labour_modifier_membership_drive", {}),
            ("psf_add_timed_eng_labour_modifier_membership_drive", {"psf_days": 3}),
            ("psf_remove_eng_labour_modifier_membership_drive", {}),
            ("psf_clear_eng_labour_modifiers", {}),
        )
        for action, arguments in actions:
            with self.subTest(action=action):
                vm = self.vm()
                if action in {"psf_remove_eng_labour_modifier_membership_drive", "psf_clear_eng_labour_modifiers"}:
                    vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
                before = self.base(vm, "support", "eng_buf")
                expected_delta = self.queue_native_support_shift(vm)
                vm.run_effect(action, arguments)
                self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), before + expected_delta)
                acknowledged = self.base(vm, "support", "eng_buf")
                # A second public action, explicit import and export must not
                # consume that same native delta a second time.
                vm.run_effect("psf_add_eng_labour_satisfaction", {"psf_amount": 1})
                vm.run_effect("psf_import_popularity")
                vm.run_effect("psf_export_popularity")
                self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), acknowledged)

    def test_repeated_direct_import_acknowledges_native_snapshot(self):
        vm = self.vm()
        before = self.base(vm, "support", "eng_buf")
        expected_delta = self.queue_native_support_shift(vm)
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), before + expected_delta)
        after = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_import_popularity")
        self.assertEqual(vm.state.variables, after)
        self.assertNotIn("psf_batch_update", vm.state.flags)

    def test_direct_export_cannot_discard_unacknowledged_native_change(self):
        vm = self.vm()
        before = self.base(vm, "support", "eng_buf")
        expected_delta = self.queue_native_support_shift(vm)
        vm.run_effect("psf_export_popularity")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), before + expected_delta)
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), before + expected_delta)

    def test_transaction_preserves_batch_state_and_imports_each_delta_once(self):
        vm = self.vm()
        before = self.base(vm, "support", "eng_buf")
        expected_delta = self.queue_native_support_shift(vm)
        vm.run_effect("psf_begin_transaction")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), before + expected_delta)
        self.assertIn("psf_batch_update", vm.state.flags)
        vm.run_effect("psf_add_eng_labour_modifier_membership_drive")
        vm.run_effect("psf_add_eng_labour_support", {"psf_amount": 2})
        # An explicit import inside the batch must not clear its lifecycle flag.
        self.queue_native_support_shift(vm, amount=1)
        vm.run_effect("psf_import_popularity")
        self.assertIn("psf_batch_update", vm.state.flags)
        acknowledged = self.base(vm, "support", "eng_buf")
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), acknowledged)
        self.assertIn("psf_batch_update", vm.state.flags)
        vm.run_effect("psf_remove_eng_labour_modifier_membership_drive")
        vm.run_effect("psf_commit_transaction")
        self.assertNotIn("psf_batch_update", vm.state.flags)
        vm.run_effect("psf_import_popularity")
        self.assertAlmostEqual(self.base(vm, "support", "eng_buf"), acknowledged)
        self.assertEqual(vm.state.popularities["fascism"], vm.state.variables["psf_last_fascism"])

    def test_timed_tooltip_uses_the_same_normalized_duration_as_state(self):
        for requested, actual in ((0.1, 1), (1.6, 2), (30, 30), (50000, 36500)):
            with self.subTest(requested=requested):
                vm = self.vm()
                vm.run_effect("psf_add_timed_eng_labour_modifier_membership_drive", {"psf_days": requested})
                self.assertEqual(vm.state.temporary["psf_days"], requested)
                self.assertEqual(vm.state.temporary["psf_modifier_days"], actual)
                self.assertEqual(vm.state.variables[modifiers.source_var("eng_labour", "membership_drive", "days")], actual)
        for lang, strings in modifiers.localizations(self.manifest).items():
            text = strings["psf_effect_add_timed_eng_labour_modifier_membership_drive"]
            self.assertIn("[?psf_modifier_days|0]", text, lang)
            self.assertNotIn("[?psf_days|0]", text, lang)

    def test_native_definition_and_localization_coverage(self):
        defined = {n.key for n in entries(parse(modifiers.definitions(self.manifest)))}
        expected = sum(len(p["groups"]) for p in model.profiles(self.manifest)) * len(modifiers.fields(self.manifest)) * 3
        self.assertEqual(len(defined), expected)
        for language, strings in modifiers.localizations(self.manifest).items():
            self.assertTrue(defined <= strings.keys(), language)
            self.assertTrue(all(strings[key] for key in defined))

    def test_invalid_modifier_references_and_zero_days_are_rejected(self):
        for mutate in (
            lambda d: d["modifiers"][0].update(duration_days=0),
            lambda d: d["modifiers"][0].update(groups=["nonexistent"]),
            lambda d: d["modifiers"][0].update(positions={"typo": {"add": 1}}),
            lambda d: d["modifiers"].append(copy.deepcopy(d["modifiers"][0])),
            lambda d: d["modifiers"][0].update(attributes={"typo": {"add": 1}}),
            lambda d: d["modifiers"][0].update(attributes={"support": {"factor": float("nan")}}),
        ):
            data = copy.deepcopy(self.raw)
            mutate(data)
            with self.assertRaises(model.ManifestError):
                model.validate(data)

    def test_scenario_cannot_apply_modifier_outside_declared_targets(self):
        data = copy.deepcopy(self.raw)
        data["scenarios"] = [{"id": "wrong_target", "profile": "eng", "date": "1936.2.1", "title": {"english": "Test", "simp_chinese": "测试"},
                              "description": {"english": "Test", "simp_chinese": "测试"}, "options": [{"id": "apply", "label": {"english": "Apply", "simp_chinese": "应用"},
                              "effects": [{"op": "add_modifier", "group": "eng_tuc", "modifier": "temporary_campaign"}]}]}]
        with self.assertRaisesRegex(model.ManifestError, "does not target"):
            model.validate(data)


if __name__ == "__main__":
    unittest.main()
