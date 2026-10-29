"""Integration of authored choices, native hooks and compiled modifier APIs."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hoi4_interpreter import Interpreter, State, entries, mapping, parse
from psf.compiler import compile_manifest
from psf.model import load, profiles, stable_id

REPO = Path(__file__).resolve().parents[1]


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

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def vm(self, profile: str) -> Interpreter:
        vm = Interpreter(State(tag=self.profile_map[profile]["tag"]))
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


if __name__ == "__main__":
    unittest.main()
