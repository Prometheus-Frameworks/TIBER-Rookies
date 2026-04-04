"""Tests for compute_age_adjusted_production.py"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.compute_age_adjusted_production import (
    AGE_MULTIPLIER_FLOOR,
    age_multiplier,
    normalize_scores,
    weighted_volume,
)


class AgeMultiplierTests(unittest.TestCase):
    def test_age_19_is_2x(self) -> None:
        self.assertAlmostEqual(age_multiplier(19), 2.0)

    def test_age_20_is_1_5x(self) -> None:
        self.assertAlmostEqual(age_multiplier(20), 1.5)

    def test_age_21_is_baseline(self) -> None:
        self.assertAlmostEqual(age_multiplier(21), 1.0)

    def test_age_22_is_floored(self) -> None:
        self.assertAlmostEqual(age_multiplier(22), AGE_MULTIPLIER_FLOOR)

    def test_age_25_still_floored(self) -> None:
        self.assertAlmostEqual(age_multiplier(25), AGE_MULTIPLIER_FLOOR)

    def test_null_breakout_age_is_neutral(self) -> None:
        self.assertAlmostEqual(age_multiplier(None), 1.0)

    def test_multiplier_increases_for_younger(self) -> None:
        self.assertGreater(age_multiplier(19), age_multiplier(20))
        self.assertGreater(age_multiplier(20), age_multiplier(21))


class NormalizeScoresTests(unittest.TestCase):
    def test_empty_list(self) -> None:
        self.assertEqual(normalize_scores([]), [])

    def test_all_same_scores_return_50(self) -> None:
        result = normalize_scores([10.0, 10.0, 10.0])
        self.assertEqual(result, [50.0, 50.0, 50.0])

    def test_min_is_0_max_is_100(self) -> None:
        result = normalize_scores([0.0, 50.0, 100.0])
        self.assertAlmostEqual(result[0], 0.0)
        self.assertAlmostEqual(result[2], 100.0)

    def test_preserves_order(self) -> None:
        scores = [10.0, 40.0, 70.0]
        result = normalize_scores(scores)
        self.assertLess(result[0], result[1])
        self.assertLess(result[1], result[2])


class WeightedVolumeTests(unittest.TestCase):
    def _write_profile(self, directory: Path, player_id: str, season: int, field: str, value: float) -> None:
        path = directory / f"{player_id}_{season}.json"
        path.write_text(json.dumps({field: value}))

    def test_both_seasons_uses_best_and_recent_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            # class_year=2026: recent=2025, prior=2024
            self._write_profile(d, "wr-player", 2025, "targets", 40.0)
            self._write_profile(d, "wr-player", 2024, "targets", 60.0)
            wvol, best, recent = weighted_volume("wr-player", 2026, "targets", d)
            self.assertAlmostEqual(best, 60.0)
            self.assertAlmostEqual(recent, 40.0)
            # 0.7 × 60 + 0.3 × 40 = 42 + 12 = 54
            self.assertAlmostEqual(wvol, 54.0)

    def test_recent_is_best_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_profile(d, "wr-player", 2025, "targets", 80.0)
            self._write_profile(d, "wr-player", 2024, "targets", 50.0)
            wvol, best, recent = weighted_volume("wr-player", 2026, "targets", d)
            self.assertAlmostEqual(best, 80.0)
            # 0.7 × 80 + 0.3 × 80 = 80 (both weights on same value)
            self.assertAlmostEqual(wvol, 80.0)

    def test_only_one_season_uses_full_weight(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_profile(d, "wr-player", 2025, "targets", 55.0)
            wvol, best, recent = weighted_volume("wr-player", 2026, "targets", d)
            self.assertAlmostEqual(wvol, 55.0)

    def test_no_profiles_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wvol, best, recent = weighted_volume("wr-nobody", 2026, "targets", Path(tmpdir))
            self.assertAlmostEqual(wvol, 0.0)
            self.assertAlmostEqual(best, 0.0)

    def test_young_breakout_raw_score_higher_than_late(self) -> None:
        """Player with same volume but younger breakout should outscore older player."""
        volume = 60.0
        young_raw = volume * age_multiplier(19)
        late_raw = volume * age_multiplier(21)
        self.assertGreater(young_raw, late_raw)
