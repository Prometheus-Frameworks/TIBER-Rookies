"""Tests for nfl fantasy outcomes builder."""

from __future__ import annotations

import unittest

from scripts.build_nfl_fantasy_outcomes import (
    build_player_outcome_rows,
    career_year_for_season,
    compute_ppr,
)


class PPRFormulaTests(unittest.TestCase):
    def test_ppr_formula_receiving_and_rushing(self) -> None:
        # 5 rec + 60 rec yds + 1 rec td + 20 rush yds + 1 rush td
        ppr = compute_ppr(5, 60, 1, 20, 1)
        self.assertEqual(ppr, 25.0)


class CareerYearTests(unittest.TestCase):
    def test_career_year(self) -> None:
        self.assertEqual(career_year_for_season(2022, 2022), 1)
        self.assertEqual(career_year_for_season(2022, 2024), 3)


class BuilderJoinTests(unittest.TestCase):
    def test_build_rows_from_draft_and_stats(self) -> None:
        draft_rows = [
            {
                "gsis_id": "00-001",
                "player_name": "Test Receiver",
                "position": "WR",
                "season": "2022",
                "round": "1",
                "pick": "8",
                "team": "ATL",
            }
        ]
        stats_rows = [
            {
                "gsis_id": "00-001",
                "player_name": "Test Receiver",
                "position": "WR",
                "season": "2022",
                "games": "10",
                "receptions": "50",
                "receiving_yards": "700",
                "receiving_tds": "6",
                "rushing_yards": "40",
                "rushing_tds": "1",
            }
        ]

        rows = build_player_outcome_rows(stats_rows, draft_rows, source_notes="fixture")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["career_year"], 1)
        self.assertEqual(rows[0]["ppr_points"], 166.0)
        self.assertEqual(rows[0]["ppr_per_game"], 16.6)


if __name__ == "__main__":
    unittest.main()
