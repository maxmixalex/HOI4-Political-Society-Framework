"""Regressions for same-turn state repair and neutral native projections."""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import frontend, mechanics, model, runtime


ROOT = Path(__file__).resolve().parents[1]


class RuntimeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load(ROOT / "examples/vanilla/manifest.json")
        cls.profiles = {profile["id"]: profile for profile in model.profiles(cls.manifest)}
        cls.effects = {node.key: node.value for text in (runtime.core_effects(), runtime.effects(cls.manifest))
                       for node in entries(parse(text))}
        cls.triggers = {node.key: node.value for text in (runtime.core_triggers(), runtime.triggers(cls.manifest))
                        for node in entries(parse(text))}
        cls.dynamics = {node.key: node.value for node in entries(parse(mechanics.dynamic_modifiers(cls.manifest)))}

    def vm(self, profile="eng", date=(1936, 1, 1)):
        definition = self.profiles[profile]
        vm = Interpreter(State(tag=definition.get("tag", "ZZZ"), date=date))
        vm.effects, vm.triggers = self.effects, self.triggers
        vm.dynamic_definitions = self.dynamics
        vm.run_effect("psf_init_" + profile)
        return vm

    def test_zero_support_replaces_stale_native_slots_without_creating_psf_support(self):
        for profile in ("eng", "fra", "ger"):
            with self.subTest(profile=profile):
                vm = self.vm(profile)
                foreign = self.vm("ger" if profile != "ger" else "eng")
                foreign_before = copy.deepcopy(foreign.state)
                legitimacy = vm.state.variables["psf_legitimacy"]
                stability = vm.state.variables["psf_stability_modifier"]
                vm.run_effect("psf_begin_transaction")
                for group in self.profiles[profile]["groups"]:
                    if group["electoral"]:
                        vm.run_effect("psf_set_" + group["id"] + "_support", {"psf_amount": 0})
                # A native event can have altered the four-slot payload in the
                # same turn. The strict bridge must discard that stale split.
                vm.state.popularities = {"democratic": 15, "fascism": 25, "communism": 35, "neutrality": 25}
                vm.run_effect("psf_commit_transaction")
                government = vm.state.engine["ruling_party"]
                self.assertEqual(vm.state.popularities, {engine: 100 if engine == government else 0
                                                       for engine in model.ENGINE_IDEOLOGIES})
                self.assertEqual(vm.state.variables["psf_total_party_support"], 0)
                self.assertEqual(vm.state.variables["psf_government_support"], 0)
                self.assertEqual(set(vm.state.arrays["psf_pie_support_frames"]), {1})
                self.assertEqual(vm.state.variables["psf_legitimacy"], legitimacy)
                self.assertEqual(vm.state.variables["psf_stability_modifier"], stability)
                self.assertEqual(vm.number("modifier@party_popularity_stability_factor"), 0)
                for group in self.profiles[profile]["groups"]:
                    if group["electoral"]:
                        self.assertEqual(vm.state.variables[runtime.gv(group["id"], "support")], 0)
                        self.assertEqual(vm.state.variables[runtime.gv(group["id"], "support_share")], 0)
                for engine in model.ENGINE_IDEOLOGIES:
                    self.assertEqual(vm.state.variables["psf_last_" + engine], vm.state.popularities[engine])
                # Returning to a positive electorate removes the placeholder.
                group = next(group for group in self.profiles[profile]["groups"] if group["electoral"] and group["status"] == "legal")
                vm.run_effect("psf_set_" + group["id"] + "_support", {"psf_amount": 10})
                self.assertEqual(vm.state.variables["psf_total_party_support"], 10)
                self.assertEqual(sum(vm.state.popularities.values()), 100)
                self.assertEqual(foreign.state, foreign_before, "Another country's records and native projection must remain separate")

    def test_monthly_respects_outer_transaction_and_current_membership(self):
        vm = self.vm()
        vm.run_effect("psf_begin_transaction")
        vm.run_effect("psf_leave_eng_government_eng_national_labour")
        before = vm.state.variables[runtime.gv("eng_national_labour", "satisfaction")]
        vm.run_effect("psf_set_eng_labour_support", {"psf_amount": 88})
        projected = dict(vm.state.popularities)
        vm.run_effect("psf_monthly")
        self.assertIn("psf_batch_update", vm.state.flags)
        self.assertEqual(vm.state.popularities, projected)
        self.assertAlmostEqual(vm.state.variables[runtime.gv("eng_national_labour", "satisfaction")],
                               before + self.manifest["settings"]["monthly_opposition_satisfaction"])
        vm.run_effect("psf_commit_transaction")
        self.assertNotIn("psf_batch_update", vm.state.flags)
        self.assertNotEqual(vm.state.popularities, projected)

    def test_bootstrap_seeds_missing_records_at_current_date_and_preserves_existing_state(self):
        vm = self.vm(date=(1939, 8, 14))
        group_id, alliance_id = "eng_labour", "eng_labour_movement"
        current = frontend.applied_profile(self.profiles["eng"], "1939.8.14")
        group = next(group for group in current["groups"] if group["id"] == group_id)
        alliance = next(alliance for alliance in current["alliances"] if alliance["id"] == alliance_id)
        vm.run_effect("psf_set_eng_conservative_support", {"psf_amount": 9})
        vm.state.variables["psf_election_count"] = 7
        vm.state.variables["psf_election_clock"] = 13
        vm.state.variables["psf_legitimacy"] = 43
        selected = (vm.state.variables["psf_governing_group"], vm.state.variables["psf_governing_alliance"])
        # These fields do not exist when an old save first loads a compiled
        # update that introduces a group and an additional political alliance.
        for key in list(vm.state.variables):
            if key.startswith(("psf_g_" + group_id + "_", "psf_m_" + group_id + "_", "psf_a_" + alliance_id + "_")):
                del vm.state.variables[key]
        vm.state.flags.discard(runtime.records_marker(self.profiles["eng"]))
        vm.run_effect("psf_bootstrap")
        for field in ("support", "influence", "satisfaction"):
            self.assertEqual(vm.state.variables[runtime.gv(group_id, field)], group[field])
        self.assertEqual(vm.state.variables[runtime.gv(group_id, "status")], model.STATUS[group["status"]])
        self.assertEqual(vm.state.variables[runtime.av(alliance_id, "cohesion")], alliance["cohesion"])
        for member in self.profiles["eng"]["groups"]:
            self.assertEqual(vm.state.variables[runtime.av(alliance_id, "g_" + member["id"])],
                             int(member["id"] in alliance["members"]))
        self.assertEqual(vm.state.variables[runtime.gv("eng_conservative", "support")], 9)
        self.assertEqual(vm.state.variables["psf_election_count"], 7)
        self.assertEqual(vm.state.variables["psf_election_clock"], 13)
        self.assertEqual(vm.state.variables["psf_legitimacy"], 43)
        self.assertEqual((vm.state.variables["psf_governing_group"], vm.state.variables["psf_governing_alliance"]), selected)
        before = dict(vm.state.variables)
        vm.run_effect("psf_initialize")
        self.assertEqual(vm.state.variables, before, "A synchronized campaign must not repeatedly rebuild or reset")

    def test_missing_axis_repair_keeps_zero_scores_dissolved_alliances_and_source_timers(self):
        vm = self.vm()
        vm.run_effect("psf_set_eng_labour_support", {"psf_amount": 0})
        vm.run_effect("psf_deactivate_eng_labour")
        vm.run_effect("psf_dissolve_eng_labour_movement")
        group = next(group for group in self.profiles["eng"]["groups"] if group["id"] == "eng_labour")
        axis = next(iter(group["positions"]))
        del vm.state.variables[runtime.gv(group["id"], "position_" + axis)]
        vm.state.flags.discard(runtime.records_marker(self.profiles["eng"]))
        # A source from an established campaign is not a starting score.
        vm.state.variables["psf_m_eng_labour_existing_campaign_days"] = 19
        memberships = {key: value for key, value in vm.state.variables.items() if key.startswith("psf_a_")}
        vm.run_effect("psf_initialize")
        self.assertEqual(vm.state.variables[runtime.gv(group["id"], "position_" + axis)], group["positions"][axis])
        self.assertEqual(vm.state.variables[runtime.gv(group["id"], "status")], 0)
        self.assertEqual(vm.state.variables[runtime.gv(group["id"], "support")], 0)
        self.assertEqual(vm.state.variables["psf_m_eng_labour_existing_campaign_days"], 19)
        self.assertEqual({key: vm.state.variables[key] for key in memberships}, memberships)
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_initialize")
        self.assertEqual(vm.state.variables, before)


if __name__ == "__main__":
    unittest.main()
