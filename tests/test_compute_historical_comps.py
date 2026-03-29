import json
import unittest
from pathlib import Path

from scripts.compute_historical_comps import (
    MARKET_WEIGHTS,
    apply_wr_historical_production_methodology,
    build_ui_display_allowed,
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
                    "normalization_scope": "class-local",
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
                    "normalization_scope": "class-local",
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
                    "normalization_scope": "class-local",
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
                    "normalization_scope": "class-local",
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
            "normalization_scope": "class-local",
        }
        distance, used = weighted_distance(rookie, historical, {"ras_0_100": 0.5, "production_0_100": 0.5})
        self.assertEqual(distance, 0.0)
        self.assertEqual(used, ["production_0_100"])

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
                    "normalization_scope": "class-local",
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
                    "normalization_scope": "class-local",
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
        self.assertIn("comp_data_warnings", artifact)
        self.assertEqual(artifact["players"][0]["comps"][0]["historical_player_id"], "qb-h")
        self.assertEqual(artifact["players"][0]["comps"][0]["effective_features_used"], ["ras_0_100", "production_0_100", "size_context_0_100"] )


    def test_ui_display_allowed_present_and_position_keyed(self) -> None:
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
                    "normalization_scope": "class-local",
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
                    "career_outcome_label": "Starter",
                    "best_season_fantasy_ppg": 18.0,
                    "top_finish_band": "QB1",
                    "years_1_to_3_summary": "sample",
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

        self.assertIn("ui_display_allowed", artifact)
        self.assertIsInstance(artifact["ui_display_allowed"], dict)
        self.assertIn("QB", artifact["ui_display_allowed"])

    def test_ui_display_allowed_false_when_warning_present(self) -> None:
        players = [
            {
                "player_id": "qb-r",
                "player_name": "Rookie QB",
                "position": "QB",
                "comps": [
                    {
                        "effective_features_used": ["ras_0_100", "production_0_100", "size_context_0_100"],
                        "outcome_snapshot": {"career_outcome_label": "Starter"},
                    }
                ],
            },
            {
                "player_id": "rb-r",
                "player_name": "Rookie RB",
                "position": "RB",
                "comps": [
                    {
                        "effective_features_used": ["ras_0_100", "production_0_100", "size_context_0_100"],
                        "outcome_snapshot": {"career_outcome_label": "Starter"},
                    }
                ],
            },
        ]
        ui_display_allowed = build_ui_display_allowed(
            players,
            {"QB": "explicit warning"},
            {"QB": True, "RB": True},
        )
        self.assertFalse(ui_display_allowed["QB"])
        self.assertTrue(ui_display_allowed["RB"])

    def test_ui_display_allowed_false_when_any_comp_has_too_few_effective_features(self) -> None:
        rookies = [
            {
                "player_id": "qb-r",
                "player_name": "Rookie QB",
                "position": "QB",
                "ras_0_100": 74.0,
                "production_0_100": None,
                "draft_capital_proxy_0_100": None,
                "size_context_0_100": None,
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
                    "production_0_100": None,
                    "draft_capital_proxy_0_100": None,
                    "size_context_0_100": None,
                    "normalization_scope": "class-local",
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
                    "career_outcome_label": "Starter",
                    "best_season_fantasy_ppg": 18.0,
                    "top_finish_band": "QB1",
                    "years_1_to_3_summary": "sample",
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

        self.assertEqual(artifact["players"][0]["comps"][0]["effective_features_used"], ["ras_0_100"])
        self.assertFalse(artifact["ui_display_allowed"]["QB"])

    def test_similarity_quality_by_position_shape_and_keys(self) -> None:
        artifact = json.loads(
            Path("exports/promoted/historical-comps/2026_historical_comps_v0.json").read_text(encoding="utf-8")
        )
        self.assertIn("similarity_quality_by_position", artifact)
        self.assertIsInstance(artifact["similarity_quality_by_position"], dict)
        required_keys = {
            "no_lane_warning",
            "min_effective_feature_count_met",
            "outcomes_present",
            "non_market_dimension_present",
            "methodology_compatible",
        }
        for position, quality in artifact["similarity_quality_by_position"].items():
            self.assertIn("status", quality, msg=position)
            self.assertIn("reason", quality, msg=position)
            self.assertTrue(bool(quality["reason"]), msg=position)
            self.assertIn("requirements_checked", quality, msg=position)
            self.assertEqual(set(quality["requirements_checked"].keys()), required_keys, msg=position)

    def test_similarity_quality_wr_directional_only_when_warning_present(self) -> None:
        artifact = json.loads(
            Path("exports/promoted/historical-comps/2026_historical_comps_v0.json").read_text(encoding="utf-8")
        )
        self.assertIn("WR", artifact["comp_data_warnings"])
        self.assertEqual(artifact["similarity_quality_by_position"]["WR"]["status"], "directional_only")

    def test_methodology_compatibility_projection_matches_similarity_quality(self) -> None:
        artifact = json.loads(
            Path("exports/promoted/historical-comps/2026_historical_comps_v0.json").read_text(encoding="utf-8")
        )
        self.assertIn("methodology_compatibility_by_position", artifact)
        for position, compatible in artifact["methodology_compatibility_by_position"].items():
            self.assertEqual(
                compatible,
                artifact["similarity_quality_by_position"][position]["requirements_checked"]["methodology_compatible"],
            )

    def test_wr_historical_rows_compute_or_null_per_threshold_and_opt_out(self) -> None:
        rows = normalize_historical_feature_rows(
            [
                {
                    "player_id": "wr-scoreable",
                    "player_name": "WR Scoreable",
                    "position": "WR",
                    "school": "Sample",
                    "draft_year": 2021,
                    "source_season": 2020,
                    "ras_0_100": 70.0,
                    "production_0_100": 55.0,
                    "draft_capital_proxy_0_100": 70.0,
                    "normalization_scope": "cross-class-wr-v0",
                    "receptions": 60,
                    "receiving_yards": 1000,
                    "receiving_tds": 10,
                },
                {
                    "player_id": "wr-null-rec",
                    "player_name": "WR Null Rec",
                    "position": "WR",
                    "school": "Sample",
                    "draft_year": 2021,
                    "source_season": 2020,
                    "ras_0_100": 70.0,
                    "production_0_100": 55.0,
                    "draft_capital_proxy_0_100": 70.0,
                    "normalization_scope": "cross-class-wr-v0",
                    "receptions": None,
                    "receiving_yards": 800,
                    "receiving_tds": 8,
                },
            ]
        )
        scored = apply_wr_historical_production_methodology(rows)
        scoreable = [row for row in scored if row["player_id"] == "wr-scoreable"][0]
        null_row = [row for row in scored if row["player_id"] == "wr-null-rec"][0]
        self.assertIsNotNone(scoreable["production_0_100"])
        self.assertEqual(scoreable["normalization_scope"], "historical-wr-cfbd-method-v1")
        self.assertIsNone(null_row["production_0_100"])
        self.assertEqual(null_row["normalization_scope"], "historical-wr-cfbd-method-v1-null")

    def test_artifact_wr_contract_flags_remain_conservative(self) -> None:
        artifact = json.loads(
            Path("exports/promoted/historical-comps/2026_historical_comps_v0.json").read_text(encoding="utf-8")
        )
        self.assertFalse(artifact["methodology_compatibility_by_position"]["WR"])
        self.assertEqual(artifact["similarity_quality_by_position"]["WR"]["status"], "directional_only")
        self.assertFalse(artifact["ui_display_allowed"]["WR"])

    def test_wr_legacy_score_populated_and_non_wr_legacy_absent(self) -> None:
        features = json.loads(Path("data/historical/historical_prospect_features.sample.json").read_text(encoding="utf-8"))
        wr_rows = [row for row in features if row["position"] == "WR"]
        non_wr_rows = [row for row in features if row["position"] != "WR"]
        self.assertTrue(all("production_0_100_legacy" in row for row in wr_rows))
        self.assertTrue(all("production_0_100_legacy" not in row for row in non_wr_rows))

    def test_waddle_partial_season_policy_enforced(self) -> None:
        features = json.loads(Path("data/historical/historical_prospect_features.sample.json").read_text(encoding="utf-8"))
        waddle = [row for row in features if row.get("player_id") == "wr-jaylen-waddle-2021"][0]
        self.assertIn("partial season", str(waddle.get("notes", "")).lower())
        self.assertIsNone(waddle.get("production_0_100"))
        self.assertEqual(waddle.get("normalization_scope"), "historical-wr-cfbd-method-v1-null")

    def test_non_wr_feature_snapshots_omit_wr_only_fields(self) -> None:
        artifact = json.loads(
            Path("exports/promoted/historical-comps/2026_historical_comps_v0.json").read_text(encoding="utf-8")
        )
        qb_comps = [player for player in artifact["players"] if player["position"] == "QB"][0]["comps"]
        self.assertTrue(qb_comps)
        snapshot = qb_comps[0]["feature_snapshot"]
        self.assertNotIn("production_0_100_legacy", snapshot)
        self.assertNotIn("receptions", snapshot)
        self.assertNotIn("receiving_yards", snapshot)
        self.assertNotIn("receiving_tds", snapshot)


if __name__ == "__main__":
    unittest.main()
