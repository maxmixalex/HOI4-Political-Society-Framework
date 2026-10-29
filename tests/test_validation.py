"""Regression coverage for loader failures that semantic CWTools misses."""
from __future__ import annotations

from pathlib import Path
from contextlib import redirect_stderr
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from psf.compiler import compile_manifest
from tools.ci.engine_safety import MAX_SCRIPT_BYTES, UTF8_BOM, file_findings, gui_windows, inspect_build
from tools.ci.validate import main as validate

ROOT = Path(__file__).resolve().parents[1]


class EngineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def codes(self, path: Path) -> set[str]:
        return {finding["code"] for finding in file_findings(path)}

    def test_bom_is_rejected_before_tolerant_text_decoding(self):
        examples = {
            "interface/frontendgamesetupview.gui": b'guiTypes = { containerWindowType = { name = "frontendgamesetupview" } }',
            "interface/psf_society.gfx": b"spriteTypes = {}",
            "common/scripted_effects/psf.txt": b"psf_test = {}",
            "psf.mod": b'supported_version="1.17.*"',
        }
        for name, content in examples.items():
            with self.subTest(file=name):
                path = self.write(name, content)
                self.assertEqual(file_findings(path), [])
                path.write_bytes(UTF8_BOM + content)
                self.assertIn("PSF_ENCODING", self.codes(path))

    def test_localisation_requires_bom_and_matching_language_header(self):
        path = self.write("localisation/english/psf_l_english.yml", b'l_english:\n psf_test:0 "Test"\n')
        self.assertIn("PSF_ENCODING", self.codes(path))
        path.write_bytes(UTF8_BOM + path.read_bytes())
        self.assertEqual(file_findings(path), [])
        path.write_bytes(UTF8_BOM + b'l_simp_chinese:\n psf_test:0 "Test"\n')
        self.assertIn("PSF_LOCALISATION_HEADER", self.codes(path))
        path.write_bytes(UTF8_BOM + b'\n# translation note\nl_english:\n psf_test:0 "Test"\n')
        self.assertEqual(file_findings(path), [])

    def test_malformed_encoding_and_nul_are_rejected(self):
        for raw in (b"\xff\xfe", b"guiTypes\x00 = {}"):
            with self.subTest(raw=raw):
                self.assertIn("PSF_ENCODING", self.codes(self.write("interface/broken.gui", raw)))

    def test_script_size_is_checked_at_the_engine_discovery_boundary(self):
        path = self.write("common/scripted_effects/oversize.txt", b"#" + b" " * (MAX_SCRIPT_BYTES - 1))
        self.assertEqual(file_findings(path), [])
        with path.open("ab") as file:
            file.write(b" ")
        self.assertIn("PSF_DISCOVERY_SIZE", self.codes(path))

    def test_native_engine_window_cannot_be_replaced_by_nested_or_commented_name(self):
        path = self.write("interface/frontendgamesetupview.gui", b'''# containerWindowType = { name = "frontendgamesetupview" }
guiTypes = { containerWindowType = { name = "different"
    containerWindowType = { name = "frontendgamesetupview" }
    instantTextBoxType = { name = "text" text = "{ frontendgamesetupview }" }
} }''')
        self.assertEqual(gui_windows(path.read_text()), {"different"})
        self.assertIn("PSF_NATIVE_GUI", self.codes(path))
        path.write_text('guiTypes = { containerWindowType = { name = "frontendgamesetupview" } }', encoding="utf-8")
        self.assertEqual(file_findings(path), [])

    def test_gui_root_is_an_engine_token(self):
        path = self.write("interface/psf.gui", b'# guiTypes = {}\nwrongTypes = {}')
        self.assertIn("PSF_GUI_ROOT", self.codes(path))

    def test_launcher_version_warning_cannot_recur(self):
        path = self.write("psf.mod", b'supported_version="1.*"\n')
        self.assertIn("PSF_SUPPORTED_VERSION", self.codes(path))
        for version in ("1.17.*", "1.17.3", "1.17.3.1"):
            path.write_text(f'supported_version="{version}"\n', encoding="utf-8")
            self.assertEqual(file_findings(path), [])

    def test_generated_build_passes_and_both_launcher_layers_are_checked(self):
        output = self.root / "dist"
        compile_manifest(ROOT / "examples/minimal/manifest.json", output)
        names = ("psf", "psf_minimal")
        clean = inspect_build(output, names)
        self.assertEqual(clean["diagnostics"], [])
        self.assertEqual(clean["native_gui_files"], 3)
        self.assertGreater(clean["checked_files"], 10)

        # This is the actual failure reported in error(9).log, with otherwise
        # valid script contents. No semantic parser gets a chance to erase it.
        gui = output / "psf_minimal/interface/frontendgamesetupview.gui"
        gui.write_bytes(UTF8_BOM + gui.read_bytes())
        launcher = output / "psf_minimal.mod"
        launcher.write_text('supported_version="1.*"\n', encoding="utf-8")
        broken = inspect_build(output, names)
        self.assertIn("PSF_ENCODING", {d["code"] for d in broken["diagnostics"]})
        self.assertIn("PSF_SUPPORTED_VERSION", {d["code"] for d in broken["diagnostics"]})
        reports = self.root / "reports"
        reports.mkdir()
        (reports / "summary.json").write_text('{"errors": 0, "exit_code": 0}')
        (reports / "cwtools.json").write_text("[]")
        stderr = io.StringIO()
        with patch("tools.ci.validate.verify_toolchain") as toolchain, redirect_stderr(stderr):
            result = validate(["--root", str(output), "--reports", str(reports)])
            self.assertEqual(result, 2)
            toolchain.assert_not_called()
        self.assertIn("PSF_ENCODING", stderr.getvalue())
        self.assertTrue((reports / "engine-preflight.json").is_file())
        self.assertEqual(json.loads((reports / "summary.json").read_text())["status"], "failed")
        self.assertFalse((reports / "cwtools.json").exists())


if __name__ == "__main__":
    unittest.main()
