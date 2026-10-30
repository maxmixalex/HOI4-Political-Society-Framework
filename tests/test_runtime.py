"""Execute emitted HOI4 scripts and check political state transitions."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import unittest

from hoi4_interpreter import Interpreter, State, entries, parse
from psf import frontend, mechanics, model, runtime


REPO = Path(__file__).resolve().parents[1]


def group_var(identifier, field):
    return f"psf_g_{identifier}_{field}"


def alliance_var(identifier, field):
    return f"psf_a_{identifier}_{field}"


class GeneratedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load(REPO / "examples/vanilla/manifest.json")
        cls.profile_map = {p["id"]: p for p in model.profiles(cls.manifest)}
        cls.effects, cls.triggers = {}, {}
        cls.dynamic_definitions = {node.key: node.value for node in entries(parse(mechanics.dynamic_modifiers(cls.manifest)))}
        sources = (
            (runtime.core_effects(), cls.effects), (runtime.effects(cls.manifest), cls.effects),
            (runtime.core_triggers(), cls.triggers), (runtime.triggers(cls.manifest), cls.triggers),
        )
        for text, registry in sources:
            for node in entries(parse(text)):
                if node.key in registry:
                    raise AssertionError(f"Duplicate generated API {node.key}")
                registry[node.key] = node.value

    def vm(self, profile="eng", date=(1936, 1, 1)):
        definition = self.profile_map[profile]
        vm = Interpreter(State(tag=definition.get("tag", "ZZZ"), date=date))
        vm.effects = self.effects
        vm.triggers = self.triggers
        vm.dynamic_definitions = self.dynamic_definitions
        vm.state.engine["ruling_party"] = definition.get("engine_ideology", "neutrality")
        vm.run_effect("psf_init_" + profile)
        return vm

    def test_every_profile_initializes_and_survives_twelve_months(self):
        for profile, definition in self.profile_map.items():
            with self.subTest(profile=profile):
                vm = self.vm(profile)
                for _ in range(12):
                    vm.run_effect("psf_monthly_" + profile)
                self.assertIn("psf_initialized", vm.state.flags)
                self.assertNotIn("psf_batch_update", vm.state.flags)
                self.assertTrue(all(math.isfinite(v) for v in vm.state.variables.values()))
                self.assertGreaterEqual(vm.state.variables["psf_legitimacy"], 0)
                self.assertLessEqual(vm.state.variables["psf_legitimacy"], 100)
                for group in definition["groups"]:
                    gid = group["id"]
                    self.assertIn(vm.state.variables[group_var(gid, "status")], (0, 1, 2, 3))
                    for metric in ("support", "influence", "satisfaction"):
                        self.assertGreaterEqual(vm.state.variables[group_var(gid, metric)], 0)
                        self.assertLessEqual(vm.state.variables[group_var(gid, metric)], 100)
                    if vm.state.variables[group_var(gid, "governing")]:
                        self.assertEqual(vm.state.variables[group_var(gid, "status")], 1)

    def test_initialization_cannot_reset_an_existing_save(self):
        vm = self.vm()
        vm.run_effect("psf_add_eng_labour_support", {"psf_amount": 4})
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_init_eng")
        self.assertEqual(vm.state.variables, before)

    def test_bootstrap_refreshes_immediately_without_advancing_time_or_resetting_state(self):
        vm = self.vm()
        vm.run_effect("psf_add_eng_labour_support", {"psf_amount": 7})
        baseline = {key: value for key, value in vm.state.variables.items()
                    if key.endswith(("_days", "_support", "_influence", "_satisfaction"))
                    or key in {"psf_legitimacy", "psf_election_clock", "psf_election_count"}}
        revision = vm.state.variables["psf_ui_revision"]
        for _ in range(3):
            vm.run_effect("psf_bootstrap")
        self.assertEqual({key: vm.state.variables[key] for key in baseline}, baseline)
        self.assertGreater(vm.state.variables["psf_ui_revision"], revision)
        self.assertEqual(vm.state.date, (1936, 1, 1))

    def test_group_government_and_caretaker_preserve_coexisting_alliances(self):
        vm = self.vm()
        stored = {key: value for key, value in vm.state.variables.items()
                  if key.startswith("psf_a_") and ("_g_" in key or key.endswith("_active"))}
        labour = next(g for g in self.profile_map["eng"]["groups"] if g["id"] == "eng_labour")
        vm.run_effect("psf_govern_group_eng_labour")
        self.assertEqual(vm.state.variables["psf_governing_group"], labour["_index"])
        self.assertEqual(vm.state.variables["psf_government_leader_group"], labour["_index"])
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
        self.assertEqual(vm.state.variables[group_var("eng_labour", "governing")], 1)
        self.assertEqual(vm.state.variables[alliance_var("eng_government", "role")], 2)
        self.assertEqual({key: vm.state.variables[key] for key in stored}, stored)
        vm.run_effect("psf_clear_government")
        self.assertEqual(vm.state.variables["psf_caretaker"], 1)
        self.assertEqual(vm.state.variables["psf_governing_group"], 0)
        self.assertEqual(vm.state.variables["psf_government_leader_group"], 0)
        self.assertEqual({key: vm.state.variables[key] for key in stored}, stored)

    def test_government_leader_prefers_party_over_stronger_army_and_has_organization_fallback(self):
        vm = self.vm("ger")
        party = next(g for g in self.profile_map["ger"]["groups"] if g["id"] == "ger_nsdap")
        army = next(g for g in self.profile_map["ger"]["groups"] if g["id"] == "ger_officers")
        vm.state.variables[group_var("ger_nsdap", "influence")] = 2
        vm.state.variables[group_var("ger_officers", "influence")] = 100
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables["psf_government_leader_group"], party["_index"])
        self.assertEqual(vm.state.variables[group_var("ger_officers", "governing")], 1)
        vm.run_effect("psf_leave_ger_government_ger_nsdap")
        self.assertEqual(vm.state.variables["psf_government_leader_group"], army["_index"])
        vm.run_effect("psf_govern_group_ger_officers")
        self.assertEqual(vm.state.variables["psf_government_leader_group"], army["_index"])
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)

    def test_alliance_with_dormant_members_remains_in_existence(self):
        vm = self.vm()
        alliance = next(a for a in self.profile_map["eng"]["alliances"] if a["id"] == "eng_labour_movement")
        for gid in alliance["members"]:
            vm.state.variables[group_var(gid, "status")] = 0
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables[alliance_var(alliance["id"], "active")], 1)
        self.assertEqual(vm.state.variables[alliance_var(alliance["id"], "member_count")], len(alliance["members"]))
        self.assertEqual(vm.state.variables[alliance_var(alliance["id"], "influence")], 0)

    def test_government_leader_ties_are_stable_and_agree_with_frontend(self):
        from psf.script import emit
        profile = copy.deepcopy(self.profile_map["eng"])
        cabinet = next(a for a in profile["alliances"] if a["id"] == "eng_government")
        candidates = [g for g in profile["groups"] if g["id"] in cabinet["members"]
                      and (g["electoral"] or g["kind"] == "party") and g["status"] == "legal"]
        expected = min(g["_index"] for g in candidates)
        vm = self.vm()
        for group in profile["groups"]:
            group["influence"] = 10
            vm.state.variables[group_var(group["id"], "influence")] = 10
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables["psf_government_leader_group"], expected)
        profile["groups"].reverse()
        refresh = entries(parse(emit([runtime.refresh_effect(self.manifest, profile)])))[0]
        vm.effects = {**self.effects, refresh.key: refresh.value}
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables["psf_government_leader_group"], expected)
        self.assertEqual(frontend.snapshot(self.manifest, profile, None)["ruling_group"]["_index"], expected)

    def test_profiles_without_any_alliance_can_govern_and_hold_elections(self):
        profile = next(p for p in self.profile_map.values() if not p["alliances"] and p["engine_ideology"] == "democratic")
        vm = self.vm(profile["id"])
        self.assertEqual(vm.state.variables["psf_caretaker"], 0)
        self.assertGreater(vm.state.variables["psf_governing_group"], 0)
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
        vm.run_effect("psf_hold_election")
        self.assertEqual(vm.state.variables["psf_election_count"], 1)
        self.assertGreater(vm.state.variables["psf_governing_group"], 0)

    def test_explicit_government_selection_overrides_legacy_alliance_kind(self):
        from psf.script import emit
        for selection in (None, {"group": "eng_labour"}):
            with self.subTest(selection=selection):
                changed = copy.deepcopy(self.profile_map["eng"])
                changed["government"] = selection
                init = entries(parse(emit([runtime.initialize_effect(self.manifest, changed)])))[0]
                vm = Interpreter(State(tag="ENG"))
                vm.effects, vm.triggers = {**self.effects, init.key: init.value}, self.triggers
                vm.run_effect("psf_init_eng")
                self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
                self.assertEqual(vm.state.variables["psf_caretaker"], int(selection is None))
                self.assertEqual(vm.state.variables[alliance_var("eng_government", "role")], 2)
                self.assertEqual(vm.state.variables[alliance_var("eng_government", "active")], 1)

    def test_old_transition_cabinet_save_migrates_without_losing_political_state(self):
        vm = self.vm()
        vm.state.variables["psf_schema_version"] = 1
        vm.state.variables.pop("psf_governing_group")
        vm.state.variables.pop("psf_identity")
        vm.state.variables["psf_governing_alliance"] = model.stable_id("removed_transition_cabinet")
        before = {g["id"]: vm.state.variables[group_var(g["id"], "support")] for g in self.profile_map["eng"]["groups"]}
        vm.run_effect("psf_bootstrap")
        self.assertEqual(vm.state.variables["psf_schema_version"], 2)
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
        self.assertGreater(vm.state.variables["psf_governing_group"], 0)
        self.assertEqual(vm.state.variables["psf_caretaker"], 0)
        self.assertEqual({gid: vm.state.variables[group_var(gid, "support")] for gid in before}, before)

    def test_strict_popularity_stability_offset_tracks_external_sources_without_oscillation(self):
        vm = self.vm()
        for external in (0.2, 0.2, 0.35, 0.35, 0.0, 0.0, -0.15, -0.15):
            vm.state.modifier_values["party_popularity_stability_factor"] = external
            vm.run_effect("psf_refresh")
            self.assertAlmostEqual(vm.state.variables["psf_native_popularity_stability_offset"], -external)
            self.assertAlmostEqual(vm.number("modifier@party_popularity_stability_factor"), 0)

    def test_strict_policy_uses_actual_institutions_and_disables_native_election_clock(self):
        vm = self.vm()
        self.assertFalse(vm.state.engine["elections_allowed"])
        self.assertEqual(vm.state.variables["psf_elections_enabled"], 1)
        self.assertAlmostEqual(vm.number("modifier@generate_wargoal_tension"), 1.0)
        unelected = next(r for r in self.manifest["regimes"] if not r.get("elections", False))
        vm.run_effect("psf_set_regime_" + unelected["id"])
        self.assertEqual(vm.state.variables["psf_elections_enabled"], 0)
        self.assertAlmostEqual(vm.number("modifier@generate_wargoal_tension"), 0.5)
        self.assertFalse(vm.state.rules["can_only_justify_war_on_threat_country"])

    def test_strict_bootstrap_discards_native_slot_drift_without_changing_psf_support(self):
        vm = self.vm()
        before = {g["id"]: vm.state.variables[group_var(g["id"], "support")] for g in self.profile_map["eng"]["groups"]}
        projected = dict(vm.state.popularities)
        vm.state.popularities = {"democratic": 0, "communism": 100, "fascism": 0, "neutrality": 0}
        vm.state.engine["ruling_party"] = "communism"
        vm.run_effect("psf_bootstrap")
        self.assertEqual({gid: vm.state.variables[group_var(gid, "support")] for gid in before}, before)
        self.assertEqual(vm.state.popularities, projected)
        self.assertNotEqual(vm.state.engine["ruling_party"], "communism")

    def test_legitimacy_change_refreshes_ui_and_native_modifier_without_a_daily_tick(self):
        vm = self.vm()
        revision = vm.state.variables["psf_ui_revision"]
        vm.state.callbacks.clear()
        vm.run_effect("psf_add_legitimacy", {"psf_amount": -5})
        self.assertGreater(vm.state.variables["psf_ui_revision"], revision)
        self.assertIn(("force_update_dynamic_modifier", "yes"), vm.state.callbacks)
        self.assertAlmostEqual(vm.state.variables["psf_stability_modifier"],
                               (vm.state.variables["psf_legitimacy"] - 60) / 500)
        vm.state.callbacks.clear()
        vm.run_effect("psf_refresh_modifiers")
        self.assertNotIn(("force_update_dynamic_modifier", "yes"), vm.state.callbacks,
                         "Unchanged inputs must not force all native dynamic modifiers again")

    def test_election_inside_transaction_uses_new_support_and_preserves_batch_owner(self):
        vm = self.vm()
        vm.run_effect("psf_begin_transaction")
        for group in self.profile_map["eng"]["groups"]:
            if group["electoral"]:
                vm.run_effect("psf_set_" + group["id"] + "_support", {"psf_amount": 0})
        vm.run_effect("psf_set_eng_labour_support", {"psf_amount": 90})
        vm.run_effect("psf_hold_election")
        winner = next(g for g in self.profile_map["eng"]["groups"] if g["id"] == "eng_labour")
        self.assertEqual(vm.state.variables["psf_winning_group"], winner["_index"])
        self.assertAlmostEqual(vm.state.variables[group_var("eng_labour", "vote_share")], 100)
        self.assertIn("psf_batch_update", vm.state.flags)
        vm.run_effect("psf_commit_transaction")
        self.assertNotIn("psf_batch_update", vm.state.flags)

    def test_election_permission_tracks_regime_changes_inside_transaction(self):
        vm = self.vm()
        unelected = next(r for r in self.manifest["regimes"] if not r.get("elections", False))
        elected = next(r for r in self.manifest["regimes"] if r.get("elections", False))
        vm.run_effect("psf_begin_transaction")
        vm.run_effect("psf_set_regime_" + unelected["id"])
        vm.run_effect("psf_hold_election")
        self.assertEqual(vm.state.variables["psf_election_count"], 0)
        self.assertEqual(vm.state.variables["psf_elections_enabled"], 0)
        self.assertIn("psf_batch_update", vm.state.flags)
        vm.run_effect("psf_set_regime_" + elected["id"])
        vm.run_effect("psf_hold_election")
        self.assertEqual(vm.state.variables["psf_election_count"], 1)
        self.assertEqual(vm.state.variables["psf_elections_enabled"], 1)
        self.assertIn("psf_batch_update", vm.state.flags)

    def test_same_ideology_parties_remain_separate_organizations(self):
        vm = self.vm()
        buckets = {}
        for group in self.profile_map["eng"]["groups"]:
            if group["kind"] == "party":
                buckets.setdefault(vm.state.variables[group_var(group["id"], "ideology")], []).append(group["id"])
        duplicates = next((ids for ids in buckets.values() if len(ids) >= 2), None)
        self.assertIsNotNone(duplicates, "The example must demonstrate multiple parties of one ideology")
        first, second = duplicates[:2]
        before_first = vm.state.variables[group_var(first, "support")]
        before_second = vm.state.variables[group_var(second, "support")]
        vm.run_effect("psf_add_" + first + "_support", {"psf_amount": 3})
        self.assertEqual(vm.state.variables[group_var(first, "support")], before_first + 3)
        self.assertEqual(vm.state.variables[group_var(second, "support")], before_second)

    def test_influence_and_popular_support_are_independent(self):
        vm = self.vm("ger")
        gid = "ger_industry"
        before = vm.state.variables[group_var(gid, "support")]
        before_influence = vm.state.variables[group_var(gid, "influence")]
        vm.run_effect("psf_add_" + gid + "_influence", {"psf_amount": 10})
        self.assertEqual(vm.state.variables[group_var(gid, "support")], before)
        self.assertEqual(vm.state.variables[group_var(gid, "influence")], before_influence + 10)
        self.assertGreater(vm.state.variables[group_var(gid, "influence")], before)

    def test_ban_reduces_effective_influence_and_is_idempotent(self):
        vm = self.vm()
        gid = "eng_buf"
        influence = vm.state.variables[group_var(gid, "influence")]
        support = vm.state.variables[group_var(gid, "support")]
        vm.run_effect("psf_ban_" + gid)
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 3)
        self.assertEqual(vm.state.variables[group_var(gid, "influence")], influence)
        self.assertEqual(vm.state.variables[group_var(gid, "support")], support)
        self.assertAlmostEqual(vm.state.variables[group_var(gid, "effective_influence")], influence * self.manifest["settings"]["banned_influence_factor"])
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_ban_" + gid)
        self.assertEqual(vm.state.variables, before)
        vm.run_effect("psf_legalize_" + gid)
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 1)
        self.assertEqual(vm.state.variables[group_var(gid, "effective_influence")], influence)
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_legalize_" + gid)
        self.assertEqual(vm.state.variables, before)

    def test_governing_member_must_leave_cabinet_before_a_ban(self):
        vm = self.vm()
        vm.run_effect("psf_ban_eng_conservative")
        self.assertEqual(vm.state.variables[group_var("eng_conservative", "status")], 1)
        vm.run_effect("psf_leave_eng_government_eng_conservative")
        vm.run_effect("psf_ban_eng_conservative")
        self.assertEqual(vm.state.variables[group_var("eng_conservative", "status")], 3)
        self.assertEqual(vm.state.variables[group_var("eng_conservative", "governing")], 0)

    def test_statutory_ban_survives_underground_recovery_until_legalized(self):
        vm = self.vm()
        gid = "eng_labour"
        vm.run_effect("psf_ban_" + gid)
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_banned"]))
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_suppressed"]))
        vm.run_effect("psf_monthly_eng")
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 2)
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_banned"]))
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_underground"]))
        self.assertFalse(vm.condition(vm.triggers[f"psf_{gid}_is_suppressed"]))
        vm.run_effect("psf_legalize_" + gid)
        self.assertEqual(vm.state.variables[group_var(gid, "prohibited")], 0)
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_legal"]))
        self.assertFalse(vm.condition(vm.triggers[f"psf_{gid}_is_banned"]))
        self.assertFalse(vm.condition(vm.triggers[f"psf_{gid}_is_underground"]))

    def test_native_government_import_lifts_the_incoming_partys_ban(self):
        vm = self.vm("ger")
        gid = "ger_kpd"
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_banned"]))
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_underground"]))
        vm.state.engine["ruling_party"] = "communism"
        vm.run_effect("psf_import_government")
        self.assertEqual(vm.state.variables[group_var(gid, "prohibited")], 0)
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_legal"]))
        self.assertTrue(vm.condition(vm.triggers[f"psf_{gid}_is_governing"]))
        self.assertFalse(vm.condition(vm.triggers[f"psf_{gid}_is_banned"]))
        self.assertFalse(vm.condition(vm.triggers[f"psf_{gid}_is_underground"]))

    def test_underground_member_leaves_government_but_keeps_electoral_pact(self):
        vm = self.vm("fra")
        gid = "fra_radical"
        self.assertEqual(vm.state.variables[alliance_var("fra_government", "g_" + gid)], 1)
        self.assertEqual(vm.state.variables[alliance_var("fra_popular_front", "g_" + gid)], 1)
        vm.run_effect("psf_underground_" + gid)
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 2)
        self.assertEqual(vm.state.variables[group_var(gid, "governing")], 0)
        self.assertEqual(vm.state.variables[alliance_var("fra_government", "g_" + gid)], 0)
        self.assertEqual(vm.state.variables[alliance_var("fra_popular_front", "g_" + gid)], 1)

    def test_inactive_organizations_do_not_drift_until_activated(self):
        vm = self.vm("ger")
        gid = "ger_zentrum"
        metrics = {metric: vm.state.variables[group_var(gid, metric)] for metric in ("support", "influence", "satisfaction")}
        vm.run_effect("psf_monthly_ger")
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 0)
        for metric, expected in metrics.items():
            self.assertEqual(vm.state.variables[group_var(gid, metric)], expected)
        self.assertEqual(vm.state.variables[group_var(gid, "effective_influence")], 0)
        vm.run_effect("psf_activate_" + gid)
        self.assertEqual(vm.state.variables[group_var(gid, "status")], 1)
        self.assertEqual(vm.state.variables[group_var(gid, "effective_influence")], metrics["influence"])
        before = vm.state.variables[group_var(gid, "satisfaction")]
        vm.run_effect("psf_monthly_ger")
        self.assertLess(vm.state.variables[group_var(gid, "satisfaction")], before)

    def test_foreign_profile_api_is_a_no_op(self):
        vm = self.vm()
        before = copy.deepcopy(vm.state.variables)
        vm.run_effect("psf_activate_ger_zentrum")
        self.assertEqual(vm.state.variables, before)
        self.assertNotIn(group_var("ger_zentrum", "status"), vm.state.variables)

    def test_dissolved_government_becomes_caretaker(self):
        vm = self.vm()
        vm.run_effect("psf_dissolve_eng_government")
        self.assertEqual(vm.state.variables["psf_caretaker"], 1)
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0)
        self.assertEqual(vm.state.variables["psf_government_ideology"], 0)
        for group in self.profile_map["eng"]["groups"]:
            self.assertEqual(vm.state.variables[group_var(group["id"], "governing")], 0)
        vm.run_effect("psf_govern_eng_government")
        self.assertEqual(vm.state.variables["psf_governing_alliance"], 0, "An empty coalition cannot take power")

    def test_zero_influence_and_zero_ballots_never_divide_by_zero(self):
        vm = self.vm()
        for group in self.profile_map["eng"]["groups"]:
            vm.state.variables[group_var(group["id"], "influence")] = 0
            vm.state.variables[group_var(group["id"], "support")] = 0
        vm.run_effect("psf_refresh")
        self.assertEqual(vm.state.variables["psf_caretaker"], 1)
        self.assertEqual(vm.state.variables["psf_government_influence"], 0)
        before = vm.state.variables["psf_election_count"]
        vm.run_effect("psf_hold_election_eng")
        self.assertEqual(vm.state.variables["psf_election_count"], before)

    def test_ballots_exclude_banned_parties_and_nonparties(self):
        vm = self.vm("fra")
        vm.run_effect("psf_ban_fra_pcf")
        vm.run_effect("psf_set_fra_pcf_support", {"psf_amount": 100})
        vm.run_effect("psf_set_fra_cgt_support", {"psf_amount": 100})
        vm.run_effect("psf_hold_election_fra")
        self.assertEqual(vm.state.variables[group_var("fra_pcf", "vote_share")], 0)
        self.assertEqual(vm.state.variables[group_var("fra_cgt", "vote_share")], 0)
        votes = sum(vm.state.variables[group_var(group["id"], "vote_share")] for group in self.profile_map["fra"]["groups"])
        self.assertAlmostEqual(votes, 100)
        self.assertEqual(vm.state.variables["psf_election_count"], 1)

    def test_electoral_pact_can_win_and_remain_a_pact_while_governing(self):
        vm = self.vm("fra")
        for group in self.profile_map["fra"]["groups"]:
            if group["electoral"]:
                vm.state.variables[group_var(group["id"], "support")] = 0
        for gid, support in (("fra_radical", 20), ("fra_sfio", 20), ("fra_pcf", 20), ("fra_ad", 39), ("fra_fr", 1)):
            vm.state.variables[group_var(gid, "support")] = support
        vm.run_effect("psf_refresh")
        vm.run_effect("psf_hold_election_fra")
        pact = next(a for a in self.profile_map["fra"]["alliances"] if a["id"] == "fra_popular_front")
        self.assertEqual(vm.state.variables["psf_governing_alliance"], pact["_index"])
        self.assertEqual(vm.state.variables[alliance_var(pact["id"], "role")], 1)
        self.assertEqual(vm.state.variables[alliance_var(pact["id"], "electoral")], 1)
        self.assertEqual(vm.state.variables[group_var("fra_cgt", "governing")], 1)
        self.assertEqual(vm.state.variables[group_var("fra_cgt", "vote_share")], 0)

    def test_regime_and_government_ideology_are_distinct_with_legitimacy_cost(self):
        aligned, divergent = self.vm("sov"), self.vm("sov")
        ideology = divergent.state.variables["psf_government_ideology"]
        regime = divergent.state.variables["psf_regime"]
        divergent.run_effect("psf_set_regime_workers_monarchy")
        self.assertNotEqual(divergent.state.variables["psf_regime"], regime)
        self.assertEqual(divergent.state.variables["psf_government_ideology"], ideology)
        self.assertGreater(divergent.state.variables["psf_alignment_gap"], aligned.state.variables["psf_alignment_gap"])
        aligned.run_effect("psf_monthly_sov")
        divergent.run_effect("psf_monthly_sov")
        self.assertLess(divergent.state.variables["psf_legitimacy"], aligned.state.variables["psf_legitimacy"])
        before = divergent.state.variables["psf_legitimacy"]
        divergent.run_effect("psf_rebuild_public_confidence")
        self.assertAlmostEqual(divergent.state.variables["psf_legitimacy"], min(100, before + 6))

    def test_low_cohesion_unhappy_member_defects(self):
        vm = self.vm()
        vm.state.variables[alliance_var("eng_government", "cohesion")] = 10
        vm.state.variables[group_var("eng_national_labour", "satisfaction")] = 1
        vm.run_effect("psf_monthly_eng")
        self.assertEqual(vm.state.variables[alliance_var("eng_government", "g_eng_national_labour")], 0)
        self.assertEqual(vm.state.variables[group_var("eng_national_labour", "governing")], 0)
        self.assertEqual(vm.state.variables["psf_coalition_changed"], 1)

    def test_election_winner_with_no_previous_influence_can_form_cabinet(self):
        vm = self.vm()
        for group in self.profile_map["eng"]["groups"]:
            if group["electoral"]:
                vm.state.variables[group_var(group["id"], "support")] = 0
        vm.state.variables[group_var("eng_labour", "support")] = 100
        vm.state.variables[group_var("eng_labour", "influence")] = 0
        vm.run_effect("psf_refresh")
        vm.run_effect("psf_hold_election_eng")
        self.assertEqual(vm.state.variables[group_var("eng_labour", "governing")], 1)
        self.assertGreaterEqual(vm.state.variables[group_var("eng_labour", "influence")], 10)
        self.assertEqual(vm.state.variables["psf_caretaker"], 0)

    def test_empty_alliance_deactivates_when_its_last_member_leaves(self):
        vm = self.vm()
        alliance = next(a for a in self.profile_map["eng"]["alliances"] if a["id"] == "eng_labour_movement")
        for gid in alliance["members"]:
            vm.run_effect(f"psf_leave_{alliance['id']}_{gid}")
        self.assertEqual(vm.state.variables[alliance_var(alliance["id"], "active")], 0)
        self.assertEqual(vm.state.variables[alliance_var(alliance["id"], "member_count")], 0)

    def test_aligned_opposition_is_united_by_shared_discontent(self):
        vm = self.vm()
        aid = "eng_labour_movement"
        alliance = next(a for a in self.profile_map["eng"]["alliances"] if a["id"] == aid)
        for gid in alliance["members"]:
            vm.state.variables[group_var(gid, "satisfaction")] = 1
            for axis in self.manifest["axes"]:
                vm.state.variables[group_var(gid, "position_" + axis["id"])] = 0
        vm.state.variables[alliance_var(aid, "cohesion")] = 60
        vm.run_effect("psf_refresh")
        vm.run_effect("psf_monthly_eng")
        self.assertGreater(vm.state.variables[alliance_var(aid, "cohesion")], 60)
        for gid in alliance["members"]:
            self.assertEqual(vm.state.variables[alliance_var(aid, "g_" + gid)], 1)

    def test_bookmark_overrides_apply_on_the_exact_date(self):
        before = self.vm("fra", date=(1938, 12, 31))
        after = self.vm("fra", date=(1939, 1, 1))
        self.assertEqual(before.state.variables[group_var("fra_psf", "status")], 0)
        self.assertEqual(after.state.variables[group_var("fra_psf", "status")], 1)
        self.assertEqual(after.state.variables["psf_election_clock"], 39)
        self.assertEqual(after.state.variables[alliance_var("fra_popular_front", "active")], 0)

    def test_bookmark_alliance_kind_switch_updates_ballot_role(self):
        altered = copy.deepcopy(self.manifest)
        profile = next(p for p in altered["profiles"] if p["id"] == "eng")
        profile["start_overrides"].append({"date": "1939.2.1", "alliances": [{"id": "eng_labour_movement", "kind": "electoral"}]})
        # Re-emit only initialization: this verifies the actual override code.
        from psf.script import emit
        init = entries(parse(emit([runtime.initialize_effect(altered, profile)])))[0]
        vm = Interpreter(State(tag="ENG", date=(1939, 2, 1)))
        vm.effects = {**self.effects, init.key: init.value}
        vm.triggers = self.triggers
        vm.run_effect("psf_init_eng")
        self.assertEqual(vm.state.variables[alliance_var("eng_labour_movement", "electoral")], 1)
        self.assertEqual(vm.state.variables[alliance_var("eng_labour_movement", "role")], 3)

    def test_engine_percentage_point_swing_is_imported_at_correct_scale(self):
        vm = self.vm()
        compatible = copy.deepcopy(self.manifest)
        compatible["settings"].update(mechanics_mode="compat", bridge_mode="bidirectional")
        vm.effects = {**self.effects, **{node.key: node.value for node in entries(parse(runtime.effects(compatible)))}}
        ideologies = {i["_index"]: i["engine_ideology"] for i in self.manifest["ideologies"]}
        democratic_groups = [g for g in self.profile_map["eng"]["groups"] if g["electoral"] and ideologies[vm.state.variables[group_var(g["id"], "ideology")]] == "democratic"]
        before = sum(vm.state.variables[group_var(g["id"], "support")] for g in democratic_groups)
        total = vm.state.variables["psf_total_party_support"]
        vm.state.popularities["democratic"] -= 10
        vm.state.popularities["fascism"] += 10
        vm.run_effect("psf_import_popularity")
        after = sum(vm.state.variables[group_var(g["id"], "support")] for g in democratic_groups)
        self.assertAlmostEqual(before - after, total * 0.10, places=5)

    def test_reordering_definitions_preserves_saved_registry_ids(self):
        reordered = copy.deepcopy(self.manifest)
        reordered["profiles"].reverse()
        reordered["ideologies"].reverse()
        reordered["regimes"].reverse()
        for profile in model.profiles(reordered):
            profile["groups"].reverse()
            profile["alliances"].reverse()
        changed_effects = {node.key: node.value for node in entries(parse(runtime.effects(reordered)))}
        vm = self.vm()
        other = Interpreter(State(tag="ENG"))
        other.effects = {**self.effects, **changed_effects}
        other.triggers = self.triggers
        other.run_effect("psf_init_eng")
        self.assertEqual(vm.state.variables["psf_governing_alliance"], other.state.variables["psf_governing_alliance"])
        self.assertEqual(vm.state.variables["psf_regime"], other.state.variables["psf_regime"])
        for group in self.profile_map["eng"]["groups"]:
            self.assertEqual(vm.state.variables[group_var(group["id"], "status")], other.state.variables[group_var(group["id"], "status")])
