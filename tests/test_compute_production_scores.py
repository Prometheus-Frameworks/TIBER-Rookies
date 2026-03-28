import unittest

from scripts.compute_production_scores import (
    apply_results,
    build_stat_lines,
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



if __name__ == "__main__":
    unittest.main()
