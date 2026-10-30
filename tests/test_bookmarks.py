"""Independent frontend politics preserve original bookmark content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from psf import frontend
from psf.bookmarks import fields, generate_bookmark_previews
from psf.model import load

ROOT = Path(__file__).resolve().parents[1]


class BookmarkPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name)
        cls.manifest = load(ROOT / "examples/vanilla/manifest.json")
        cls.report = generate_bookmark_previews(cls.manifest, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_all_declared_countries_and_both_dates_have_previews(self):
        self.assertEqual(self.report["covered_countries"], sorted(p["tag"] for p in self.manifest["profiles"]))
        self.assertEqual(self.report["unique_snapshots"], 20)
        self.assertEqual(len(self.report["previews"]), 28)
        self.assertEqual(self.report["unrepresented_profiles"], [])
        self.assertIn("BEL", self.report["untouched_countries"])
        self.assertFalse(self.report["runtime_render_tested"])

    def test_no_native_bookmark_or_history_localisation_is_overridden(self):
        self.assertFalse((self.output / "common/bookmarks").exists())
        self.assertFalse((self.output / "interface/psf_bookmarks.gfx").exists())
        self.assertFalse(self.report["history_overridden"])
        for preview in self.report["previews"]:
            self.assertEqual(preview["history_key"], preview["original_history_key"])
        for path in self.output.rglob("*.yml"):
            text = path.read_text(encoding="utf-8-sig")
            self.assertNotIn("psf_bookmark_history_", text)
            for preview in self.report["previews"]:
                self.assertNotIn(f" {preview['original_history_key']}:0 ", text)
                self.assertNotIn("$" + preview["original_history_key"] + "$", text)

    def test_frontend_presentations_have_separate_real_dual_pies(self):
        states = self.report["frontend"]["states"]
        self.assertEqual(self.report["compiled_states"], len(states))
        self.assertGreaterEqual(len(states), len(self.manifest["profiles"]) + len(self.manifest["fallback_profiles"]))
        definitions = (self.output / "interface/psf_frontend.gfx").read_text()
        self.assertEqual(definitions.count("legacy_lazy_load = no"), len(states))
        for item in states:
            data = (self.output / item["texture"]).read_bytes()
            self.assertEqual(struct.unpack_from("<HH", data, 12), (140, 63))
            self.assertIn(item["sprite"], definitions)
            self.assertEqual(len(data), 18 + 140 * 63 * 4)
            for language in ("english", "simp_chinese"):
                path = self.output / "localisation" / language / f"psf_frontend_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertIn(f" {item['panel_key']}:0 ", path.read_text(encoding="utf-8-sig"))

    def test_1939_previews_apply_the_same_start_overrides_as_runtime(self):
        previews = {p["date"]: p for p in self.report["previews"] if p["tag"] == "GER"}
        early, late = previews["1936.1.1.12"], previews["1939.8.14.12"]
        self.assertAlmostEqual(early["support"]["ger_nsdap"], 52.5)
        self.assertAlmostEqual(late["support"]["ger_nsdap"], 52 / 90 * 100)
        self.assertNotEqual(early["influence"], late["influence"])
        self.assertNotEqual(early["panel_key"], late["panel_key"])
        self.assertEqual(early["ruling_group"], "ger_nsdap")
        self.assertEqual(late["ruling_group"], "ger_nsdap")

    def test_dlc_variants_share_the_correct_politics_and_keep_native_history(self):
        variants = [p for p in self.report["previews"] if p["tag"] == "GER" and p["date"] == "1936.1.1.12"]
        self.assertEqual({p["version"] for p in variants}, {"base_game", "gotterdammerung"})
        self.assertEqual(len({p["snapshot"] for p in variants}), 1)
        self.assertEqual(len({p["panel_key"] for p in variants}), 1)
        source = ROOT / "psf/assets/native_bookmarks/the_gathering_storm.txt"
        text = source.read_text()
        self.assertIn('required_dlc = { "Gotterdammerung" }', text)
        self.assertIn('available = { NOT = { has_dlc = "Gotterdammerung" } }', text)
        self.assertTrue(fields(text))

    def test_empty_country_registry_still_compiles_fallback_politics_without_bookmark_overrides(self):
        manifest = load(ROOT / "examples/minimal/manifest.json")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = generate_bookmark_previews(manifest, output)
            self.assertEqual(report["previews"], [])
            self.assertFalse((output / "common/bookmarks").exists())
            self.assertEqual(report["compiled_states"], sum(len(frontend.states(p)) for p in manifest["fallback_profiles"]))

    def test_snapshot_provenance_includes_every_unmodified_native_source(self):
        source = ROOT / "psf/assets/native_bookmarks"
        for filename, digest in self.report["source_files"].items():
            self.assertEqual(hashlib.sha256((source / Path(filename).name).read_bytes()).hexdigest(), digest)
        provenance = json.loads((source / "sources.json").read_text())
        for filename, metadata in provenance["files"].items():
            self.assertEqual(hashlib.sha256((source / filename).read_bytes()).hexdigest(), metadata["sha256"])
        self.assertIn("Paradox", provenance["copyright"])


if __name__ == "__main__":
    unittest.main()
