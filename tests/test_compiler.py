from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from psf.compiler import compile_manifest, pack
from psf.model import ManifestError
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
