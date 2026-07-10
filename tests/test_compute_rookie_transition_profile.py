import json
import tempfile
import unittest
from pathlib import Path

from scripts.compute_rookie_transition_profile import (
    age_from_dob,
    build_age_field,
    build_athletic_testing_field,
    build_college_production_field,
    build_coverage_summary,
    build_draft_capital_field,
    build_official_postdraft_outcome_field,
    build_rows,
    write_csv,
    write_json,
)
from scripts.validate_rookie_transition_profile import validate_artifact_shape, validate_field


class AgeFromDobTests(unittest.TestCase):
    def test_matches_compute_breakout_age_formula(self) -> None:
        # Born 2004-09-02: as of 2026-09-01 they have not yet had their 22nd
        # birthday for the season, so age is 21, not 22.
        self.assertEqual(age_from_dob("2004-09-02", 2026), 21)
        self.assertEqual(age_from_dob("2004-09-01", 2026), 22)

    def test_invalid_dob_returns_none(self) -> None:
        self.assertIsNone(age_from_dob("not-a-date", 2026))


class BuildDraftCapitalFieldTests(unittest.TestCase):
    def test_missing_proxy_score_is_unavailable(self) -> None:
        field = build_draft_capital_field({}, None, as_of_date="2026-07-01")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")

    def test_present_score_is_market_derived_proxy(self) -> None:
        field = build_draft_capital_field(
            {"draft_capital_proxy_0_100": 95.0},
            {"big_board_rank": 1, "draft_capital_proxy_source": "Test proxy rule"},
            as_of_date="2026-07-01",
        )
        self.assertEqual(field["value"], {"big_board_rank": 1, "draft_capital_proxy_0_100": 95.0})
        self.assertEqual(field["provenance"]["source_type"], "market_derived_proxy")
        self.assertEqual(field["provenance"]["source_name"], "Test proxy rule")
        self.assertEqual(validate_field(field, prefix="draft_capital"), [])

    def test_missing_upstream_row_still_produces_valid_field(self) -> None:
        field = build_draft_capital_field({"draft_capital_proxy_0_100": 75.0}, None, as_of_date="2026-07-01")
        self.assertEqual(validate_field(field, prefix="draft_capital"), [])
        self.assertIn("upstream big_board_rank row not found", field["provenance"]["source_name"])


class BuildAgeFieldTests(unittest.TestCase):
    def test_missing_context_row_is_unavailable(self) -> None:
        field = build_age_field(None, season=2026, as_of_date="2026-07-01")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")

    def test_present_dob_is_measured_identity_fact(self) -> None:
        field = build_age_field({"dob": "2004-01-01"}, season=2026, as_of_date="2026-07-01")
        self.assertEqual(field["value"], 22)
        self.assertEqual(field["provenance"]["source_type"], "measured_identity_fact")
        self.assertEqual(validate_field(field, prefix="age_at_entry"), [])

    def test_unparseable_dob_is_unavailable(self) -> None:
        field = build_age_field({"dob": "garbage"}, season=2026, as_of_date="2026-07-01")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")


class BuildAthleticTestingFieldTests(unittest.TestCase):
    def test_neutral_default_is_unavailable_not_a_placeholder_value(self) -> None:
        """NEUTRAL_DEFAULT is Rookie Alpha's internal scoring placeholder, not a
        measurement, so it must never be presented as observed evidence here."""
        field = build_athletic_testing_field(
            {"athletic_source": "NEUTRAL_DEFAULT", "athletic_score_0_100": 50.0, "athletic_confidence": 0.5},
            as_of_date="2026-07-01",
        )
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")

    def test_real_ras_is_measured_combine(self) -> None:
        field = build_athletic_testing_field(
            {
                "athletic_source": "RAS",
                "athletic_score_0_100": 88.0,
                "athletic_confidence": 1.0,
                "athletic_explainer": "RAS 88.0 from 5 combine metrics",
            },
            as_of_date="2026-07-01",
        )
        self.assertEqual(field["value"], {"athletic_score_0_100": 88.0, "athletic_source": "RAS"})
        self.assertEqual(field["provenance"]["source_type"], "measured_combine")
        self.assertEqual(field["provenance"]["confidence"], 1.0)
        self.assertEqual(field["provenance"]["confidence_band"], "HIGH")
        self.assertIn("Kent Lee Platte", field["provenance"]["notes"])
        self.assertEqual(validate_field(field, prefix="athletic_testing"), [])


class BuildCollegeProductionFieldTests(unittest.TestCase):
    def test_missing_score_is_unavailable(self) -> None:
        field = build_college_production_field({}, None, as_of_date="2026-07-01")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")

    def test_present_score_is_measured_production_stats(self) -> None:
        field = build_college_production_field(
            {"production_0_100": 81.2},
            {"production_score_source": "CFBD 2025 season stats"},
            as_of_date="2026-07-01",
        )
        self.assertEqual(field["value"], {"production_score_0_100": 81.2})
        self.assertEqual(field["provenance"]["source_type"], "measured_production_stats")
        self.assertEqual(validate_field(field, prefix="college_production"), [])


class BuildOfficialPostdraftOutcomeFieldTests(unittest.TestCase):
    """Regression coverage for issue #267: drafted, UDFA-signed, and
    unavailable outcomes, plus the requirement that this field never
    overwrites or is derived from draft_capital."""

    def test_drafted_outcome_from_draft_results(self) -> None:
        draft_result_row = {
            "nfl_team": "LV",
            "draft_round": 1,
            "overall_pick": 1,
            "source_status": "external_verified",
            "upstream_provenance_status": "source_verified",
            "source_name": "Test tracker",
            "source_url": "https://example.com",
            "ingested_at": "2026-05-17",
        }
        field = build_official_postdraft_outcome_field(draft_result_row, None, as_of_date="2026-07-10")
        self.assertEqual(field["value"]["status"], "drafted")
        self.assertEqual(field["value"]["is_udfa"], False)
        self.assertEqual(field["value"]["draft_round"], 1)
        self.assertEqual(field["value"]["overall_pick"], 1)
        self.assertEqual(field["provenance"]["source_type"], "official_draft_result")
        self.assertEqual(field["provenance"]["last_verified_at"], "2026-05-17")
        self.assertEqual(validate_field(field, prefix="official_postdraft_outcome"), [])

    def test_udfa_signed_outcome_from_udfa_file_when_absent_from_draft_results(self) -> None:
        udfa_row = {
            "draft_result_status": "udfa_signed",
            "nfl_team": "PHI",
            "draft_round": None,
            "overall_pick": None,
            "is_udfa": True,
            "source_status": "external_verified",
            "source_url": "https://example.com/eagles",
            "source_note": "Eagles announced signing.",
        }
        field = build_official_postdraft_outcome_field(None, udfa_row, as_of_date="2026-07-10")
        self.assertEqual(field["value"]["status"], "udfa_signed")
        self.assertEqual(field["value"]["is_udfa"], True)
        self.assertIsNone(field["value"]["draft_round"])
        self.assertIsNone(field["value"]["overall_pick"])
        self.assertEqual(field["provenance"]["source_type"], "official_draft_result")
        # No per-row timestamp in the UDFA file, so falls back to as_of_date.
        self.assertEqual(field["provenance"]["last_verified_at"], "2026-07-10")
        self.assertEqual(validate_field(field, prefix="official_postdraft_outcome"), [])

    def test_draft_results_take_priority_over_udfa_file_when_both_present(self) -> None:
        draft_result_row = {
            "nfl_team": "SEA", "draft_round": 3, "overall_pick": 90,
            "source_status": "external_verified", "upstream_provenance_status": "source_verified",
            "source_name": "Test tracker", "source_url": "https://example.com", "ingested_at": "2026-05-17",
        }
        udfa_row = {
            "draft_result_status": "udfa_signed", "nfl_team": "XXX", "draft_round": None,
            "overall_pick": None, "is_udfa": True, "source_status": "external_verified",
            "source_url": "https://example.com/other", "source_note": "should not be used",
        }
        field = build_official_postdraft_outcome_field(draft_result_row, udfa_row, as_of_date="2026-07-10")
        self.assertEqual(field["value"]["status"], "drafted")
        self.assertEqual(field["value"]["nfl_team"], "SEA")

    def test_unavailable_when_no_verified_record_in_either_source(self) -> None:
        field = build_official_postdraft_outcome_field(None, None, as_of_date="2026-07-10")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")
        self.assertEqual(validate_field(field, prefix="official_postdraft_outcome"), [])

    def test_unverified_draft_result_row_is_treated_as_unavailable(self) -> None:
        draft_result_row = {
            "nfl_team": "LV", "draft_round": 1, "overall_pick": 1,
            "source_status": "needs_verification",
        }
        field = build_official_postdraft_outcome_field(draft_result_row, None, as_of_date="2026-07-10")
        self.assertIsNone(field["value"])
        self.assertEqual(field["provenance"]["source_type"], "unavailable")


class BuildRowsAndArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.alpha_players = [
            {
                "player_id": "wr-full-data",
                "player_name": "Full Data",
                "position": "WR",
                "scores": {
                    "draft_capital_proxy_0_100": 85.0,
                    "athletic_source": "RAS",
                    "athletic_score_0_100": 90.0,
                    "athletic_confidence": 0.95,
                    "athletic_explainer": "RAS 90.0 from 4 combine metrics",
                    "production_0_100": 70.0,
                },
                "context": {"school": "Test A", "class_year": 2026},
            },
            {
                "player_id": "wr-sparse-data",
                "player_name": "Sparse Data",
                "position": "WR",
                "scores": {
                    "draft_capital_proxy_0_100": 45.0,
                    "athletic_source": "NEUTRAL_DEFAULT",
                    "athletic_score_0_100": 50.0,
                    "athletic_confidence": 0.5,
                    "production_0_100": None,
                },
                "context": {},
            },
        ]
        self.draft_capital_by_id = {
            "wr-full-data": {"big_board_rank": 10, "draft_capital_proxy_source": "seed"},
        }
        self.production_by_id = {
            "wr-full-data": {"production_score_source": "CFBD 2025 season stats"},
        }
        self.context_by_id = {
            "wr-full-data": {"dob": "2004-06-01"},
        }
        self.draft_results_by_id = {
            "wr-full-data": {
                "nfl_team": "SEA",
                "draft_round": 2,
                "overall_pick": 50,
                "source_status": "external_verified",
                "upstream_provenance_status": "source_verified",
                "source_name": "Test draft tracker",
                "source_url": "https://example.com/draft",
                "ingested_at": "2026-05-01",
            },
        }
        self.udfa_results_by_id: dict = {}

    def _build_rows(self):
        return build_rows(
            season=2026,
            alpha_players=self.alpha_players,
            draft_capital_by_id=self.draft_capital_by_id,
            production_by_id=self.production_by_id,
            context_by_id=self.context_by_id,
            draft_results_by_id=self.draft_results_by_id,
            udfa_results_by_id=self.udfa_results_by_id,
            as_of_date="2026-07-10",
        )

    def test_build_rows_matches_full_and_sparse_players(self) -> None:
        rows = self._build_rows()
        self.assertEqual(len(rows), 2)
        full_row = next(r for r in rows if r["player_id"] == "wr-full-data")
        sparse_row = next(r for r in rows if r["player_id"] == "wr-sparse-data")

        self.assertEqual(full_row["school"], "Test A")
        self.assertIsNotNone(full_row["draft_capital"]["value"])
        self.assertIsNotNone(full_row["age_at_entry"]["value"])
        self.assertIsNotNone(full_row["athletic_testing"]["value"])
        self.assertIsNotNone(full_row["college_production"]["value"])
        self.assertIsNotNone(full_row["official_postdraft_outcome"]["value"])
        self.assertEqual(full_row["official_postdraft_outcome"]["value"]["status"], "drafted")
        # draft_capital must remain the pre-draft proxy, unaffected by the
        # official outcome being available (issue #267's core requirement).
        self.assertEqual(full_row["draft_capital"]["provenance"]["source_type"], "market_derived_proxy")

        self.assertIsNone(sparse_row["age_at_entry"]["value"])
        self.assertIsNone(sparse_row["athletic_testing"]["value"])
        self.assertIsNone(sparse_row["college_production"]["value"])
        self.assertIsNone(sparse_row["official_postdraft_outcome"]["value"])
        self.assertEqual(sparse_row["official_postdraft_outcome"]["provenance"]["source_type"], "unavailable")

    def test_build_coverage_summary_counts_available_values(self) -> None:
        rows = self._build_rows()
        summary = build_coverage_summary(rows)
        self.assertEqual(summary["players_total"], 2)
        self.assertEqual(summary["players_with_draft_capital"], 2)
        self.assertEqual(summary["players_with_age_at_entry"], 1)
        self.assertEqual(summary["players_with_athletic_testing"], 1)
        self.assertEqual(summary["players_with_college_production"], 1)
        self.assertEqual(summary["players_with_official_postdraft_outcome"], 1)
        self.assertEqual(summary["players_with_all_families"], 1)

    def test_built_rows_pass_full_shape_validation(self) -> None:
        rows = self._build_rows()
        artifact = {
            "schema_version": "rookie-transition-profile-v0.2.0",
            "artifact_type": "rookie_transition_profile",
            "season": 2026,
            "generated_at": "2026-07-10T00:00:00+00:00",
            "run_id": "rookie-transition-profile-2026-test",
            "disclaimer": "This artifact is an evidence consolidation layer.",
            "source_files_used": ["a", "b", "c", "d", "e", "f"],
            "coverage_summary": build_coverage_summary(rows),
            "rows": rows,
        }
        self.assertEqual(validate_artifact_shape(artifact), [])

    def test_write_json_and_csv_outputs(self) -> None:
        rows = self._build_rows()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_json = Path(temp_dir) / "profile.json"
            output_csv = Path(temp_dir) / "profile.csv"
            write_json(output_json, {"rows": rows})
            write_csv(output_csv, rows)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["rows"]), 2)
            self.assertTrue(output_csv.exists())
            csv_text = output_csv.read_text(encoding="utf-8")
            self.assertIn("wr-full-data", csv_text)
            self.assertIn("wr-sparse-data", csv_text)


if __name__ == "__main__":
    unittest.main()
