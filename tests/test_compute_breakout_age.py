import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import tempfile
import os

from scripts.compute_breakout_age import (
    estimated_age,
    find_academic_year,
    compute_breakout_for_player,
    update_context_entry,
    make_minimal_context_entry,
    BREAKOUT_THRESHOLDS,
    YOUNG_BREAKOUT_MAX_AGE,
)


class EstimatedAgeTests(unittest.TestCase):
    def test_freshman_is_18(self) -> None:
        self.assertEqual(estimated_age(1), 18)

    def test_sophomore_is_19(self) -> None:
        self.assertEqual(estimated_age(2), 19)

    def test_junior_is_20(self) -> None:
        self.assertEqual(estimated_age(3), 20)

    def test_senior_is_21(self) -> None:
        self.assertEqual(estimated_age(4), 21)

    def test_fifth_year_is_22(self) -> None:
        self.assertEqual(estimated_age(5), 22)


class FindAcademicYearTests(unittest.TestCase):
    def _roster(self) -> list[dict]:
        return [
            {"fullName": "Jane Doe", "year": 2},
            {"fullName": "John Smith", "year": 3},
            {"first_name": "Alice", "last_name": "Jones", "year": 1},
        ]

    def test_finds_by_full_name(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "Jane Doe"), 2)

    def test_finds_by_first_last_name(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "Alice Jones"), 1)

    def test_returns_none_when_not_found(self) -> None:
        self.assertIsNone(find_academic_year(self._roster(), "Nobody Here"))

    def test_case_insensitive(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "JANE DOE"), 2)

    def test_empty_roster(self) -> None:
        self.assertIsNone(find_academic_year([], "Jane Doe"))


class BreakoutThresholdTests(unittest.TestCase):
    def test_all_positions_defined(self) -> None:
        for pos in ("WR", "TE", "QB", "RB"):
            self.assertIn(pos, BREAKOUT_THRESHOLDS)

    def test_young_breakout_max_age_is_20(self) -> None:
        self.assertEqual(YOUNG_BREAKOUT_MAX_AGE, 20)


class ComputeBreakoutTests(unittest.TestCase):
    def _make_args(self, tmp_dir: Path) -> MagicMock:
        args = MagicMock()
        args.wr_dir = tmp_dir
        args.qb_dir = tmp_dir
        args.rb_dir = tmp_dir
        return args

    def _write_profile(self, tmp_dir: Path, player_id: str, season: int, data: dict) -> None:
        path = tmp_dir / f"{player_id}_{season}.json"
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_wr_young_breakout_sophomore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_profile(tmp, "wr-jane-doe", 2024, {"targets": 60})
            self._write_profile(tmp, "wr-jane-doe", 2025, {"targets": 75})
            args = self._make_args(tmp)
            roster_cache: dict = {}
            roster_cache[("State U", 2024)] = [{"fullName": "Jane Doe", "year": 2}]
            player = {"player_id": "wr-jane-doe", "player_name": "Jane Doe",
                      "position": "WR", "school": "State U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertEqual(result["breakout_age"], 19)  # sophomore = 17+2
            self.assertTrue(result["young_breakout_flag"])

    def test_wr_late_breakout_senior(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_profile(tmp, "wr-jane-doe", 2024, {"targets": 10})  # below threshold
            self._write_profile(tmp, "wr-jane-doe", 2025, {"targets": 60})
            args = self._make_args(tmp)
            roster_cache: dict = {}
            roster_cache[("State U", 2025)] = [{"fullName": "Jane Doe", "year": 4}]
            player = {"player_id": "wr-jane-doe", "player_name": "Jane Doe",
                      "position": "WR", "school": "State U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertEqual(result["breakout_age"], 21)  # senior = 17+4
            self.assertFalse(result["young_breakout_flag"])

    def test_no_breakout_season(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_profile(tmp, "wr-jane-doe", 2024, {"targets": 5})
            self._write_profile(tmp, "wr-jane-doe", 2025, {"targets": 10})
            args = self._make_args(tmp)
            roster_cache: dict = {}
            player = {"player_id": "wr-jane-doe", "player_name": "Jane Doe",
                      "position": "WR", "school": "State U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertIsNone(result["breakout_age"])
            self.assertIsNone(result["young_breakout_flag"])

    def test_qb_breakout_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_profile(tmp, "qb-joe-qb", 2025, {"pass_attempts": 200})
            args = self._make_args(tmp)
            roster_cache = {("Big U", 2025): [{"fullName": "Joe QB", "year": 3}]}
            player = {"player_id": "qb-joe-qb", "player_name": "Joe QB",
                      "position": "QB", "school": "Big U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertEqual(result["breakout_age"], 20)
            self.assertTrue(result["young_breakout_flag"])

    def test_rb_breakout_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_profile(tmp, "rb-joe-rb", 2025, {"rush_attempts": 100})
            args = self._make_args(tmp)
            roster_cache = {("Big U", 2025): [{"fullName": "Joe RB", "year": 2}]}
            player = {"player_id": "rb-joe-rb", "player_name": "Joe RB",
                      "position": "RB", "school": "Big U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertEqual(result["breakout_age"], 19)

    def test_missing_profile_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self._make_args(Path(td))
            roster_cache: dict = {}
            player = {"player_id": "wr-nobody", "player_name": "No Body",
                      "position": "WR", "school": "Nowhere U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertIsNone(result["breakout_age"])


class UpdateContextEntryTests(unittest.TestCase):
    def test_young_breakout_adds_evidence_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": [], "context_flags": []}
        result = update_context_entry(existing, {"breakout_age": 19, "age_at_first_impact_season": 19, "young_breakout_flag": True}, {})
        self.assertIn("young_breakout", result["evidence_tags"])

    def test_late_breakout_does_not_add_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": [], "context_flags": []}
        result = update_context_entry(existing, {"breakout_age": 22, "age_at_first_impact_season": 22, "young_breakout_flag": False}, {})
        self.assertNotIn("young_breakout", result["evidence_tags"])

    def test_removes_stale_young_breakout_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": ["young_breakout"], "context_flags": []}
        result = update_context_entry(existing, {"breakout_age": 22, "age_at_first_impact_season": 22, "young_breakout_flag": False}, {})
        self.assertNotIn("young_breakout", result["evidence_tags"])


if __name__ == "__main__":
    unittest.main()
