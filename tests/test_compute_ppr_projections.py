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
    """Tests for project_player.

    v2 adds player-level modifiers, so exact PPR values may differ from
    the base band lookup.  Band assignment is still deterministic from
    alpha alone, so we assert band correctness and use range checks for
    the adjusted floor / median / ceiling values.
    """

    def _player(self, alpha: float, position: str = "WR", missing: list[str] | None = None,
                production: float | None = None, draft_capital: float | None = None,
                ras: float | None = None, breakout_age: int | None = None,
                young_breakout: bool = False) -> dict:
        scores: dict = {"rookie_alpha_0_100": alpha}
        if production is not None:
            scores["production_0_100"] = production
        if draft_capital is not None:
            scores["draft_capital_proxy_0_100"] = draft_capital
        if ras is not None:
            scores["ras_0_100"] = ras
        context: dict = {}
        if breakout_age is not None:
            context["breakout_age"] = breakout_age
        if young_breakout:
            context["young_breakout_flag"] = True
        return {
            "player_id": f"{position.lower()}-test",
            "player_name": "Test Player",
            "position": position,
            "scores": scores,
            "rookie_alpha_rank": 1,
            "model_inputs_missing": missing or [],
            "context": context,
        }

    def test_wr_elite_alpha_gets_elite_band(self) -> None:
        proj = project_player(self._player(85.0, "WR"))
        self.assertEqual(proj.projection_band, "Elite")

    def test_rb_starter_alpha_gets_starter_band(self) -> None:
        proj = project_player(self._player(65.0, "RB"))
        self.assertEqual(proj.projection_band, "Starter")

    def test_qb_contributor_alpha(self) -> None:
        proj = project_player(self._player(45.0, "QB"))
        self.assertEqual(proj.projection_band, "Contributor")

    def test_te_lottery_alpha(self) -> None:
        proj = project_player(self._player(15.0, "TE"))
        self.assertEqual(proj.projection_band, "Lottery")

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

    def test_floor_lt_median_lt_ceiling(self) -> None:
        """All projections must maintain floor < median < ceiling."""
        for pos in ("WR", "RB", "TE", "QB"):
            for alpha in (10, 40, 60, 90):
                proj = project_player(self._player(float(alpha), pos))
                self.assertLess(proj.ppr_floor, proj.ppr_median,
                                f"{pos} alpha={alpha}: floor >= median")
                self.assertLess(proj.ppr_median, proj.ppr_ceiling,
                                f"{pos} alpha={alpha}: median >= ceiling")


class ProjectionModifierTests(unittest.TestCase):
    """Tests for v2 player-level modifiers."""

    def _player(self, alpha: float, position: str = "WR", **kwargs) -> dict:
        scores: dict = {"rookie_alpha_0_100": alpha}
        context: dict = {}
        for k, v in kwargs.items():
            if k in ("production", "draft_capital", "ras", "age_adj_production"):
                score_key = {
                    "production": "production_0_100",
                    "draft_capital": "draft_capital_proxy_0_100",
                    "ras": "ras_0_100",
                    "age_adj_production": "age_adjusted_production_0_100",
                }[k]
                scores[score_key] = v
            elif k == "breakout_age":
                context["breakout_age"] = v
            elif k == "young_breakout":
                context["young_breakout_flag"] = v
        return {
            "player_id": f"{position.lower()}-mod-test",
            "player_name": "Modifier Test",
            "position": position,
            "scores": scores,
            "rookie_alpha_rank": 1,
            "model_inputs_missing": kwargs.get("missing", []),
            "context": context,
        }

    def test_high_capital_raises_median(self) -> None:
        base = project_player(self._player(65.0, "RB"))
        boosted = project_player(self._player(65.0, "RB", draft_capital=95.0))
        self.assertGreater(boosted.ppr_median, base.ppr_median)

    def test_low_capital_lowers_median(self) -> None:
        base = project_player(self._player(65.0, "RB"))
        penalized = project_player(self._player(65.0, "RB", draft_capital=10.0))
        self.assertLess(penalized.ppr_median, base.ppr_median)

    def test_high_production_raises_wr_median(self) -> None:
        base = project_player(self._player(65.0, "WR"))
        boosted = project_player(self._player(65.0, "WR", production=90.0))
        self.assertGreater(boosted.ppr_median, base.ppr_median)

    def test_young_breakout_tightens_range(self) -> None:
        no_breakout = project_player(self._player(65.0, "WR", production=70.0))
        young = project_player(self._player(65.0, "WR", production=70.0,
                                            breakout_age=19, young_breakout=True))
        no_spread = no_breakout.ppr_ceiling - no_breakout.ppr_floor
        young_spread = young.ppr_ceiling - young.ppr_floor
        self.assertLessEqual(young_spread, no_spread)

    def test_te_default_volatile(self) -> None:
        """TE position should default to wider ranges (Volatile label)."""
        proj = project_player(self._player(65.0, "TE", production=50.0))
        self.assertEqual(proj.projection_volatility, "Volatile")

    def test_missing_inputs_widens_range(self) -> None:
        clean = project_player(self._player(65.0, "WR", production=70.0))
        gappy = project_player(self._player(65.0, "WR", production=70.0,
                                            missing=["ras", "combine"]))
        gappy_spread = gappy.ppr_ceiling - gappy.ppr_floor
        clean_spread = clean.ppr_ceiling - clean.ppr_floor
        self.assertGreaterEqual(gappy_spread, clean_spread)

    def test_method_is_v2_with_signals(self) -> None:
        proj = project_player(self._player(65.0, "WR", production=70.0))
        self.assertEqual(proj.projection_method, "alpha_band_v2")

    def test_method_is_v1_fallback_without_signals(self) -> None:
        proj = project_player(self._player(65.0, "WR"))
        self.assertEqual(proj.projection_method, "alpha_band_v1_fallback")

    def test_confidence_high_for_strong_signals(self) -> None:
        proj = project_player(self._player(75.0, "WR", production=80.0, draft_capital=80.0))
        self.assertEqual(proj.projection_confidence, "High")

    def test_confidence_low_for_weak_signals(self) -> None:
        proj = project_player(self._player(25.0, "WR", missing=["ras", "combine"]))
        self.assertEqual(proj.projection_confidence, "Low")

    def test_thesis_is_nonempty_string(self) -> None:
        proj = project_player(self._player(65.0, "WR", production=70.0))
        self.assertIsInstance(proj.projection_thesis, str)
        self.assertGreater(len(proj.projection_thesis), 10)

    def test_modifiers_capped(self) -> None:
        """Even with extreme inputs, floor < median < ceiling must hold."""
        extreme = project_player(self._player(
            90.0, "RB", production=100.0, draft_capital=100.0,
            ras=100.0, age_adj_production=100.0, young_breakout=True, breakout_age=18,
        ))
        self.assertLess(extreme.ppr_floor, extreme.ppr_median)
        self.assertLess(extreme.ppr_median, extreme.ppr_ceiling)
        self.assertGreater(extreme.ppr_floor, 0)
