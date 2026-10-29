from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from psf.compiler import compile_manifest, descriptor, pack
from psf.model import ManifestError
from psf.localization import write_localization
from psf.script import quoted

ROOT = Path(__file__).resolve().parents[1]


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temporary.name)
        cls.output = cls.base / "dist"
        cls.report = compile_manifest(ROOT / "examples/vanilla/manifest.json", cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_two_installable_mods_have_explicit_dependency(self):
        self.assertTrue((self.output / "psf" / "descriptor.mod").is_file())
        self.assertIn('dependencies={ "Political Society Framework" }', (self.output / "psf_vanilla_example" / "descriptor.mod").read_text())
        self.assertIn('path="mod/psf"', (self.output / "psf.mod").read_text())

    def test_launcher_version_is_optional_and_engine_compatible(self):
        self.assertNotIn("supported_version", descriptor("Example"))
        self.assertIn('supported_version="1.19.*"', descriptor("Example", supported_version="1.19.*"))
        for invalid in ("1.*", "*", "1.19", '1.19.*"\npath="elsewhere'):
            with self.subTest(version=invalid), self.assertRaisesRegex(ValueError, "supported_version"):
                descriptor("Example", supported_version=invalid)

    def test_entire_runtime_is_below_semantic_discovery_limit(self):
        chunks = list((self.output / "psf_vanilla_example/common/scripted_effects").glob("10_psf_registry_*.txt"))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(p.stat().st_size < 1_000_000 for p in chunks))
        source = "\n".join(p.read_text() for p in sorted(chunks))
        self.assertIn("psf_initialize = {", source)
        self.assertIn("psf_activate_group = {", source)

    def test_rebuild_is_byte_reproducible(self):
        other = self.base / "again"
        report = compile_manifest(ROOT / "examples/vanilla/manifest.json", other)
        self.assertEqual(self.report["files"], report["files"])
        self.assertEqual((self.output / "build-manifest.json").read_bytes(), (other / "build-manifest.json").read_bytes())

    def test_localization_has_engine_bom_and_language_header(self):
        for p in self.output.glob("*/localisation/*/*.yml"):
            data = p.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbfl_"), p)
        self.assertEqual(quoted('a"b\nc'), '"a\\"b\\nc"')

    def test_multibyte_localization_splits_without_losing_entries(self):
        root = self.base / "localization-chunks"
        values = {"key_" + str(i): "政治团体的修正说明" * 3 for i in range(30)}
        write_localization(root, "chunked", {"simp_chinese": values}, max_bytes=350)
        paths = sorted(root.rglob("*.yml"))
        self.assertGreater(len(paths), 1)
        lines = []
        for path in paths:
            self.assertLessEqual(path.stat().st_size, 350)
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            header, *entries = path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(header, "l_simp_chinese:")
            lines.extend(entries)
        self.assertEqual(sorted(lines), sorted(" " + key + ":0 " + quoted(value) for key, value in values.items()))

    def test_all_generated_script_definitions_fit_discovery_budget(self):
        for path in self.output.glob("*/common/**/*.txt"):
            self.assertLess(path.stat().st_size, 1_000_000, path)
        for path in self.output.glob("*/localisation/**/*.yml"):
            self.assertLess(path.stat().st_size, 1_000_000, path)

    def test_archive_rejects_changed_build_and_has_launcher_entries(self):
        archive = self.base / "pack.zip"
        pack(self.output, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertIn("psf.mod", z.namelist())
            self.assertIn("psf_vanilla_example/descriptor.mod", z.namelist())
        altered = self.base / "tampered"
        compile_manifest(ROOT / "examples/vanilla/manifest.json", altered)
        (altered / "psf.mod").write_text("invalid")
        with self.assertRaisesRegex(ValueError, "Build changed"):
            pack(altered, self.base / "invalid.zip")

    def test_compile_will_not_overwrite_its_own_sources(self):
        with self.assertRaisesRegex(ValueError, "overwrite authoring source"):
            compile_manifest(ROOT / "examples/vanilla/manifest.json", ROOT)

    def test_invalid_manifest_preserves_previous_build(self):
        bad = self.base / "invalid.json"
        bad.write_text('{"schema_version":"1.0"}')
        original = (self.output / "psf.mod").read_bytes()
        with self.assertRaises(ManifestError):
            compile_manifest(bad, self.output)
        self.assertEqual(original, (self.output / "psf.mod").read_bytes())


if __name__ == "__main__":
    unittest.main()
