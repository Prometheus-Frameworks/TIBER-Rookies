import copy
import json
import unittest
from pathlib import Path

from scripts.compute_devy_league_market_snapshot_diff import compute_diff
from scripts.validate_devy_league_market_snapshot import validate_devy_league_market_snapshot


class DevyLeagueMarketSnapshotWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot_path = Path("data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json")
        self.seed_path = Path("data/devy/devy_seed_watchlist_2026.json")
        self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        self.seed = json.loads(self.seed_path.read_text(encoding="utf-8"))

    def test_snapshot_fixture_validates(self) -> None:
        self.assertEqual(validate_devy_league_market_snapshot(self.snapshot), [])

    def test_derrek_cooper_resolves_as_known_seed_watchlist_player(self) -> None:
        diff = compute_diff(self.snapshot, self.seed)
        known = diff["drafted_and_known_by_tiber"]
        self.assertTrue(any(row["seed_player_id"] == "derrek-cooper" for row in known))

    def test_aaron_gregory_resolves_as_missing_and_monthly_pulse_candidate(self) -> None:
        diff = compute_diff(self.snapshot, self.seed)
        missing_rows = [row for row in diff["drafted_missing_from_tiber"] if row["player_name_normalized"] == "Aaron Gregory"]
        self.assertEqual(len(missing_rows), 1)
        self.assertTrue(missing_rows[0]["coverage_gap_candidate"])
        self.assertFalse(missing_rows[0]["auto_add_to_seed_watchlist"])

        pulse_rows = [row for row in diff["recommended_monthly_pulse_candidates"] if row["player_name_normalized"] == "Aaron Gregory"]
        self.assertEqual(len(pulse_rows), 1)
        self.assertEqual(pulse_rows[0]["auto_seed_watchlist_mutation"], "none")

    def test_identity_unresolved_rows_are_flagged(self) -> None:
        diff = compute_diff(self.snapshot, self.seed)
        unresolved = diff["identity_conflicts_or_unresolved"]
        self.assertTrue(any(row["player_name_normalized"] == "Brendan Sorsby" for row in unresolved))

    def test_snapshot_workflow_has_scoring_truth_guardrails(self) -> None:
        diff = compute_diff(self.snapshot, self.seed)
        warnings_text = " ".join(diff["warnings"]).lower()
        self.assertIn("not be treated as rankings", warnings_text)
        self.assertIn("do not route", warnings_text)

    def test_validation_fails_without_required_privacy_notes(self) -> None:
        invalid = copy.deepcopy(self.snapshot)
        invalid["privacy_notes"] = []
        errors = validate_devy_league_market_snapshot(invalid)
        self.assertTrue(any("privacy_notes must be a non-empty list" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
