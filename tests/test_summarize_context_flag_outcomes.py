"""Tests for context flag outcome summarizer validations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.summarize_context_flag_outcomes import (
    build_day2_cohorts,
    build_cohort_players,
    detect_missing_player_reason,
    extract_cache_paths_from_source_notes,
    name_matches_expected,
    row_matches_cohort_rule,
    validate_known_2025_skill_picks,
)


class SourceNoteParsingTests(unittest.TestCase):
    def test_extract_cache_paths(self) -> None:
        notes = "player_stats=cache:data/external/nflverse/player_stats.csv; draft_picks=download:data/external/nflverse/draft_picks.csv"
        stats_path, draft_path = extract_cache_paths_from_source_notes(notes)
        self.assertEqual(stats_path, Path("data/external/nflverse/player_stats.csv"))
        self.assertEqual(draft_path, Path("data/external/nflverse/draft_picks.csv"))


class KnownPickValidationTests(unittest.TestCase):
    def test_name_matching_supports_abbreviated_forms(self) -> None:
        self.assertTrue(name_matches_expected("T.Hunter", "Travis Hunter"))
        self.assertTrue(name_matches_expected("T Hunter", "Travis Hunter"))
        self.assertTrue(name_matches_expected("Tetairoa McMillan", "T.McMillan"))
        self.assertFalse(name_matches_expected("T.Burden", "Travis Hunter"))

    def test_validation_succeeds_when_expected_players_exist(self) -> None:
        rows = [
            {"player_name": "Travis Hunter", "position": "WR", "draft_year": 2025, "overall_pick": 2},
            {"player_name": "Tetairoa McMillan", "position": "WR", "draft_year": 2025, "overall_pick": 8},
            {"player_name": "Colston Loveland", "position": "TE", "draft_year": 2025, "overall_pick": 10},
        ]
        warnings = validate_known_2025_skill_picks(
            normalized_rows=rows,
            source_metadata={"latest_stats_season": 2025, "latest_draft_year": 2025},
        )
        self.assertEqual(warnings, [])

    def test_validation_accepts_abbreviated_player_names(self) -> None:
        rows = [
            {"player_name": "T.Hunter", "position": "WR", "draft_year": 2025, "overall_pick": 2},
            {"player_name": "T McMillan", "position": "WR", "draft_year": 2025, "overall_pick": 8},
            {"player_name": "C.Loveland", "position": "TE", "draft_year": 2025, "overall_pick": 10},
        ]
        warnings = validate_known_2025_skill_picks(
            normalized_rows=rows,
            source_metadata={"latest_stats_season": 2025, "latest_draft_year": 2025},
        )
        self.assertEqual(warnings, [])

    def test_reason_prefers_missing_draft_data_signal(self) -> None:
        reason = detect_missing_player_reason(
            expected={"player_name": "Travis Hunter", "position": "WR", "draft_year": 2025, "overall_pick": 2},
            outcome_rows=[],
            draft_source_rows=[],
            stats_source_rows=[],
            latest_stats_season=2024,
            latest_draft_year=2024,
        )
        self.assertEqual(reason, "missing 2025 draft data")

    def test_reason_detects_id_join_mismatch(self) -> None:
        reason = detect_missing_player_reason(
            expected={"player_name": "Travis Hunter", "position": "WR", "draft_year": 2025, "overall_pick": 2},
            outcome_rows=[],
            draft_source_rows=[{"player_name": "Travis Hunter", "season": "2025", "position": "WR"}],
            stats_source_rows=[{"player_name": "Travis Hunter", "season": "2025", "position": "WR"}],
            latest_stats_season=2025,
            latest_draft_year=2025,
        )
        self.assertEqual(reason, "ID join mismatch")

    def test_validation_uses_source_note_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_path = Path(tmpdir) / "stats.csv"
            draft_path = Path(tmpdir) / "draft.csv"
            stats_path.write_text(
                "player_name,season,position\nTravis Hunter,2025,WR\nTetairoa McMillan,2025,WR\n",
                encoding="utf-8",
            )
            draft_path.write_text(
                "player_name,season,position,pick\nTravis Hunter,2025,WR,2\nTetairoa McMillan,2025,WR,8\n",
                encoding="utf-8",
            )
            metadata = {
                "latest_stats_season": 2025,
                "latest_draft_year": 2025,
                "source_notes": f"player_stats=cache:{stats_path}; draft_picks=cache:{draft_path}",
            }
            warnings = validate_known_2025_skill_picks(normalized_rows=[], source_metadata=metadata)
            self.assertTrue(any("Colston Loveland" in warning for warning in warnings))


class CohortFilteringTests(unittest.TestCase):
    def test_day2_cohort_definitions_include_expected_names(self) -> None:
        cohorts = build_day2_cohorts(2020)
        self.assertIn("wr_round2_since_2020", cohorts)
        self.assertIn("wr_round3_since_2020", cohorts)
        self.assertIn("wr_day2_since_2020", cohorts)
        self.assertIn("early_round2_skill_since_2020", cohorts)

    def test_generic_filter_supports_round_and_pick_ranges(self) -> None:
        rule = {
            "positions": ["WR", "RB", "TE"],
            "since": 2020,
            "min_round": 2,
            "max_round": 3,
            "min_pick": 33,
            "max_pick": 102,
        }
        included = {
            "player_id": "p1",
            "player_name": "Included",
            "position": "WR",
            "draft_year": 2021,
            "draft_round": 2,
            "overall_pick": 40,
            "career_year": 1,
            "ppr_points": 100.0,
            "ppr_per_game": 10.0,
        }
        too_early_pick = {**included, "player_id": "p2", "overall_pick": 30}
        too_late_round = {**included, "player_id": "p3", "draft_round": 4, "overall_pick": 110}
        wrong_position = {**included, "player_id": "p4", "position": "QB", "overall_pick": 60}

        self.assertTrue(row_matches_cohort_rule(included, rule))
        self.assertFalse(row_matches_cohort_rule(too_early_pick, rule))
        self.assertFalse(row_matches_cohort_rule(too_late_round, rule))
        self.assertFalse(row_matches_cohort_rule(wrong_position, rule))

        cohort_players = build_cohort_players([included, too_early_pick, too_late_round, wrong_position], rule)
        self.assertEqual(len(cohort_players), 1)
        self.assertEqual(cohort_players[0]["player_name"], "Included")


if __name__ == "__main__":
    unittest.main()
