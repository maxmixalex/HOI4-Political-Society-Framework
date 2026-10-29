from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psf.model import ManifestError, load, normalize, stable_id, validate

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

    def test_generated_cabinet_collision_cannot_change_saved_id(self):
        cabinet_id = self.data["profiles"][0]["id"] + "_transition_cabinet"
        self.data["profiles"][0]["alliances"][0]["numeric_id"] = stable_id(cabinet_id)
        validate(self.data)
        with self.assertRaisesRegex(ManifestError, "collision including generated"):
            normalize(self.data)

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


if __name__ == "__main__":
    unittest.main()
