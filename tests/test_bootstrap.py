"""Preserving original history and initializing before any daily action."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import tempfile
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import bootstrap, mechanics, model, runtime


ROOT = Path(__file__).resolve().parents[1]


class HistoryBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load(ROOT / "examples/vanilla/manifest.json")
        cls.effects = {node.key: node.value for text in (runtime.core_effects(), runtime.effects(cls.manifest)) for node in entries(parse(text))}
        cls.triggers = {node.key: node.value for text in (runtime.core_triggers(), runtime.triggers(cls.manifest)) for node in entries(parse(text))}

    def test_every_bundled_history_is_preserved_byte_for_byte_except_insertions(self):
        paths = sorted(bootstrap.ASSETS.glob("*.txt"))
        self.assertEqual(len(paths), 364)
        total_dates = 0
        for path in paths:
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                text = raw.decode("utf-8")
                generated, dates = bootstrap.patch_history(text)
                self.assertFalse(generated.startswith("\ufeff"))
                total_dates += dates
                newline = "\r\n" if "\r\n" in text else "\n"
                for indent in ("\t", ""):
                    insertion = newline + newline.join(indent + line for line in
                        (bootstrap.MARKER, "psf_history_bootstrap = yes", "psf_prepare_frontend = yes")) + newline
                    generated = generated.replace(insertion, "")
                generated = generated.removesuffix(bootstrap.REPAIR)
                generated = generated.replace(bootstrap.EMPTY_BRANCH_REPAIR, bootstrap.KNOWN_EMPTY_BRANCH)
                if raw.startswith(b"\xef\xbb\xbf"):
                    generated = "\ufeff" + generated
                self.assertEqual(generated.encode("utf-8"), raw)
        self.assertGreater(total_dates, 100)

    def test_nested_dates_comments_and_strings_are_not_date_boundaries(self):
        text = 'capital = 1\n# 1939.1.1 = { }\nlog = "1939.1.1 = { }"\nif = { limit = { always = yes } 1939.1.1 = { } }\n1939.1.1 = { }\n'
        generated, count = bootstrap.patch_history(text)
        self.assertEqual(count, 1)
        self.assertEqual(generated.count(bootstrap.MARKER), 2)
        with self.assertRaisesRegex(model.ManifestError, "already contains"):
            bootstrap.patch_history(generated)
        with self.assertRaisesRegex(model.ManifestError, "unmatched opening"):
            bootstrap.patch_history("1939.1.1 = { log = test")

    def test_history_initializes_authored_and_fallback_countries_before_first_tick(self):
        for tag, date in (("ENG", (1936, 1, 1)), ("ZZZ", (1936, 1, 1)), ("ZZZ", (1939, 1, 1))):
            with self.subTest(tag=tag, date=date):
                # A source country can change its engine government at a later
                # bookmark. The selected fallback must follow that date block.
                source = 'set_politics = { ruling_party = democratic }\n1939.1.1 = { set_politics = { ruling_party = communism } }\n'
                script, _ = bootstrap.patch_history(source, frontend=False)
                nodes = entries(parse(script))
                # Native history has a root phase and selected date phases.
                # Exercise both scheduling orders; each boundary is guarded.
                for root_first in (False, True):
                    vm = Interpreter(State(tag=tag, date=date))
                    vm.effects, vm.triggers = self.effects, self.triggers
                    vm.dynamic_definitions = {n.key: n.value for n in entries(parse(mechanics.dynamic_modifiers(self.manifest)))}
                    ordered = sorted(nodes, key=lambda n: bool(re.fullmatch(r"\d{4}\.\d+\.\d+", n.key))) if root_first else nodes
                    for node in ordered:
                        if re.fullmatch(r"\d{4}\.\d+\.\d+", node.key):
                            if tuple(map(int, node.key.split("."))) <= date:
                                vm.execute(node.value)
                        else:
                            vm.execute((node,))
                    self.assertIn("psf_initialized", vm.state.flags)
                    self.assertGreater(vm.state.variables["psf_group_count"], 0)
                    self.assertGreater(vm.state.variables["psf_ui_revision"], 0)
                    self.assertEqual(vm.state.variables["psf_election_count"], 0)
                    if tag == "ZZZ":
                        expected = "communism" if date[0] == 1939 else "democratic"
                        fallback = next(p for p in model.profiles(self.manifest) if p.get("engine_ideology") == expected)
                        self.assertIn("psf_profile_" + fallback["id"], vm.state.flags)

    def test_writer_preserves_filenames_and_has_reproducible_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            report = bootstrap.write_bootstrap_history(self.manifest, output)
            self.assertEqual(report["country_count"], 364)
            self.assertEqual(report["source"], "bundled/native_history")
            self.assertEqual(sum("known_source_repair" in item for item in report["files"]), 1)
            repaired = next(item for item in report["files"] if "known_source_repair" in item)
            self.assertEqual(len(repaired["known_source_repair"]), 2)
            self.assertEqual(sum(item["source_had_bom"] for item in report["files"]), 336)
            for item in report["files"]:
                self.assertEqual(item["encoding_normalized"], item["source_had_bom"])
                self.assertFalse((output / item["file"]).read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual({p.name for p in (output / "history/countries").glob("*.txt")},
                             {p.name for p in bootstrap.ASSETS.glob("*.txt")})
            compat = copy.deepcopy(self.manifest)
            compat["settings"]["mechanics_mode"] = "compat"
            self.assertFalse(bootstrap.write_bootstrap_history(compat, output)["enabled"])


if __name__ == "__main__":
    unittest.main()
