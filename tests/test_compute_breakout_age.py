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
    SHARE_BREAKOUT_CRITERIA,
    YOUNG_BREAKOUT_MAX_AGE,
    _check_share_breakout,
    _compute_breakout_strength,
    _compute_breakout_confidence,
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
            {"firstName": "Bob", "lastName": "Brown", "year": 4},
        ]

    def test_finds_by_full_name(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "Jane Doe"), 2)

    def test_finds_by_first_last_name(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "Alice Jones"), 1)

    def test_returns_none_when_not_found(self) -> None:
        self.assertIsNone(find_academic_year(self._roster(), "Nobody Here"))

    def test_finds_by_camel_case_first_last_name(self) -> None:
        self.assertEqual(find_academic_year(self._roster(), "Bob Brown"), 4)

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

    def test_te_threshold_lower_than_wr(self) -> None:
        wr_field, wr_val = BREAKOUT_THRESHOLDS["WR"]
        te_field, te_val = BREAKOUT_THRESHOLDS["TE"]
        self.assertEqual(wr_field, te_field)  # both use targets
        self.assertLess(te_val, wr_val)       # TE bar is lower


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
            # New fields
            self.assertIsNotNone(result["breakout_strength"])
            self.assertIsNotNone(result["breakout_confidence"])
            self.assertGreaterEqual(result["breakout_strength"], 0.0)
            self.assertLessEqual(result["breakout_strength"], 1.0)
            self.assertGreaterEqual(result["breakout_confidence"], 0.7)
            self.assertEqual(result["seasons_available"], 2)

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
            self.assertIsNone(result["breakout_strength"])
            self.assertIsNone(result["breakout_confidence"])
            self.assertEqual(result["seasons_available"], 2)

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


class ShareBreakoutTests(unittest.TestCase):
    def test_wr_target_share_triggers_breakout(self) -> None:
        profile = {"targets": 30, "target_share": 0.25}
        met, had = _check_share_breakout(profile, "WR")
        self.assertTrue(met)
        self.assertTrue(had)

    def test_wr_below_share_does_not_trigger(self) -> None:
        profile = {"targets": 30, "target_share": 0.10}
        met, had = _check_share_breakout(profile, "WR")
        self.assertFalse(met)
        self.assertTrue(had)

    def test_qb_has_no_share_criteria(self) -> None:
        profile = {"pass_attempts": 200}
        met, had = _check_share_breakout(profile, "QB")
        self.assertFalse(met)
        self.assertFalse(had)

    def test_no_share_data_returns_false_false(self) -> None:
        profile = {"targets": 60}
        met, had = _check_share_breakout(profile, "WR")
        self.assertFalse(met)
        self.assertFalse(had)

    def test_wr_share_breakout_with_low_volume(self) -> None:
        """A WR with high target share but below raw volume threshold should
        still qualify via share-based criteria."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            args = MagicMock()
            args.wr_dir = tmp
            args.qb_dir = tmp
            args.rb_dir = tmp
            # 40 targets below raw threshold (50), but high target share
            path = tmp / "wr-share-wr_2025.json"
            path.write_text(json.dumps({"targets": 40, "target_share": 0.22}))
            roster_cache = {("Share U", 2025): [{"fullName": "Share WR", "year": 3}]}
            player = {"player_id": "wr-share-wr", "player_name": "Share WR",
                      "position": "WR", "school": "Share U", "class_year": 2026}
            result = compute_breakout_for_player(player, args, roster_cache)
            self.assertEqual(result["breakout_age"], 20)
            self.assertTrue(result["young_breakout_flag"])


class BreakoutStrengthTests(unittest.TestCase):
    def test_at_threshold_strength_is_zero(self) -> None:
        strength = _compute_breakout_strength(50, 50, {"targets": 50}, "WR")
        self.assertAlmostEqual(strength, 0.0)

    def test_double_threshold_strength_is_max(self) -> None:
        strength = _compute_breakout_strength(100, 50, {"targets": 100}, "WR")
        self.assertAlmostEqual(strength, 1.0)

    def test_share_data_blends_with_volume(self) -> None:
        profile = {"targets": 75, "target_share": 0.30}  # 0.30 vs 0.20 threshold
        strength = _compute_breakout_strength(75, 50, profile, "WR")
        # volume part: (75/50 - 1) = 0.5; share part: (0.30/0.20 - 1) = 0.5
        self.assertAlmostEqual(strength, 0.5)


class BreakoutConfidenceTests(unittest.TestCase):
    def test_two_seasons_no_share(self) -> None:
        conf = _compute_breakout_confidence(2, False)
        self.assertAlmostEqual(conf, 0.90)

    def test_one_season_no_share(self) -> None:
        conf = _compute_breakout_confidence(1, False)
        self.assertAlmostEqual(conf, 0.80)

    def test_two_seasons_with_share(self) -> None:
        conf = _compute_breakout_confidence(2, True)
        self.assertAlmostEqual(conf, 1.00)

    def test_confidence_range(self) -> None:
        for s in range(3):
            for share in (True, False):
                conf = _compute_breakout_confidence(s, share)
                self.assertGreaterEqual(conf, 0.7)
                self.assertLessEqual(conf, 1.0)


class UpdateContextEntryTests(unittest.TestCase):
    def _breakout_data(self, age, flag, strength=0.5, confidence=0.9):
        return {
            "breakout_age": age,
            "age_at_first_impact_season": age,
            "young_breakout_flag": flag,
            "breakout_strength": strength,
            "breakout_confidence": confidence,
            "seasons_available": 2,
        }

    def test_young_breakout_adds_evidence_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": [], "context_flags": []}
        result = update_context_entry(existing, self._breakout_data(19, True), {})
        self.assertIn("young_breakout", result["evidence_tags"])

    def test_late_breakout_does_not_add_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": [], "context_flags": []}
        result = update_context_entry(existing, self._breakout_data(22, False), {})
        self.assertNotIn("young_breakout", result["evidence_tags"])

    def test_removes_stale_young_breakout_tag(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": ["young_breakout"], "context_flags": []}
        result = update_context_entry(existing, self._breakout_data(22, False), {})
        self.assertNotIn("young_breakout", result["evidence_tags"])

    def test_new_fields_present(self) -> None:
        existing = {"player_id": "wr-x", "evidence_tags": [], "context_flags": []}
        result = update_context_entry(existing, self._breakout_data(19, True, 0.8, 1.0), {})
        self.assertEqual(result["breakout_strength"], 0.8)
        self.assertEqual(result["breakout_confidence"], 1.0)
        self.assertEqual(result["seasons_available"], 2)


if __name__ == "__main__":
    unittest.main()
