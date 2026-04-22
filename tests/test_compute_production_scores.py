import unittest

from scripts.compute_production_scores import (
    apply_results,
    build_stat_lines,
    build_team_passing_totals,
    compute_scores_for_seed,
    normalize_identity,
    pivot_stats,
    school_aliases,
)


class ComputeProductionScoresTests(unittest.TestCase):
    def test_normalize_identity(self) -> None:
        self.assertEqual(normalize_identity("Miami (FL)"), "miami (fl)")
        self.assertEqual(normalize_identity("J.J. Mc-Carthy"), "jj mccarthy")

    def test_school_aliases(self) -> None:
        self.assertIn("miami", school_aliases("Miami (FL)"))
        self.assertIn("miss st", school_aliases("Mississippi State"))

    def test_pivot_stats_merges_stat_rows(self) -> None:
        rows = [
            {"player": "A", "team": "X", "statType": "YDS", "stat": "100"},
            {"player": "A", "team": "X", "statType": "TD", "stat": "2"},
        ]
        pivoted = pivot_stats(rows)
        self.assertEqual(len(pivoted), 1)
        entry = next(iter(pivoted.values()))
        self.assertEqual(entry["stats"]["YDS"], 100.0)
        self.assertEqual(entry["stats"]["TD"], 2.0)

    def test_compute_scores_for_seed_qb(self) -> None:
        passing_rows = [
            {"player": "QB One", "team": "Indiana", "statType": "ATT", "stat": "200"},
            {"player": "QB One", "team": "Indiana", "statType": "COMPLETIONS", "stat": "140"},
            {"player": "QB One", "team": "Indiana", "statType": "YDS", "stat": "2500"},
            {"player": "QB One", "team": "Indiana", "statType": "TD", "stat": "24"},
            {"player": "QB One", "team": "Indiana", "statType": "INT", "stat": "8"},
            {"player": "QB Two", "team": "Ohio State", "statType": "ATT", "stat": "220"},
            {"player": "QB Two", "team": "Ohio State", "statType": "COMPLETIONS", "stat": "150"},
            {"player": "QB Two", "team": "Ohio State", "statType": "YDS", "stat": "2800"},
            {"player": "QB Two", "team": "Ohio State", "statType": "TD", "stat": "28"},
            {"player": "QB Two", "team": "Ohio State", "statType": "INT", "stat": "6"},
        ]
        seed_rows = [
            {"player_id": "p1", "player_name": "QB One", "position": "QB", "school": "Indiana"},
        ]
        results = compute_scores_for_seed(seed_rows, pivot_stats(passing_rows), {}, {})
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].score)
        self.assertEqual(results[0].match_mode, "primary")

    def test_apply_results_null_on_failed(self) -> None:
        seed = [{"player_id": "p1", "production_score_0_100": 88.8, "production_score_source": "PFF"}]
        result_seed = apply_results(
            seed,
            [
                type(
                    "R",
                    (),
                    {
                        "player_id": "p1",
                        "score": None,
                        "source": None,
                    },
                )()
            ],
        )
        self.assertIsNone(result_seed[0]["production_score_0_100"])
        self.assertIsNone(result_seed[0]["production_score_source"])

    def test_build_stat_lines_qb_and_failed_player(self) -> None:
        passing_rows = [
            {"player": "QB One", "team": "Indiana", "statType": "ATT", "stat": "200"},
            {"player": "QB One", "team": "Indiana", "statType": "COMPLETIONS", "stat": "140"},
            {"player": "QB One", "team": "Indiana", "statType": "YDS", "stat": "2500"},
            {"player": "QB One", "team": "Indiana", "statType": "TD", "stat": "24"},
            {"player": "QB One", "team": "Indiana", "statType": "INT", "stat": "8"},
        ]
        seed_rows = [
            {"player_id": "p1", "player_name": "QB One", "position": "QB", "school": "Indiana"},
            {"player_id": "p2", "player_name": "QB Missing", "position": "QB", "school": "Nowhere"},
        ]
        results = compute_scores_for_seed(seed_rows, pivot_stats(passing_rows), {}, {})
        stat_lines = build_stat_lines(seed_rows, results, pivot_stats(passing_rows), {}, {}, 2025)
        self.assertEqual(len(stat_lines), 2)
        self.assertEqual(stat_lines[0]["stats"]["completions"], 140)
        self.assertEqual(stat_lines[0]["stats"]["completion_pct"], 70)
        self.assertEqual(stat_lines[0]["stats"]["yards_per_attempt"], 12.5)
        self.assertEqual(stat_lines[1]["stats"], {})



    def test_dominator_rating_wr(self) -> None:
        passing_rows = [
            {"player": "QB One", "team": "Oregon", "statType": "YDS", "stat": "3000"},
            {"player": "QB One", "team": "Oregon", "statType": "TD", "stat": "20"},
        ]
        receiving_rows = [
            {"player": "WR One", "team": "Oregon", "statType": "REC", "stat": "80"},
            {"player": "WR One", "team": "Oregon", "statType": "YDS", "stat": "1000"},
            {"player": "WR One", "team": "Oregon", "statType": "TD", "stat": "8"},
        ]
        seed_rows = [
            {"player_id": "wr-one", "player_name": "WR One", "position": "WR", "school": "Oregon"},
        ]
        passing_stats = pivot_stats(passing_rows)
        receiving_stats = pivot_stats(receiving_rows)
        team_totals = build_team_passing_totals(passing_stats)
        results = compute_scores_for_seed(seed_rows, passing_stats, {}, receiving_stats)
        stat_lines = build_stat_lines(seed_rows, results, passing_stats, {}, receiving_stats, 2025, team_totals)
        self.assertEqual(len(stat_lines), 1)
        # dominator_rating = (1000 + 8*20) / (3000 + 20*20) = 1160 / 3400
        expected = round(1160 / 3400, 1)
        self.assertAlmostEqual(stat_lines[0]["stats"]["dominator_rating"], expected, places=1)

    def test_dominator_rating_absent_without_team_totals(self) -> None:
        receiving_rows = [
            {"player": "WR One", "team": "Oregon", "statType": "REC", "stat": "80"},
            {"player": "WR One", "team": "Oregon", "statType": "YDS", "stat": "1000"},
            {"player": "WR One", "team": "Oregon", "statType": "TD", "stat": "8"},
        ]
        seed_rows = [
            {"player_id": "wr-one", "player_name": "WR One", "position": "WR", "school": "Oregon"},
        ]
        receiving_stats = pivot_stats(receiving_rows)
        results = compute_scores_for_seed(seed_rows, {}, {}, receiving_stats)
        stat_lines = build_stat_lines(seed_rows, results, {}, {}, receiving_stats, 2025)
        self.assertNotIn("dominator_rating", stat_lines[0]["stats"])


if __name__ == "__main__":
    unittest.main()
