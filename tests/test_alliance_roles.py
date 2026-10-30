"""Execute playable coalition workshop and reversible agreement policies."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from examples.coalitions.build import build, workshop_manifest
from hoi4_interpreter import Interpreter, State, entries, mapping, parse
from psf import model, runtime


class AllianceRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        build(cls.root)
        cls.manifest = model.normalize(workshop_manifest())
        cls.profile = cls.manifest["profiles"][0]
        cls.loaded = Interpreter().load((cls.root / "psf", cls.root / cls.manifest["id"]))
        cls.alliances = {a["id"]: a for a in cls.profile["alliances"]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def vm(self):
        vm = Interpreter(State(tag="GER"))
        vm.effects, vm.triggers = self.loaded.effects, self.loaded.triggers
        vm.dynamic_definitions = self.loaded.dynamic_definitions
        vm.run_effect("psf_init_workshop")
        return vm

    def test_independent_cabinet_keeps_all_three_alliances_and_identity(self):
        vm = self.vm()
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
        self.assertEqual(vm.state.variables["psf_governing_group"], model.stable_id("ws_civic"))
        for aid in self.alliances:
            self.assertEqual(vm.state.variables[runtime.av(aid, "active")], 1)
        self.assertEqual(vm.state.cosmetic_tag, "PSF_WS_CIVIC_IDENTITY")
        self.assertEqual(len(self.alliances), 3)

    def test_role_change_retains_members_and_cohesion_and_updates_electoral_status(self):
        vm = self.vm()
        aid = "ws_labor_front"
        before = {runtime.av(aid, "g_" + g["id"]): vm.state.variables[runtime.av(aid, "g_" + g["id"])]
                  for g in self.profile["groups"]}
        cohesion = vm.state.variables[runtime.av(aid, "cohesion")]
        revision = vm.state.variables["psf_ui_revision"]
        vm.run_effect(f"psf_set_{aid}_role_electoral")
        self.assertEqual(vm.state.variables[runtime.av(aid, "role")], model.ROLES["electoral"])
        self.assertEqual(vm.state.variables[runtime.av(aid, "electoral")], 1)
        self.assertGreater(vm.state.variables["psf_ui_revision"], revision)
        vm.run_effect(f"psf_set_{aid}_role_opposition")
        self.assertEqual(vm.state.variables[runtime.av(aid, "role")], model.ROLES["opposition"])
        self.assertEqual(vm.state.variables[runtime.av(aid, "electoral")], 0)
        self.assertEqual(vm.state.variables[runtime.av(aid, "cohesion")], cohesion)
        self.assertEqual({name: vm.state.variables[name] for name in before}, before)
        self.assertEqual(vm.state.variables["psf_governing_group"], model.stable_id("ws_civic"))

    def test_pact_role_changes_next_election_result(self):
        first, second = self.vm(), self.vm()
        # Disable the starting joint list, then give the Labour/Industry pact
        # a civic partner. The non-electoral council contributes no extra vote.
        for vm in (first, second):
            vm.run_effect("psf_set_ws_electoral_pact_role_opposition")
            vm.run_effect("psf_join_ws_labor_front_ws_civic")
        first.run_effect("psf_set_ws_labor_front_role_electoral")
        first.run_effect("psf_hold_election_workshop")
        second.run_effect("psf_hold_election_workshop")
        self.assertEqual(first.state.variables["psf_governing_alliance"], self.alliances["ws_labor_front"]["_index"])
        self.assertEqual(second.state.variables["psf_governing_alliance"], 0)
        self.assertEqual(second.state.variables["psf_governing_group"], model.stable_id("ws_civic"))

    def test_government_and_cross_country_guards_and_full_membership_lifecycle(self):
        vm = self.vm()
        vm.run_effect("psf_govern_ws_reform")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_WS_COALITION_IDENTITY")
        vm.run_effect("psf_set_ws_reform_role_electoral")
        self.assertEqual(vm.state.variables[runtime.av("ws_reform", "role")], model.ROLES["government"])
        vm.run_effect("psf_govern_group_ws_civic")
        vm.run_effect("psf_set_ws_reform_role_electoral")
        self.assertEqual(vm.state.variables[runtime.av("ws_reform", "electoral")], 1)
        vm.run_effect("psf_leave_ws_reform_ws_civic")
        vm.run_effect("psf_dissolve_ws_reform")
        self.assertEqual(vm.state.variables[runtime.av("ws_reform", "active")], 0)
        vm.run_effect("psf_join_ws_reform_ws_local")
        self.assertEqual(vm.state.variables[runtime.av("ws_reform", "active")], 1)
        for aid in ("ws_labor_front", "ws_electoral_pact"):
            self.assertEqual(vm.state.variables[runtime.av(aid, "active")], 1)
        vm.state.flags.remove("psf_profile_workshop")
        previous = dict(vm.state.variables)
        vm.run_effect("psf_set_ws_labor_front_role_electoral")
        self.assertEqual(vm.state.variables, previous)

    def test_release_restore_and_identity_free_profile_preserve_native_appearance(self):
        vm = self.vm()
        vm.run_effect("psf_release_identity")
        self.assertIsNone(vm.state.cosmetic_tag)
        vm.run_effect("psf_refresh")
        self.assertIsNone(vm.state.cosmetic_tag)
        vm.run_effect("psf_resume_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_WS_CIVIC_IDENTITY")
        vm = Interpreter(State(tag="ZZZ", cosmetic_tag="EXTERNAL_FORMABLE"))
        vm.effects, vm.triggers = self.loaded.effects, self.loaded.triggers
        vm.dynamic_definitions = self.loaded.dynamic_definitions
        vm.run_effect("psf_init_" + self.manifest["fallback_profiles"][0]["id"])
        vm.run_effect("psf_release_identity")
        self.assertEqual(vm.state.cosmetic_tag, "EXTERNAL_FORMABLE")

    def test_generated_decisions_execute_the_same_public_role_api(self):
        content = self.root / self.manifest["id"]
        choices = {}
        for path in (content / "common/decisions").glob("*.txt"):
            for category in entries(parse(path.read_text())):
                choices.update({entry.key: entry.value for entry in entries(category.value)})
        vm = self.vm()
        choice = mapping(choices["psf_policy_ws_labor_front_role_electoral"])
        vm.execute(choice["complete_effect"])
        self.assertEqual(vm.state.variables[runtime.av("ws_labor_front", "electoral")], 1)


if __name__ == "__main__":
    unittest.main()
