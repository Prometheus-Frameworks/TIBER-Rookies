import json
import unittest
from pathlib import Path

from scripts.compute_historical_comps import (
    MARKET_WEIGHTS,
    REQUIRED_HISTORICAL_FEATURE_FIELDS,
    REQUIRED_HISTORICAL_OUTCOME_FIELDS,
    build_comp_candidates,
    compute_historical_comps,
    normalize_historical_feature_rows,
    normalize_outcome_rows,
    validate_required_fields,
    weighted_distance,
)


class ComputeHistoricalCompsTests(unittest.TestCase):
    def test_sample_historical_feature_shape_validation(self) -> None:
        sample_path = Path("data/historical/historical_prospect_features.sample.json")
        rows = json.loads(sample_path.read_text(encoding="utf-8"))
        self.assertIsInstance(rows, list)
        validate_required_fields(rows, REQUIRED_HISTORICAL_FEATURE_FIELDS, "historical features")

    def test_sample_historical_outcome_shape_validation(self) -> None:
        sample_path = Path("data/historical/historical_player_outcomes.sample.json")
        rows = json.loads(sample_path.read_text(encoding="utf-8"))
        self.assertIsInstance(rows, list)
        validate_required_fields(rows, REQUIRED_HISTORICAL_OUTCOME_FIELDS, "historical outcomes")

    def test_deterministic_similarity_ordering_with_tie_break(self) -> None:
        rookie = {
            "player_id": "r1",
            "player_name": "Rookie One",
            "position": "QB",
            "ras_0_100": 70.0,
            "production_0_100": 70.0,
            "size_context_0_100": None,
            "draft_capital_proxy_0_100": 70.0,
        }
        historical = normalize_historical_feature_rows(
            [
                {
                    "player_id": "qb-z",
                    "player_name": "QB Z",
                    "position": "QB",
                    "school": "A",
                    "draft_year": 2018,
                    "source_season": 2017,
                    "ras_0_100": 70.0,
                    "production_0_100": 70.0,
                    "draft_capital_proxy_0_100": 70.0,
                },
                {
                    "player_id": "qb-a",
                    "player_name": "QB A",
                    "position": "QB",
                    "school": "B",
                    "draft_year": 2019,
                    "source_season": 2018,
                    "ras_0_100": 70.0,
                    "production_0_100": 70.0,
                    "draft_capital_proxy_0_100": 70.0,
                },
            ]
        )
        comps = build_comp_candidates(rookie, historical, {}, comp_mode="talent_comp", top_n=2)
        self.assertEqual(comps[0]["historical_player_id"], "qb-a")
        self.assertEqual(comps[1]["historical_player_id"], "qb-z")

    def test_position_only_matching(self) -> None:
        rookie = {
            "player_id": "r2",
            "player_name": "Rookie WR",
            "position": "WR",
            "ras_0_100": 80.0,
            "production_0_100": 82.0,
            "size_context_0_100": 60.0,
            "draft_capital_proxy_0_100": 75.0,
        }
        historical = normalize_historical_feature_rows(
            [
                {
                    "player_id": "wr-1",
                    "player_name": "WR One",
                    "position": "WR",
                    "school": "A",
                    "draft_year": 2020,
                    "source_season": 2019,
                    "ras_0_100": 80.0,
                    "production_0_100": 82.0,
                    "draft_capital_proxy_0_100": 75.0,
                },
                {
                    "player_id": "rb-1",
                    "player_name": "RB One",
                    "position": "RB",
                    "school": "B",
                    "draft_year": 2020,
                    "source_season": 2019,
                    "ras_0_100": 80.0,
                    "production_0_100": 82.0,
                    "draft_capital_proxy_0_100": 75.0,
                },
            ]
        )
        comps = build_comp_candidates(rookie, historical, {}, comp_mode="talent_comp", top_n=5)
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["historical_player_id"], "wr-1")

    def test_null_handling_missing_values(self) -> None:
        rookie = {
            "player_id": "r3",
            "player_name": "Null Rookie",
            "position": "TE",
            "ras_0_100": None,
            "production_0_100": 55.0,
            "size_context_0_100": None,
            "draft_capital_proxy_0_100": None,
        }
        historical = {
            "player_id": "te-1",
            "player_name": "TE One",
            "position": "TE",
            "school": "X",
            "draft_year": 2021,
            "source_season": 2020,
            "ras_0_100": None,
            "production_0_100": 55.0,
            "draft_capital_proxy_0_100": None,
            "size_context_0_100": None,
        }
        distance = weighted_distance(rookie, historical, {"ras_0_100": 0.5, "production_0_100": 0.5})
        self.assertEqual(distance, 0.0)

    def test_zero_overlap_candidates_are_excluded(self) -> None:
        rookie = {
            "player_id": "r4",
            "player_name": "No Overlap Rookie",
            "position": "TE",
            "ras_0_100": None,
            "production_0_100": None,
            "size_context_0_100": None,
            "draft_capital_proxy_0_100": None,
        }
        historical = normalize_historical_feature_rows(
            [
                {
                    "player_id": "te-no-overlap",
                    "player_name": "TE No Overlap",
                    "position": "TE",
                    "school": "X",
                    "draft_year": 2019,
                    "source_season": 2018,
                    "ras_0_100": None,
                    "production_0_100": None,
                    "draft_capital_proxy_0_100": None,
                    "size_context_0_100": None,
                }
            ]
        )
        comps = build_comp_candidates(rookie, historical, {}, comp_mode="talent_comp", top_n=5)
        self.assertEqual(comps, [])

    def test_market_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(MARKET_WEIGHTS.values()), 1.0)

    def test_artifact_shape_for_emitted_output(self) -> None:
        rookies = [
            {
                "player_id": "qb-r",
                "player_name": "Rookie QB",
                "position": "QB",
                "ras_0_100": 74.0,
                "production_0_100": 80.0,
                "draft_capital_proxy_0_100": 90.0,
                "size_context_0_100": 72.0,
            }
        ]
        historical_features = normalize_historical_feature_rows(
            [
                {
                    "player_id": "qb-h",
                    "player_name": "Historical QB",
                    "position": "QB",
                    "school": "Sample",
                    "draft_year": 2018,
                    "source_season": 2017,
                    "ras_0_100": 74.0,
                    "production_0_100": 80.0,
                    "draft_capital_proxy_0_100": 90.0,
                    "size_context_0_100": 72.0,
                }
            ]
        )
        outcomes = normalize_outcome_rows(
            [
                {
                    "player_id": "qb-h",
                    "player_name": "Historical QB",
                    "position": "QB",
                    "draft_year": 2018,
                    "career_outcome_label": None,
                    "best_season_fantasy_ppg": None,
                    "top_finish_band": None,
                    "years_1_to_3_summary": None,
                }
            ]
        )

        artifact = compute_historical_comps(
            season=2026,
            rookies=rookies,
            historical_features=historical_features,
            outcomes_by_player_id=outcomes,
            comp_mode="talent_comp",
            top_n=3,
            source_files_used=["a", "b"],
            generated_at="2026-03-28T00:00:00+00:00",
        )

        self.assertEqual(artifact["season"], 2026)
        self.assertEqual(artifact["model"]["comp_mode"], "talent_comp")
        self.assertEqual(len(artifact["players"]), 1)
        self.assertIn("comps", artifact["players"][0])
        self.assertEqual(artifact["players"][0]["comps"][0]["historical_player_id"], "qb-h")


if __name__ == "__main__":
    unittest.main()
