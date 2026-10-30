"""Exercise emitted identity transitions and actual engine-ready flag files."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import identity
from psf.model import ManifestError, load, normalize, validate
from psf.script import emit

ROOT = Path(__file__).resolve().parents[1]


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((ROOT / "examples/vanilla/manifest.json").read_text())
        cls.manifest = load(ROOT / "examples/vanilla/manifest.json")
        cls.effects = {node.key: node.value for node in entries(parse(emit(identity.definitions(cls.manifest))))}

    def vm(self):
        state = State(tag="GER")
        state.flags.update({"psf_initialized", "psf_profile_ger"})
        state.variables["psf_regime"] = next(r["_index"] for r in self.manifest["regimes"] if r["id"] == "one_party_republic")
        vm = Interpreter(state)
        vm.effects = self.effects
        return vm

    def test_regime_change_selects_country_name_without_changing_engine_government(self):
        vm = self.vm()
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_NATIONAL_IDENTITY")
        original_engine = copy.deepcopy(vm.state.engine)
        vm.state.variables["psf_regime"] = next(r["_index"] for r in self.manifest["regimes"] if r["id"] == "parliamentary_republic")
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_CONSTITUTIONAL_IDENTITY")
        self.assertEqual(vm.state.engine, original_engine)
        revision = vm.state.variables["psf_ui_revision"]
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.variables["psf_ui_revision"], revision)

    def test_external_cosmetic_tag_survives_refresh_until_explicit_resume(self):
        vm = self.vm()
        vm.run_effect("psf_apply_identity")
        vm.state.cosmetic_tag = "EXTERNAL_FORMABLE"
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "EXTERNAL_FORMABLE")
        self.assertIn("psf_identity_external_override", vm.state.flags)
        vm.run_effect("psf_resume_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_NATIONAL_IDENTITY")

    def test_external_selection_of_another_psf_tag_is_not_stolen_or_released(self):
        vm = self.vm()
        vm.run_effect("psf_apply_identity")
        vm.state.cosmetic_tag = "PSF_GER_CONSTITUTIONAL_IDENTITY"
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_CONSTITUTIONAL_IDENTITY")
        self.assertIn("psf_identity_external_override", vm.state.flags)
        vm.run_effect("psf_release_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_CONSTITUTIONAL_IDENTITY")
        vm.run_effect("psf_resume_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_NATIONAL_IDENTITY")

    def test_identity_can_follow_leading_party_inside_a_coalition(self):
        raw = copy.deepcopy(self.raw)
        profile = raw["profiles"][0]
        profile["identities"][0]["when"] = {"leader": profile["groups"][0]["id"],
                                             "alliance": profile["alliances"][0]["id"]}
        validate(raw)
        manifest = normalize(raw)
        profile = manifest["profiles"][0]
        vm = Interpreter(State(tag=profile["tag"]))
        vm.state.flags.add("psf_profile_" + profile["id"])
        vm.state.variables.update(psf_governing_group=0,
                                  psf_government_leader_group=profile["groups"][0]["_index"],
                                  psf_governing_alliance=profile["alliances"][0]["_index"])
        vm.effects = {n.key: n.value for n in entries(parse(emit(identity.definitions(manifest))))}
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, profile["identities"][0]["cosmetic_tag"])
        vm.state.variables["psf_government_leader_group"] = profile["groups"][1]["_index"]
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, profile["identities"][-1]["cosmetic_tag"])

    def test_manual_identity_holds_until_resume_and_cannot_apply_to_wrong_profile(self):
        vm = self.vm()
        vm.run_effect("psf_set_identity_ger_constitutional_identity")
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_CONSTITUTIONAL_IDENTITY")
        vm.run_effect("psf_set_identity_eng_national_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_CONSTITUTIONAL_IDENTITY")
        vm.run_effect("psf_resume_identity")
        self.assertEqual(vm.state.cosmetic_tag, "PSF_GER_NATIONAL_IDENTITY")

    def test_release_only_removes_a_tag_owned_by_psf(self):
        vm = self.vm()
        vm.state.cosmetic_tag = "EXTERNAL_PUPPET"
        vm.run_effect("psf_release_identity")
        self.assertEqual(vm.state.cosmetic_tag, "EXTERNAL_PUPPET")
        vm.run_effect("psf_resume_identity")
        vm.run_effect("psf_release_identity")
        self.assertIsNone(vm.state.cosmetic_tag)
        vm.run_effect("psf_apply_identity")
        self.assertIsNone(vm.state.cosmetic_tag)

    def test_each_localized_name_has_all_native_ideology_variants(self):
        actual = identity.localizations(self.manifest)
        for language, values in actual.items():
            for item in identity.all_identities(self.manifest):
                for engine in ("", "democratic", "fascism", "communism", "neutrality"):
                    prefix = item["cosmetic_tag"] + ("_" + engine if engine else "")
                    for suffix, field in (("", "name"), ("_ADJ", "adjective"), ("_DEF", "definite_name")):
                        self.assertEqual(values[prefix + suffix], item[field][language])

    def test_authored_flag_triplet_is_identical_across_every_ideology_suffix(self):
        manifest = copy.deepcopy(self.manifest)
        item = manifest["profiles"][0]["identities"][0]
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "source", Path(tmp) / "out"
            source.mkdir()
            item["flags"] = {}
            for size, (width, height) in identity.FLAG_SIZES.items():
                raw = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 8)
                raw += bytes((40, 80, 150, 255)) * width * height
                (source / (size + ".tga")).write_bytes(raw)
                item["flags"][size] = size + ".tga"
            report = identity.write_assets(manifest, output, source)
            self.assertEqual(len(report["flags"]), 3)
            for entry in report["flags"].values():
                self.assertEqual(len(entry["outputs"]), 5)
                self.assertEqual(len({(output / path).read_bytes() for path in entry["outputs"]}), 1)
            (source / "small.tga").write_bytes(b"not a TGA")
            with self.assertRaisesRegex(ManifestError, "complete TGA"):
                identity.write_assets(manifest, output, source)

    def test_identity_rejects_traversal_cross_country_and_shadowed_defaults(self):
        for mutation in ("path", "group", "leader", "default", "duplicate_tag", "unreachable_government"):
            data = copy.deepcopy(self.raw)
            items = data["profiles"][0]["identities"]
            if mutation == "path":
                items[0]["flags"] = dict.fromkeys(identity.FLAG_SIZES, "../secret.tga")
            elif mutation == "group":
                items[0]["when"] = {"group": "eng_conservative"}
            elif mutation == "leader":
                items[0]["when"] = {"leader": "eng_conservative"}
            elif mutation == "default":
                items[0].pop("when")
            elif mutation == "duplicate_tag":
                items[0]["cosmetic_tag"] = items[1]["cosmetic_tag"] = "DUPLICATE_TAG"
            else:
                items[0]["when"] = {"group": "ger_nsdap", "alliance": "ger_government"}
            with self.subTest(mutation=mutation), self.assertRaises(ManifestError):
                validate(data)

    def test_absent_identity_is_an_explicit_noop(self):
        data = copy.deepcopy(self.raw)
        for p in data["profiles"]:
            p.pop("identities", None)
        effects = {node.key: node.value for node in entries(parse(emit(identity.definitions(normalize(data)))))}
        vm = self.vm()
        vm.effects = effects
        vm.state.cosmetic_tag = "ORIGINAL_TAG"
        vm.run_effect("psf_apply_identity")
        self.assertEqual(vm.state.cosmetic_tag, "ORIGINAL_TAG")


if __name__ == "__main__":
    unittest.main()
