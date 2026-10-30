"""Native diagnostics are inherited only after exact, source-bound proof."""
from pathlib import Path
import re
import tempfile
import unittest

from psf import bootstrap
from tools.ci import native_history


class NativeHistoryValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = "history/countries/PRC - ComChina.txt"
        self.raw = (bootstrap.ASSETS / "PRC - ComChina.txt").read_bytes()
        self.generated = bootstrap.patch_history(self.raw.decode("utf-8"))[0].encode("utf-8")
        self.history = native_history.reconstruct(self.relative, self.raw, self.generated)
        self.verified = {self.relative: self.history}
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.generated)

    def diagnostic(self, line=1, **changes):
        return {"file": str(self.path), "line": line, "code": "CW242", "severity": "Warning",
                "message": "Field 'capital' appears 0 time(s), expected at least 1", **changes}

    def test_bootstrap_changes_unknown_additions_and_native_edits_fail_reconstruction(self):
        native_assignment = re.search(rb"(?m)^\s*state\s*=\s*\d+", self.generated)
        self.assertIsNotNone(native_assignment)
        candidates = (self.generated.replace(b"psf_history_bootstrap = yes", b"psf_history_bootstrap = no", 1),
                      self.generated + b"\npsf_ci_new_unknown_effect = yes\n",
                      self.generated[:native_assignment.start()] + b"state = 99999" + self.generated[native_assignment.end():])
        for tampered in candidates:
            with self.assertRaisesRegex(ValueError, "exact source"):
                native_history.reconstruct(self.relative, self.raw, tampered)

    def test_diagnostic_needs_exact_file_line_code_severity_message_and_multiplicity(self):
        baseline = self.diagnostic()
        generated_line = next(g for g, b in self.history.generated_to_baseline.items() if b == 1)
        actual = self.diagnostic(generated_line)
        added_line = next(i for i, line in enumerate(self.generated.decode().splitlines(), 1)
                          if "psf_history_bootstrap = yes" in line)
        for altered in (self.diagnostic(added_line), self.diagnostic(generated_line, code="CW263"),
                        self.diagnostic(generated_line, severity="Error"),
                        self.diagnostic(generated_line, message="Different native failure"),
                        self.diagnostic(generated_line, file=str(self.root / "history/countries/OTHER.txt"))):
            checked, inherited = native_history.classify([actual, altered], [baseline], self.root, self.verified)
            self.assertEqual(checked, [altered])
            self.assertEqual(len(inherited), 1)
            self.assertEqual(inherited[0]["source_line"], 1)
            self.assertEqual(len(inherited[0]["source_context_sha256"]), 64)
        checked, inherited = native_history.classify([actual, actual], [baseline], self.root, self.verified)
        self.assertEqual(len(inherited), 1)
        self.assertEqual(checked, [actual])

    def test_same_message_on_a_different_original_line_cannot_be_inherited(self):
        actual = self.diagnostic(next(g for g, b in self.history.generated_to_baseline.items() if b == 1))
        checked, inherited = native_history.classify([actual], [self.diagnostic(2)], self.root, self.verified)
        self.assertEqual(checked, [actual])
        self.assertEqual(inherited, [])

    def test_baseline_keeps_other_psf_files_and_restores_generated_history_on_failure(self):
        sentinel = self.root / "common/scripted_effects/psf.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("psf_test = { add_political_power = 1 }")
        before = sentinel.read_bytes()
        def failing_engine(binary, staged, report, vanilla):
            self.assertEqual(self.path.read_bytes(), self.history.baseline.encode())
            self.assertNotIn(bootstrap.MARKER.encode(), self.path.read_bytes())
            self.assertEqual(sentinel.read_bytes(), before)
            raise RuntimeError("engine failure")
        with self.assertRaisesRegex(RuntimeError, "engine failure"):
            native_history.run_baseline(failing_engine, Path("engine"), self.root,
                                        self.root / "report.json", self.verified)
        self.assertEqual(self.path.read_bytes(), self.generated)
        self.assertEqual(sentinel.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
