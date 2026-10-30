"""Integration of authored choices, native hooks and compiled modifier APIs."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hoi4_interpreter import Interpreter, State, entries, mapping, parse
from psf.compiler import compile_manifest
from psf.model import load, profiles, stable_id

REPO = Path(__file__).resolve().parents[1]
MANDATE_SOURCES = {"independent_executive_mandate", "negotiated_governing_support", "caretaker_assurances"}


class ContentInterpreter(Interpreter):
    """Provide an explicit external game-rule value to the emitted scheduler."""
    examples_enabled = True

    def trigger(self, node):
        if node.key == "has_game_rule":
            request = mapping(node.value)
            if request != {"rule": "psf_content_events", "option": "ENABLED"}:
                raise AssertionError(f"Unexpected game-rule lookup: {request}")
            return self.examples_enabled
        return super().trigger(node)


class CompiledContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name)
        cls.manifest = load(REPO / "examples/vanilla/manifest.json")
        compile_manifest(REPO / "examples/vanilla/manifest.json", cls.output)
        cls.roots = (cls.output / "psf", cls.output / cls.manifest["id"])
        loaded = Interpreter().load(cls.roots)
        cls.effects, cls.triggers = loaded.effects, loaded.triggers
        cls.profile_map = {p["id"]: p for p in profiles(cls.manifest)}
        event_source = (cls.roots[1] / "events/psf_events.txt").read_text()
        cls.events = {str(mapping(event.value)["id"]): event.value
                      for event in entries(parse(event_source)) if event.key == "country_event"}
        on_actions = mapping(parse((cls.roots[1] / "common/on_actions/psf_on_actions.txt").read_text()))
        cls.daily = mapping(mapping(on_actions["on_actions"])["on_daily"])["effect"]
        cls.weekly = mapping(mapping(on_actions["on_actions"])["on_weekly"])["effect"]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def vm(self, profile: str) -> Interpreter:
        vm = ContentInterpreter(State(tag=self.profile_map[profile]["tag"]))
        vm.effects, vm.triggers = self.effects, self.triggers
        vm.run_effect("psf_init_" + profile)
        return vm

    def test_every_new_negotiation_option_executes_its_named_source(self):
        scenarios = [s for s in self.manifest["scenarios"] if s["id"].endswith("_modifier_agreement")]
        self.assertEqual({s["profile"] for s in scenarios}, set(p["id"] for p in self.manifest["profiles"]))
        for scenario in scenarios:
            event = self.events["psf_content." + str(stable_id(scenario["id"]))]
            options = [o for o in entries(event) if o.key == "option"]
            for authored, emitted in zip(scenario["options"], options, strict=True):
                with self.subTest(scenario=scenario["id"], choice=authored["id"]):
                    vm = self.vm(scenario["profile"])
                    vm.executed = 0
                    vm.execute(tuple(e for e in entries(emitted.value) if e.key not in {"name", "ai_chance"}))
                    for op in authored["effects"]:
                        variable = f"psf_m_{op['group']}_{op['modifier']}_active"
                        self.assertEqual(vm.state.variables[variable], 1)
                    self.assertNotIn("psf_batch_update", vm.state.flags)

    def test_compiled_daily_hook_updates_one_country_exactly_once(self):
        vm = self.vm("eng")
        base = "psf_g_eng_tuc_influence"
        original = vm.state.variables[base]
        vm.run_effect("psf_add_eng_tuc_modifier_labor_compact")
        vm.executed = 0
        vm.state.temporary.clear()
        vm.execute(self.daily)
        self.assertAlmostEqual(vm.state.variables[base], original + 0.02)
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_labor_compact_days"], 89)
        self.assertNotIn("psf_g_ger_spd_support", vm.state.variables)

    def test_named_sources_cover_every_authored_axis(self):
        affected = {axis for source in self.manifest["modifiers"] for axis in source.get("positions", {})}
        self.assertEqual(affected, {a["id"] for a in self.manifest["axes"]})
        durations = {s["duration_days"] for s in self.manifest["modifiers"]}
        self.assertIn(-1, durations)
        self.assertTrue(any(d > 0 for d in durations))

    def late_vm(self, profile: str) -> Interpreter:
        vm = ContentInterpreter(State(tag=self.profile_map[profile]["tag"], date=(1939, 8, 14)))
        vm.effects, vm.triggers = self.effects, self.triggers
        vm.run_effect("psf_init_" + profile)
        return vm

    def coordination_scenarios(self):
        return [s for s in self.manifest["scenarios"] if s["id"].endswith("_coordination_settlement")]

    def mandate_scenarios(self):
        return [s for s in self.manifest["scenarios"] if s["id"].endswith("_government_mandate")]

    def execute_option(self, vm, scenario, choice):
        event = self.events["psf_content." + str(stable_id(scenario["id"]))]
        options = [o for o in entries(event) if o.key == "option"]
        vm.executed = 0
        vm.state.temporary.clear()
        vm.execute(tuple(e for e in entries(options[choice].value) if e.key not in {"name", "ai_chance"}))

    def test_late_bookmark_keeps_new_negotiations_and_skips_old_ones(self):
        scenarios = self.coordination_scenarios()
        self.assertEqual({s["profile"] for s in scenarios}, {p["id"] for p in self.manifest["profiles"]})
        for scenario in scenarios:
            with self.subTest(profile=scenario["profile"]):
                vm = self.late_vm(scenario["profile"])
                self.assertNotIn("psf_scenario_" + scenario["id"], vm.state.flags)
                self.assertIn("psf_scenario_" + scenario["profile"] + "_modifier_agreement", vm.state.flags)

    def test_all_thirty_new_choices_execute_and_preserve_organization_identity(self):
        for scenario in self.coordination_scenarios():
            for index, option in enumerate(scenario["options"]):
                with self.subTest(scenario=scenario["id"], choice=option["id"]):
                    vm = self.late_vm(scenario["profile"])
                    alliance = vm.state.variables["psf_governing_alliance"]
                    membership = {k: v for k, v in vm.state.variables.items() if k.startswith("psf_a_") and "_g_" in k}
                    self.execute_option(vm, scenario, index)
                    for operation in option["effects"]:
                        if operation["op"] == "add_modifier":
                            active = f"psf_m_{operation['group']}_{operation['modifier']}_active"
                            self.assertEqual(vm.state.variables[active], 1)
                        elif operation["op"] == "legalize":
                            self.assertEqual(vm.state.variables[f"psf_g_{operation['group']}_status"], 1)
                    self.assertEqual(vm.state.variables["psf_governing_alliance"], alliance)
                    self.assertEqual({k: vm.state.variables[k] for k in membership}, membership)
                    self.assertNotIn("psf_batch_update", vm.state.flags)

    def test_new_settlement_replaces_competing_mandate_without_stacking(self):
        # The strongest adversarial case starts with a centralized mandate,
        # then takes the independent charter. Temporary centralization and
        # exclusion must disappear, while the permanent charter is singular.
        scenario = next(s for s in self.coordination_scenarios() if s["profile"] == "eng")
        vm = self.late_vm("eng")
        self.execute_option(vm, scenario, 1)
        self.assertEqual(vm.state.variables["psf_m_eng_conservative_executive_coordination_active"], 1)
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_excluded_from_consultation_active"], 1)
        self.execute_option(vm, scenario, 2)
        self.assertEqual(vm.state.variables["psf_m_eng_conservative_executive_coordination_active"], 0)
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_excluded_from_consultation_active"], 0)
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_independent_civic_charter_active"], 1)
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_independent_civic_charter_days"], -1)
        influence = vm.state.variables["psf_g_eng_tuc_effective_influence"]
        self.execute_option(vm, scenario, 2)
        self.assertEqual(vm.state.variables["psf_g_eng_tuc_effective_influence"], influence)

    def test_new_council_daily_drift_and_expiry_preserve_accumulated_support(self):
        vm = self.late_vm("eng")
        variable = "psf_g_eng_tuc_support"
        vm.run_effect("psf_add_eng_tuc_modifier_production_council")
        initial = vm.state.variables[variable]
        # One day before expiry proves the actual generated daily hook and
        # removal path, without simulating 180 equivalent daily pulses.
        vm.state.variables["psf_m_eng_tuc_production_council_days"] = 1
        vm.executed = 0
        vm.state.temporary.clear()
        vm.execute(self.daily)
        self.assertAlmostEqual(vm.state.variables[variable], min(100, initial + .015))
        self.assertEqual(vm.state.variables["psf_m_eng_tuc_production_council_active"], 0)
        self.assertEqual(vm.state.variables["psf_g_eng_tuc_modified_support"], vm.state.variables[variable])

    def test_all_thirty_mandates_change_government_and_apply_nonstacking_sources(self):
        scenarios = self.mandate_scenarios()
        self.assertEqual({s["profile"] for s in scenarios}, {p["id"] for p in self.manifest["profiles"]})
        self.assertEqual(sum(len(s["options"]) for s in scenarios), 30)
        source_map = {m["id"]: m for m in self.manifest["modifiers"]}
        for scenario in scenarios:
            profile = self.profile_map[scenario["profile"]]
            groups = {g["id"]: g for g in profile["groups"]}
            pact = next(a for a in profile["alliances"] if a["id"] == profile["id"] + "_executive_agreement")
            self.assertEqual(pact["members"], [])
            self.assertNotEqual(pact["kind"], "government")
            for index, option in enumerate(scenario["options"]):
                with self.subTest(profile=profile["id"], option=option["id"]):
                    vm = self.late_vm(profile["id"])
                    original = {k: v for k, v in vm.state.variables.items()
                                if k.startswith("psf_a_") and "_g_" in k and not k.startswith(f"psf_a_{pact['id']}_")}
                    self.execute_option(vm, scenario, index)
                    self.assertEqual({k: vm.state.variables[k] for k in original}, original)
                    sources = [op for op in option["effects"] if op["op"] == "add_modifier"]
                    for operation in sources:
                        prefix = f"psf_m_{operation['group']}_{operation['modifier']}_"
                        self.assertEqual(vm.state.variables[prefix + "active"], 1)
                        self.assertEqual(vm.state.variables[prefix + "days"], source_map[operation["modifier"]]["duration_days"])
                    if option["id"] == "independent":
                        group = next(op["group"] for op in option["effects"] if op["op"] == "govern_group")
                        self.assertEqual(vm.state.variables["psf_governing_group"], groups[group]["_index"])
                        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
                        self.assertEqual(vm.state.variables["psf_caretaker"], 0)
                    elif option["id"] == "agreement":
                        self.assertEqual(vm.state.variables["psf_governing_alliance"], pact["_index"])
                        self.assertEqual(vm.state.variables["psf_governing_group"], 0)
                        self.assertEqual(vm.state.variables["psf_caretaker"], 0)
                        for operation in (op for op in option["effects"] if op["op"] == "join"):
                            self.assertEqual(vm.state.variables[f"psf_a_{pact['id']}_g_{operation['group']}"], 1)
                            self.assertEqual(vm.state.variables[f"psf_g_{operation['group']}_governing"], 1)
                    else:
                        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
                        self.assertEqual(vm.state.variables["psf_governing_group"], 0)
                        self.assertEqual(vm.state.variables["psf_caretaker"], 1)
                        self.assertFalse(any(vm.state.variables[f"psf_g_{gid}_governing"] for gid in groups))
                    # Re-execute the actual emitted option, not a Python
                    # calculation of its expected bonus. Source replacement
                    # and cabinet APIs must not accumulate repeated gains.
                    keys = [f"psf_g_{op['group']}_{field}" for op in sources
                            for field in ("influence", "satisfaction", "modified_influence", "modified_satisfaction")]
                    once = {key: vm.state.variables[key] for key in keys}
                    self.execute_option(vm, scenario, index)
                    self.assertEqual({key: vm.state.variables[key] for key in keys}, once)
                    self.assertNotIn("psf_batch_update", vm.state.flags)

    def test_new_and_previous_alliances_survive_independent_and_caretaker_governments(self):
        for scenario in self.mandate_scenarios():
            with self.subTest(profile=scenario["profile"]):
                vm = self.late_vm(scenario["profile"])
                self.execute_option(vm, scenario, 1)
                membership = {k: v for k, v in vm.state.variables.items() if k.startswith("psf_a_") and "_g_" in k}
                active = {k: v for k, v in vm.state.variables.items() if k.startswith("psf_a_") and k.endswith("_active")}
                self.assertGreaterEqual(sum(active.values()), 2)
                for choice in (0, 2):
                    self.execute_option(vm, scenario, choice)
                    self.assertEqual({k: vm.state.variables[k] for k in membership}, membership)
                    self.assertEqual({k: vm.state.variables[k] for k in active}, active)
                active_sources = {mid for mid in MANDATE_SOURCES for g in self.profile_map[scenario["profile"]]["groups"]
                                  if vm.state.variables.get(f"psf_m_{g['id']}_{mid}_active", 0)}
                self.assertEqual(active_sources, {"caretaker_assurances"})

    def test_mandates_reactivate_dormant_early_bookmark_participants_explicitly(self):
        for profile, group, choice in (("spr", "spr_unification", 0), ("pol", "pol_ozon", 1)):
            with self.subTest(profile=profile):
                vm = self.vm(profile)
                self.assertEqual(vm.state.variables[f"psf_g_{group}_status"], 0)
                vm.state.date = (1939, 9, 2)
                scenario = next(s for s in self.mandate_scenarios() if s["profile"] == profile)
                self.execute_option(vm, scenario, choice)
                self.assertEqual(vm.state.variables[f"psf_g_{group}_status"], 1)
                self.assertEqual(vm.state.variables[f"psf_g_{group}_governing"], 1)
                self.assertGreater(vm.state.variables[f"psf_g_{group}_effective_influence"], 0)

    def test_late_bookmark_and_weekly_rule_preserve_and_dispatch_each_mandate_once(self):
        for scenario in self.mandate_scenarios():
            with self.subTest(profile=scenario["profile"]):
                self.assertEqual(scenario["date"], "1939.9.1")
                vm = self.late_vm(scenario["profile"])
                marker = "psf_scenario_" + scenario["id"]
                self.assertNotIn(marker, vm.state.flags)
                for day, enabled in (((1939, 8, 14), True), ((1939, 9, 1), True), ((1939, 9, 2), False)):
                    vm.state.date, vm.examples_enabled = day, enabled
                    vm.executed = 0
                    vm.execute(self.weekly)
                    self.assertNotIn(marker, vm.state.flags)
                    self.assertFalse(any(name == "country_event" for name, _ in vm.state.callbacks))
                vm.examples_enabled = True
                for _ in range(2):
                    vm.executed = 0
                    vm.execute(self.weekly)
                self.assertIn(marker, vm.state.flags)
                delivered = [mapping(body)["id"] for name, body in vm.state.callbacks if name == "country_event"]
                self.assertEqual(delivered, ["psf_content." + str(stable_id(scenario["id"]))])

    def test_expired_mandate_removes_bonus_without_dissolving_the_government(self):
        scenario = next(s for s in self.mandate_scenarios() if s["profile"] == "eng")
        vm = self.late_vm("eng")
        self.execute_option(vm, scenario, 0)
        group = "eng_conservative"
        base = vm.state.variables[f"psf_g_{group}_influence"]
        government = vm.state.variables["psf_governing_group"]
        self.assertGreater(vm.state.variables[f"psf_g_{group}_modified_influence"], base)
        vm.state.variables[f"psf_m_{group}_independent_executive_mandate_days"] = 1
        vm.executed = 0
        vm.execute(self.daily)
        self.assertEqual(vm.state.variables[f"psf_m_{group}_independent_executive_mandate_active"], 0)
        self.assertEqual(vm.state.variables[f"psf_g_{group}_modified_influence"], base)
        self.assertEqual(vm.state.variables["psf_governing_group"], government)


if __name__ == "__main__":
    unittest.main()
