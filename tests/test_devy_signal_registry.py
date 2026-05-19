import copy
import json
import unittest
from pathlib import Path

from scripts.devy_signal_registry import (
    CURRENT_DEVY_SCHEMA_VERSION,
    DevyDevelopmentHorizon,
    DevyDevelopmentTag,
    DevyLifecycleStage,
    enum_snapshot,
    expected_horizon_band,
    validate_devy_registry,
)


class DevySignalRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_path = Path("data/fixtures/devy_prospect_registry_v0_fixture.json")
        self.payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        self.seed_path = Path("data/devy/devy_seed_watchlist_2026.json")
        self.seed_payload = json.loads(self.seed_path.read_text(encoding="utf-8"))

    def test_fixture_registry_validates(self) -> None:
        self.assertEqual(validate_devy_registry(self.payload), [])

    def test_seed_watchlist_validates(self) -> None:
        self.assertEqual(validate_devy_registry(self.seed_payload), [])

    def test_seed_watchlist_long_horizon_player_is_not_near_term_actionable(self) -> None:
        prospect = next(p for p in self.seed_payload["prospects"] if p["player_id"] == "chris-henry-jr")
        self.assertEqual(prospect["development_horizon"], DevyDevelopmentHorizon.LONG_HORIZON.value)
        self.assertEqual(prospect["actionability_band"], "WATCHLIST")
        self.assertNotIn(prospect["actionability_band"], {"TARGET", "PRIORITY"})

    def test_seed_watchlist_missing_provenance_notes_fails_validation(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["identity_provenance"]["source_notes"] = []
        errors = validate_devy_registry(payload)
        self.assertTrue(any("identity_provenance.source_notes must be a non-empty list" in error for error in errors))

    def test_seed_watchlist_duplicate_player_ids_fail_validation(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][1]["player_id"] = payload["prospects"][0]["player_id"]
        errors = validate_devy_registry(payload)
        self.assertTrue(any("player_id duplicates" in error for error in errors))

    def test_seed_watchlist_invalid_horizon_and_tag_fail_validation(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["development_horizon"] = DevyDevelopmentHorizon.NEAR_TERM.value
        payload["prospects"][0]["development_tags"].append("UNSUPPORTED_TAG")
        errors = validate_devy_registry(payload)
        self.assertTrue(any("development_horizon must be" in error for error in errors))
        self.assertTrue(any("development_tags has invalid value" in error for error in errors))

    def test_enums_are_centrally_exported(self) -> None:
        snapshot = enum_snapshot()
        self.assertEqual(self.payload["schema_version"], CURRENT_DEVY_SCHEMA_VERSION)
        self.assertIn(DevyLifecycleStage.TRUE_FRESHMAN.value, snapshot["lifecycle_stages"])
        self.assertIn(DevyDevelopmentHorizon.LONG_HORIZON.value, snapshot["development_horizons"])
        self.assertIn(DevyDevelopmentTag.PRODUCTION_PENDING.value, snapshot["development_tags"])

    def test_2029_type_prospect_is_not_next_cycle_actionable(self) -> None:
        prospect = next(p for p in self.payload["prospects"] if p["player_id"] == "fixture-long-horizon-wr-2029")
        self.assertEqual(prospect["years_to_projected_draft"], 3)
        self.assertEqual(prospect["development_horizon"], DevyDevelopmentHorizon.LONG_HORIZON.value)
        self.assertEqual(prospect["actionability_band"], "WATCHLIST")
        self.assertNotEqual(prospect["development_horizon"], DevyDevelopmentHorizon.NEAR_TERM.value)
        self.assertNotIn(prospect["actionability_band"], {"TARGET", "PRIORITY"})

    def test_expected_horizon_band_treats_time_as_risk(self) -> None:
        self.assertEqual(expected_horizon_band(1), DevyDevelopmentHorizon.NEAR_TERM.value)
        self.assertEqual(expected_horizon_band(2), DevyDevelopmentHorizon.MEDIUM_TERM.value)
        self.assertEqual(expected_horizon_band(3), DevyDevelopmentHorizon.LONG_HORIZON.value)
        self.assertEqual(expected_horizon_band(4), DevyDevelopmentHorizon.PREP_OR_FUTURE.value)
        self.assertEqual(expected_horizon_band(3, DevyLifecycleStage.PREP.value), DevyDevelopmentHorizon.PREP_OR_FUTURE.value)

    def test_invalid_lifecycle_stage_fails_validation(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["prospects"][0]["lifecycle_stage"] = "NEXT_BIG_THING"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("lifecycle_stage has invalid value" in error for error in errors))

    def test_invalid_development_tag_fails_validation(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["prospects"][0]["development_tags"].append("MADE_UP_TAG")
        errors = validate_devy_registry(payload)
        self.assertTrue(any("development_tags has invalid value" in error for error in errors))

    def test_malformed_draft_class_logic_fails_validation(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["prospects"][0]["earliest_possible_draft_class"] = 2030
        payload["prospects"][0]["years_to_projected_draft"] = 1
        payload["prospects"][0]["development_horizon"] = "NEAR_TERM"
        payload["prospects"][0]["actionability_band"] = "TARGET"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("earliest_possible_draft_class cannot exceed" in error for error in errors))
        self.assertTrue(any("must equal projected_draft_class - as_of_year" in error for error in errors))

    def test_long_horizon_target_actionability_fails_validation(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["prospects"][0]["actionability_band"] = "TARGET"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("long-horizon prospect cannot be TARGET or PRIORITY" in error for error in errors))


    def test_missing_identity_provenance_fails_validation(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0].pop("identity_provenance", None)
        errors = validate_devy_registry(payload)
        self.assertTrue(any("identity_provenance must be an object" in error for error in errors))

    def test_missing_signal_provenance_fails_when_signal_fields_present(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0].pop("signal_provenance", None)
        errors = validate_devy_registry(payload)
        self.assertTrue(any("signal_provenance must be an object" in error for error in errors))

    def test_missing_timeline_provenance_fails_when_timeline_fields_present(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0].pop("timeline_provenance", None)
        errors = validate_devy_registry(payload)
        self.assertTrue(any("timeline_provenance must be an object" in error for error in errors))


    def test_identity_provenance_rejects_signal_only_source_type(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["identity_provenance"]["source_type"] = "manual_curated_seed_signal"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("identity_provenance.source_type 'manual_curated_seed_signal' is not allowed" in error for error in errors))

    def test_timeline_provenance_rejects_roster_source_type(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["timeline_provenance"]["source_type"] = "official_roster"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("timeline_provenance.source_type 'official_roster' is not allowed" in error for error in errors))

    def test_signal_provenance_rejects_roster_source_type(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["signal_provenance"]["source_type"] = "official_roster"
        errors = validate_devy_registry(payload)
        self.assertTrue(any("signal_provenance.source_type 'official_roster' is not allowed" in error for error in errors))

    def test_signal_provenance_accepts_team_context_artifact_source_type(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["signal_provenance"]["source_type"] = "team_context_artifact"
        errors = validate_devy_registry(payload)
        self.assertEqual(errors, [])

    def test_invalid_provenance_source_type_url_and_future_year_fail(self) -> None:
        payload = copy.deepcopy(self.seed_payload)
        payload["prospects"][0]["identity_provenance"]["source_type"] = "made_up_source"
        payload["prospects"][0]["identity_provenance"]["source_urls"] = ["ftp://not-allowed"]
        payload["prospects"][0]["identity_provenance"]["last_verified_year"] = payload["as_of_year"] + 1
        errors = validate_devy_registry(payload)
        self.assertTrue(any("source_type must be one of" in error for error in errors))
        self.assertTrue(any("source_urls entries must be HTTP(S) URLs" in error for error in errors))
        self.assertTrue(any("last_verified_year must be an integer no later than as_of_year" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
