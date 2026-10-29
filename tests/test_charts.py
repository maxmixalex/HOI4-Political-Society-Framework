"""Execute the emitted pie-cache scripts, including zero and changed totals."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import random
import struct
import tempfile
import unittest

from hoi4_interpreter import Interpreter, entries, parse
from psf import charts
from psf.script import emit


class ChartRuntimeTests(unittest.TestCase):
    def vm(self):
        profile = {"id": "test", "groups": [
            {"id": "alpha", "kind": "party", "electoral": True},
            {"id": "union", "kind": "trade_union", "electoral": False},
            {"id": "beta", "kind": "party", "electoral": True},
        ]}
        manifest = {"profiles": [profile], "fallback_profiles": []}
        vm = Interpreter()
        vm.effects = {entry.key: entry.value for entry in entries(parse(emit([charts.refresh_effect(manifest, profile)])))}
        for group in profile["groups"]:
            for field, value in (("status", 1), ("modified_support", 0), ("effective_influence", 0)):
                vm.state.variables[f"psf_g_{group['id']}_{field}"] = value
        return vm

    def test_support_excludes_overlapping_civil_approval_and_influence_includes_it(self):
        vm = self.vm()
        vm.state.variables.update({
            "psf_g_alpha_modified_support": 30, "psf_g_beta_modified_support": 70,
            "psf_g_union_modified_support": 100,
            "psf_g_alpha_effective_influence": 20, "psf_g_union_effective_influence": 80,
        })
        vm.run_effect("psf_update_charts_test")
        self.assertEqual(Counter(vm.state.arrays["psf_pie_support_frames"]), {2: 54, 4: 126})
        self.assertEqual(Counter(vm.state.arrays["psf_pie_influence_frames"]), {2: 36, 3: 144})
        self.assertEqual(vm.state.variables["psf_g_union_support_share"], 0)
        self.assertEqual(vm.state.variables["psf_g_union_influence_share"], 80)
        self.assertFalse(vm.state.undefined_reads)

    def test_zero_and_inactive_totals_clear_stale_slices_without_division_by_zero(self):
        vm = self.vm()
        vm.state.variables["psf_g_alpha_modified_support"] = 100
        vm.state.variables["psf_g_alpha_effective_influence"] = 100
        vm.run_effect("psf_update_charts_test")
        self.assertEqual(vm.state.arrays["psf_pie_support_frames"], [2] * charts.SECTORS)
        vm.state.variables["psf_g_alpha_status"] = 0
        vm.run_effect("psf_update_charts_test")
        for metric in ("support", "influence"):
            self.assertEqual(vm.state.arrays[f"psf_pie_{metric}_frames"], [1] * charts.SECTORS)
            self.assertEqual(vm.state.variables[f"psf_g_alpha_{metric}_share"], 0)

    def test_changed_modifiers_and_suppression_refresh_the_complete_circle(self):
        vm = self.vm()
        vm.state.variables.update({"psf_g_alpha_modified_support": 50, "psf_g_beta_modified_support": 50,
                                   "psf_g_alpha_effective_influence": 50, "psf_g_beta_effective_influence": 50})
        vm.run_effect("psf_update_charts_test")
        vm.state.variables.update({"psf_g_alpha_modified_support": 75, "psf_g_beta_modified_support": 25,
                                   "psf_g_beta_status": 3, "psf_g_beta_effective_influence": 6})
        vm.run_effect("psf_update_charts_test")
        self.assertEqual(Counter(vm.state.arrays["psf_pie_support_frames"]), {2: 135, 4: 45})
        self.assertEqual(len(vm.state.arrays["psf_pie_influence_frames"]), charts.SECTORS)
        self.assertNotIn(1, vm.state.arrays["psf_pie_influence_frames"])
        self.assertLess(vm.state.variables["psf_g_beta_influence_share"], 11)

    def test_fractional_weights_cover_all_sectors_and_preserve_order(self):
        rng = random.Random(280)
        for _ in range(20):
            vm = self.vm()
            a, b = rng.uniform(.01, 100), rng.uniform(.01, 100)
            vm.state.variables["psf_g_alpha_modified_support"] = a
            vm.state.variables["psf_g_beta_modified_support"] = b
            vm.run_effect("psf_update_charts_test")
            slices = vm.state.arrays["psf_pie_support_frames"]
            self.assertEqual(len(slices), charts.SECTORS)
            self.assertNotIn(1, slices)
            self.assertEqual(slices, sorted(slices))
            self.assertLessEqual(abs(slices.count(2) - charts.SECTORS * a / (a + b)), .5 + 1e-8)

    def test_native_bookmark_icons_apply_the_selected_start_date(self):
        profile = {"id": "test", "groups": [
            {"id": "alpha", "status": "legal", "electoral": True, "support": 80, "influence": 20},
            {"id": "beta", "status": "legal", "electoral": True, "support": 20, "influence": 80}],
            "start_overrides": [{"date": "1939.1.1", "groups": [
                {"id": "alpha", "support": 20}, {"id": "beta", "support": 80, "status": "banned"}]}]}
        manifest = {"profiles": [profile], "settings": {"banned_influence_factor": .1}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            early = charts.bookmark_artwork(manifest, profile, "1936.1.1", root)
            late = charts.bookmark_artwork(manifest, profile, "1939.8.14", root)
            self.assertEqual(early["support"], {"alpha": 80, "beta": 20})
            self.assertEqual(late["support"], {"alpha": 20, "beta": 80})
            self.assertAlmostEqual(late["influence"]["beta"], 100 * 8 / 28)
            first, second = (root / item["texture"] for item in (early, late))
            self.assertNotEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(struct.unpack_from("<HH", second.read_bytes(), 12), (140, 63))
            self.assertEqual(len(second.read_bytes()), 18 + 140 * 63 * 4)
            self.assertEqual(profile["groups"][0]["support"], 80)


if __name__ == "__main__":
    unittest.main()
