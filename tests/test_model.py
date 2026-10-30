from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psf.model import ManifestError, load, normalize, stable_id, validate
from psf.palette import color

ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "examples/vanilla/manifest.json").read_text())

    def setUp(self):
        self.data = copy.deepcopy(self.fixture)

    def test_both_localizations_required(self):
        del self.data["profiles"][0]["groups"][0]["name"]["simp_chinese"]
        with self.assertRaisesRegex(ManifestError, "simp_chinese"):
            validate(self.data)

    def test_typo_in_metric_does_not_silently_default(self):
        self.data["profiles"][0]["groups"][0]["influnce"] = 50
        with self.assertRaisesRegex(ManifestError, "influnce"):
            validate(self.data)

    def test_out_of_range_and_nonfinite_values_rejected(self):
        for value in (-1, 101, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.data["profiles"][0]["groups"][0]["support"] = value
                with self.assertRaises(ManifestError):
                    validate(self.data)

    def test_organization_colors_accept_exact_rgb_and_normalize_equivalent_forms(self):
        group = self.data["profiles"][0]["groups"][0]
        for value in ("#00aFff", [0, 175, 255]):
            with self.subTest(value=value):
                group["color"] = value
                validate(self.data)
                normalized = normalize(self.data)
                self.assertEqual(normalized["profiles"][0]["groups"][0]["color"], [0, 175, 255])
                self.assertEqual(group["color"], value)
        other = self.data["fallback_profiles"][0]["groups"][0]
        other.pop("color", None)
        normalized = normalize(self.data)
        self.assertEqual(normalized["fallback_profiles"][0]["groups"][0]["color"], list(color(other["id"])))
        self.assertNotIn("color", other)

    def test_invalid_organization_colors_fail_before_any_artwork_is_written(self):
        group = self.data["profiles"][0]["groups"][0]
        for value in ("#abc", "123456", "#12345G", "#12345678", [], [1, 2],
                      [1, 2, 3, 4], [256, 0, 0], [-1, 0, 0], [1.5, 2, 3],
                      [True, 2, 3], ["1", 2, 3], [float("nan"), 0, 0],
                      [float("inf"), 0, 0], None):
            with self.subTest(value=value):
                group["color"] = value
                with self.assertRaisesRegex(ManifestError, "color"):
                    validate(self.data)

    def test_unknown_axis_is_an_error(self):
        self.data["profiles"][0]["groups"][0]["positions"]["typo_axis"] = 0
        with self.assertRaisesRegex(ManifestError, "unknown"):
            validate(self.data)

    def test_adding_an_axis_requires_all_positions(self):
        axis = copy.deepcopy(self.data["axes"][0])
        axis["id"] = "new_issue"
        self.data["axes"].append(axis)
        with self.assertRaisesRegex(ManifestError, "new_issue"):
            validate(self.data)

    def test_cross_country_alliance_member_is_rejected(self):
        self.data["profiles"][0]["alliances"][0]["members"].append(self.data["profiles"][1]["groups"][0]["id"])
        with self.assertRaisesRegex(ManifestError, "same profile"):
            validate(self.data)

    def test_duplicate_global_organization_id_is_rejected(self):
        self.data["profiles"][1]["groups"][0]["id"] = self.data["profiles"][0]["groups"][0]["id"]
        with self.assertRaisesRegex(ManifestError, "duplicate id"):
            validate(self.data)

    def test_all_four_fallbacks_required(self):
        self.data["fallback_profiles"].pop()
        with self.assertRaisesRegex(ManifestError, "fallback_profiles"):
            validate(self.data)

    def test_scenario_operation_requires_correct_arguments(self):
        self.data["scenarios"][0]["options"][0]["effects"] = [{"op": "join", "group": self.data["profiles"][0]["groups"][0]["id"]}]
        with self.assertRaisesRegex(ManifestError, "join requires"):
            validate(self.data)

    def test_invalid_calendar_date_rejected(self):
        self.data["scenarios"][0]["date"] = "1936.2.31"
        with self.assertRaisesRegex(ManifestError, "invalid calendar date"):
            validate(self.data)

    def test_government_can_be_a_single_group_with_no_alliances(self):
        p = self.data["profiles"][0]
        p["alliances"] = []
        p["government"] = {"group": p["groups"][0]["id"]}
        self.data["scenarios"] = [s for s in self.data["scenarios"] if s["profile"] != p["id"]]
        validate(self.data)
        actual = normalize(self.data)["profiles"][0]
        self.assertEqual(actual["alliances"], [])
        self.assertEqual(actual["government"], p["government"])

    def test_caretaker_and_nonruling_alliances_do_not_need_a_government_alliance(self):
        p = self.data["profiles"][1]
        p["government"] = None
        for a in p["alliances"]:
            a["kind"] = "opposition"
        validate(self.data)
        actual = normalize(self.data)["profiles"][1]
        self.assertIsNone(actual["government"])
        self.assertEqual(len(actual["alliances"]), len(p["alliances"]))

    def test_legacy_initial_alliance_normalizes_without_synthetic_cabinet(self):
        validate(self.data)
        actual = normalize(self.data)["profiles"][0]
        self.assertEqual(actual["government"], {"alliance": "ger_government"})
        self.assertEqual(actual["alliances"], [dict(a, _index=stable_id(a["id"])) for a in self.data["profiles"][0]["alliances"]])

    def test_explicit_government_does_not_require_legal_members_in_a_former_cabinet(self):
        profile = self.data["profiles"][0]
        former = next(a for a in profile["alliances"] if a["kind"] == "government")
        former["members"] = ["ger_spd"]  # A banned opposition member may keep its pact.
        for selection in (None, {"group": "ger_nsdap"}):
            with self.subTest(selection=selection):
                profile["government"] = selection
                validate(self.data)
        profile.pop("government")
        with self.assertRaisesRegex(ManifestError, "initial government needs at least one legal group"):
            validate(self.data)

    def test_government_rejects_foreign_banned_or_ambiguous_group(self):
        p = self.data["profiles"][0]
        for government in ({"group": "eng_conservative"}, {"group": "ger_spd"},
                           {"group": "ger_nsdap", "alliance": "ger_government"},
                           {"alliance": "eng_government"}):
            with self.subTest(government=government):
                p["government"] = government
                with self.assertRaises(ManifestError):
                    validate(self.data)

    def test_bookmark_government_checks_post_override_group_status(self):
        p = self.data["profiles"][0]
        p["start_overrides"] = [{"date": "1937.1.1", "government": {"group": "ger_spd"},
                                  "groups": [{"id": "ger_spd", "status": "legal"}]}]
        validate(self.data)
        p["start_overrides"][0]["groups"] = []
        with self.assertRaisesRegex(ManifestError, "government group must be legal"):
            validate(self.data)

    def test_identity_leader_condition_rejects_foreign_organizations(self):
        profile = next(p for p in self.data["profiles"] if p.get("identities"))
        identity = profile["identities"][0]
        identity["when"] = {"leader": profile["groups"][0]["id"]}
        validate(self.data)
        foreign = next(p for p in self.data["profiles"] if p["id"] != profile["id"])
        identity["when"]["leader"] = foreign["groups"][0]["id"]
        with self.assertRaisesRegex(ManifestError, "unknown or cross-country leader"):
            validate(self.data)

    def test_scenario_numeric_collisions_rejected(self):
        original = stable_id
        scenario_ids = {s["id"] for s in self.data["scenarios"]}
        with patch("psf.model.stable_id", lambda x: 42 if x in scenario_ids else original(x)):
            with self.assertRaisesRegex(ManifestError, "Scenario event id collision"):
                validate(self.data)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"id":"a","id":"b"}')
            with self.assertRaisesRegex(ManifestError, "Duplicate JSON"):
                load(path)

    def test_duplicate_yaml_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("id: a\nid: b\n")
            with self.assertRaisesRegex(ManifestError, "Duplicate YAML"):
                load(path)

    def test_framework_folder_name_is_reserved(self):
        self.data["id"] = "psf"
        with self.assertRaisesRegex(ManifestError, "reserved"):
            validate(self.data)

    def test_strict_mode_defaults_to_export_and_rejects_native_import(self):
        self.data["settings"] = {"mechanics_mode": "strict"}
        validate(self.data)
        self.assertEqual(normalize(self.data)["settings"]["bridge_mode"], "export")
        for mode in ("bidirectional", "none"):
            self.data["settings"]["bridge_mode"] = mode
            with self.assertRaisesRegex(ManifestError, "strict mechanics require"):
                validate(self.data)


if __name__ == "__main__":
    unittest.main()
