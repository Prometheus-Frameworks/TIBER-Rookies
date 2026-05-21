import copy
import json
import unittest
from pathlib import Path

from scripts.validate_devy_roster_pulse import validate_devy_roster_pulse


class DevyRosterPulseValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_path = Path("data/devy/monthly_pulse/devy_roster_pulse_2026_05.json")
        self.payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))

    def test_fixture_validates(self) -> None:
        self.assertEqual(validate_devy_roster_pulse(self.payload), [])

    def test_missing_source_notes_fails_closed(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["candidates"][0]["source_notes"] = []
        errors = validate_devy_roster_pulse(payload)
        self.assertTrue(any("source_notes must be a non-empty list" in error for error in errors))

    def test_missing_prior_stats_does_not_allow_confirmed_freshman_tag(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["candidates"][0]["prior_college_production_found"] = False
        payload["candidates"][0]["candidate_tags"].append("confirmed_freshman")
        errors = validate_devy_roster_pulse(payload)
        self.assertTrue(any("cannot set confirmed_freshman from missing prior stats alone" in error for error in errors))

    def test_missing_prior_stats_and_unknown_class_source_cannot_confirm_freshman(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["candidates"][0]["prior_college_production_found"] = False
        payload["candidates"][0]["class_year_source"] = "unknown"
        payload["candidates"][0]["freshman_status"] = "confirmed"
        errors = validate_devy_roster_pulse(payload)
        self.assertTrue(any("cannot mark freshman_status='confirmed'" in error for error in errors))

    def test_pulse_cannot_auto_mutate_seed_watchlist(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["candidates"][0]["auto_seed_watchlist_mutation"] = "append_to_seed_watchlist"
        errors = validate_devy_roster_pulse(payload)
        self.assertTrue(any("auto_seed_watchlist_mutation must be 'none'" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
