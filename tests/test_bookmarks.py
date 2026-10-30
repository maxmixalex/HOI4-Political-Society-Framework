"""Front-end previews preserve native bindings and original bookmark content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unicodedata
import unittest

from psf.bookmarks import (LABEL_COLUMNS, TEXT_ICON_SIZE, _compact_label, _history_text,
                           fields, generate_bookmark_previews)
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

    def test_entire_native_bookmark_structure_survives_except_history_keys(self):
        original_by_key = {entry["history_key"]: entry["original_history_key"] for entry in self.report["previews"]}

        def semantic_tree(nodes, restore=False):
            return tuple((node.key, semantic_tree(node.value, restore) if isinstance(node.value, tuple)
                          else original_by_key.get(node.value, node.value) if restore else node.value)
                         for node in nodes)

        for filename, source_hash in self.report["source_files"].items():
            source = ROOT / "psf/assets/native_bookmarks" / Path(filename).name
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
            actual = self.output / filename
            self.assertFalse(actual.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(semantic_tree(fields(source.read_text())), semantic_tree(fields(actual.read_text()), True))

    def test_wrappers_use_text_icons_and_preserve_original_localisation(self):
        for language in ("english", "simp_chinese"):
            path = self.output / "localisation" / language / f"psf_bookmarks_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for preview in self.report["previews"]:
                self.assertIn(f" {preview['history_key']}:0 ", text)
                self.assertIn(f"${preview['original_history_key']}$", text)
                for row in preview["rows"]:
                    self.assertIn(f"£{row['sprite'].removeprefix('GFX_')}£", text)
                    self.assertIn(f"{row['support']:.1f}% / {row['influence']:.1f}%", text)
                self.assertNotIn(f" {preview['original_history_key']}:0 ", text)
        definitions = (self.output / "interface/psf_bookmarks.gfx").read_text()
        self.assertIn("legacy_lazy_load = no", definitions)

    def test_1939_preview_applies_the_same_start_overrides_as_runtime(self):
        previews = {p["date"]: p for p in self.report["previews"] if p["tag"] == "GER"}
        early, late = previews["1936.1.1.12"], previews["1939.8.14.12"]
        self.assertAlmostEqual(early["support"]["ger_nsdap"], 52.5)
        self.assertAlmostEqual(late["support"]["ger_nsdap"], 52 / 90 * 100)
        self.assertNotEqual(early["influence"], late["influence"])
        self.assertNotEqual(_history_text(early, "ORIGINAL_HISTORY", "english"),
                            _history_text(late, "ORIGINAL_HISTORY", "english"))
        early_rows, late_rows = ({row["group"]: row for row in preview["rows"]} for preview in (early, late))
        self.assertNotEqual(early_rows["ger_nsdap"]["support"], late_rows["ger_nsdap"]["support"])
        self.assertEqual(early_rows["ger_nsdap"]["sprite"], late_rows["ger_nsdap"]["sprite"])

    def test_dlc_variants_keep_their_original_gates_and_share_correct_snapshot(self):
        variants = [p for p in self.report["previews"] if p["tag"] == "GER" and p["date"] == "1936.1.1.12"]
        self.assertEqual({p["version"] for p in variants}, {"base_game", "gotterdammerung"})
        self.assertEqual(len({p["snapshot"] for p in variants}), 1)
        text = (self.output / "common/bookmarks/the_gathering_storm.txt").read_text()
        self.assertIn('required_dlc = { "Gotterdammerung" }', text)
        self.assertIn('available = { NOT = { has_dlc = "Gotterdammerung" } }', text)

    def test_empty_country_registry_does_not_override_native_bookmarks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = generate_bookmark_previews(load(ROOT / "examples/minimal/manifest.json"), output)
            self.assertEqual(report["previews"], [])
            self.assertFalse((output / "common/bookmarks").exists())

    def test_snapshot_provenance_is_included(self):
        source = ROOT / "psf/assets/native_bookmarks"
        report = json.loads((source / "sources.json").read_text())
        for filename, metadata in report["files"].items():
            self.assertEqual(hashlib.sha256((source / filename).read_bytes()).hexdigest(), metadata["sha256"])
        self.assertIn("Paradox", report["copyright"])

    def test_every_frontend_image_fits_one_text_row_with_exact_identity_color(self):
        textures = {}
        for preview in self.report["previews"]:
            for row in preview["rows"]:
                textures[row["texture"]] = row
                self.assertEqual(row["support"], preview["support"][row["group"]])
                self.assertEqual(row["influence"], preview["influence"][row["group"]])
        self.assertEqual(len(textures), self.report["unique_text_icons"])
        self.assertLessEqual(TEXT_ICON_SIZE, 16)
        for texture, row in textures.items():
            data = (self.output / texture).read_bytes()
            self.assertEqual(struct.unpack_from("<HH", data, 12), (12, 12))
            r, g, b = row["color"]
            self.assertEqual(data[18:], bytes((b, g, r, 255)) * 144)
        # The defective 140x63 inline charts are no longer shipped or referenced
        # by the history adapter; campaign GUI pies are unaffected.
        self.assertEqual(len(list((self.output / "gfx/interface/psf/bookmarks").rglob("*.tga"))), len(textures))

    def test_each_organization_occupies_one_native_text_line_and_history_stays_separate(self):
        for preview in self.report["previews"]:
            for language in ("english", "simp_chinese"):
                text = _history_text(preview, "ORIGINAL_HISTORY", language)
                lines = text.splitlines()
                self.assertEqual(len(lines), len(preview["rows"]) + 3)
                self.assertEqual(lines[-2:], ["", "$ORIGINAL_HISTORY$"])
                for row, line in zip(preview["rows"], lines[1:-2]):
                    self.assertEqual(line.count("£"), 2)
                    self.assertEqual(line.count("%"), 2)
                    self.assertIn(row["labels"][language], line)

    def test_unusually_long_or_multiline_names_cannot_push_values_outside_the_label_budget(self):
        for label in ("Very long organization " * 20, "政治团体名称" * 20, "A\nB\tC"):
            group = {"name": {"english": label, "simp_chinese": label}}
            compact = _compact_label(group, "english")
            columns = sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in compact)
            self.assertLessEqual(columns, LABEL_COLUMNS)
            self.assertNotIn("\n", compact)
            self.assertNotIn("\t", compact)

    def test_zero_total_snapshot_has_explicit_empty_state_and_keeps_original_prose(self):
        self.assertEqual(_history_text({"rows": []}, "HISTORY", "english"),
                         "Support / Influence\nNo active organizations\n\n$HISTORY$")


if __name__ == "__main__":
    unittest.main()
