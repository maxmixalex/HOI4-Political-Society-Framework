"""Strict native adapters preserve script identity and replace mechanics."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from hoi4_interpreter import entries, parse
from psf import mechanics, model
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
            self.assertEqual(len(report["files"]), 3)
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


if __name__ == "__main__":
    unittest.main()
