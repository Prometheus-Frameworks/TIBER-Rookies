"""Tests for context flag outcome summarizer validations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.summarize_context_flag_outcomes import (
    detect_missing_player_reason,
    extract_cache_paths_from_source_notes,
    validate_known_2025_skill_picks,
)


class SourceNoteParsingTests(unittest.TestCase):
    def test_extract_cache_paths(self) -> None:
        notes = "player_stats=cache:data/external/nflverse/player_stats.csv; draft_picks=download:data/external/nflverse/draft_picks.csv"
        stats_path, draft_path = extract_cache_paths_from_source_notes(notes)
        self.assertEqual(stats_path, Path("data/external/nflverse/player_stats.csv"))
        self.assertEqual(draft_path, Path("data/external/nflverse/draft_picks.csv"))


class KnownPickValidationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
