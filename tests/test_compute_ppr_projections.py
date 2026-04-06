"""Tests for compute_ppr_projections.py"""
from __future__ import annotations

import unittest

from scripts.compute_ppr_projections import (
    BANDS,
    PPR_RANGES,
    alpha_band,
    project_player,
)


class AlphaBandTests(unittest.TestCase):
    def test_100_is_elite(self) -> None:
        self.assertEqual(alpha_band(100.0), "Elite")

    def test_80_is_elite(self) -> None:
        self.assertEqual(alpha_band(80.0), "Elite")

    def test_79_is_starter(self) -> None:
        self.assertEqual(alpha_band(79.0), "Starter")

    def test_55_is_starter(self) -> None:
        self.assertEqual(alpha_band(55.0), "Starter")

    def test_54_is_contributor(self) -> None:
        self.assertEqual(alpha_band(54.0), "Contributor")

    def test_30_is_contributor(self) -> None:
        self.assertEqual(alpha_band(30.0), "Contributor")

    def test_29_is_lottery(self) -> None:
        self.assertEqual(alpha_band(29.0), "Lottery")

    def test_0_is_lottery(self) -> None:
        self.assertEqual(alpha_band(0.0), "Lottery")


class PPRRangesTests(unittest.TestCase):
    def test_all_positions_defined(self) -> None:
        for pos in ("WR", "RB", "QB", "TE"):
            self.assertIn(pos, PPR_RANGES)

    def test_all_bands_defined_per_position(self) -> None:
        band_labels = {label for label, _, _ in BANDS}
        for pos, ranges in PPR_RANGES.items():
            self.assertEqual(set(ranges.keys()), band_labels, f"{pos} missing bands")

    def test_floor_lt_median_lt_ceiling(self) -> None:
        for pos, ranges in PPR_RANGES.items():
            for band, (floor_, median_, ceiling_) in ranges.items():
                self.assertLess(floor_, median_, f"{pos}/{band}: floor >= median")
                self.assertLess(median_, ceiling_, f"{pos}/{band}: median >= ceiling")

    def test_elite_ceiling_higher_than_starter_ceiling(self) -> None:
        for pos in PPR_RANGES:
            elite_ceil = PPR_RANGES[pos]["Elite"][2]
            starter_ceil = PPR_RANGES[pos]["Starter"][2]
            self.assertGreater(elite_ceil, starter_ceil, f"{pos} Elite ceiling not > Starter ceiling")

    def test_wr_elite_ceiling_is_240(self) -> None:
        self.assertEqual(PPR_RANGES["WR"]["Elite"][2], 240)


class ProjectPlayerTests(unittest.TestCase):
    def _player(self, alpha: float, position: str = "WR", missing: list[str] | None = None) -> dict:
        return {
            "player_id": f"{position.lower()}-test",
            "player_name": "Test Player",
            "position": position,
            "scores": {"rookie_alpha_0_100": alpha},
            "rookie_alpha_rank": 1,
            "model_inputs_missing": missing or [],
        }

    def test_wr_elite_alpha_gets_elite_band(self) -> None:
        proj = project_player(self._player(85.0, "WR"))
        self.assertEqual(proj.projection_band, "Elite")
        self.assertEqual(proj.ppr_ceiling, 240)

    def test_rb_starter_alpha_gets_starter_band(self) -> None:
        proj = project_player(self._player(65.0, "RB"))
        self.assertEqual(proj.projection_band, "Starter")
        self.assertEqual(proj.ppr_median, 135)

    def test_qb_contributor_alpha(self) -> None:
        proj = project_player(self._player(45.0, "QB"))
        self.assertEqual(proj.projection_band, "Contributor")
        self.assertEqual(proj.ppr_floor, 80)

    def test_te_lottery_alpha(self) -> None:
        proj = project_player(self._player(15.0, "TE"))
        self.assertEqual(proj.projection_band, "Lottery")
        self.assertEqual(proj.ppr_median, 20)

    def test_data_gap_flag_when_missing_inputs(self) -> None:
        proj = project_player(self._player(50.0, "WR", missing=["ras"]))
        self.assertTrue(proj.data_gap_flag)
        self.assertIsNotNone(proj.data_gap_note)

    def test_no_data_gap_when_complete(self) -> None:
        proj = project_player(self._player(75.0, "WR"))
        self.assertFalse(proj.data_gap_flag)
        self.assertIsNone(proj.data_gap_note)

    def test_unknown_position_falls_back_to_lottery(self) -> None:
        player = self._player(90.0, "K")  # kicker — not in PPR_RANGES
        proj = project_player(player)
        self.assertEqual(proj.projection_band, "Lottery")
