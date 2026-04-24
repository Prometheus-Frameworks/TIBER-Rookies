"""Tests for nfl fantasy outcomes builder."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import patch

from scripts.build_nfl_fantasy_outcomes import (
    build_player_outcome_rows,
    build_source_metadata,
    career_year_for_season,
    compute_ppr,
    discover_stats_player_seasonal_assets,
    is_stale_source,
    latest_draft_year,
    latest_stats_season,
    resolve_stats_rows,
)


class PPRFormulaTests(unittest.TestCase):
    def test_ppr_formula_receiving_and_rushing(self) -> None:
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
        self.assertIn("source_mode=seasonal_source", rows[0]["source_notes"])

    def test_weekly_rows_are_aggregated_to_single_player_season(self) -> None:
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
                "week": "1",
                "game_id": "2022_01_ATL_NO",
                "receptions": "3",
                "receiving_yards": "40",
                "receiving_tds": "0",
                "rushing_yards": "0",
                "rushing_tds": "0",
            },
            {
                "gsis_id": "00-001",
                "player_name": "Test Receiver",
                "position": "WR",
                "season": "2022",
                "week": "2",
                "game_id": "2022_02_LAR_ATL",
                "receptions": "5",
                "receiving_yards": "80",
                "receiving_tds": "1",
                "rushing_yards": "10",
                "rushing_tds": "0",
            },
        ]

        rows = build_player_outcome_rows(stats_rows, draft_rows, source_notes="fixture")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["games"], 2)
        self.assertEqual(rows[0]["receptions"], 8.0)
        self.assertEqual(rows[0]["receiving_yards"], 120.0)
        self.assertEqual(rows[0]["receiving_tds"], 1.0)
        self.assertEqual(rows[0]["rushing_yards"], 10.0)
        self.assertEqual(rows[0]["ppr_points"], 27.0)
        self.assertEqual(rows[0]["ppr_per_game"], 13.5)
        self.assertIn("source_mode=weekly_aggregated", rows[0]["source_notes"])


class SourceFreshnessTests(unittest.TestCase):
    def test_latest_season_detectors(self) -> None:
        stats_rows = [{"season": "2023"}, {"season": "2025"}, {"season": "2024"}]
        draft_rows = [{"season": "2022"}, {"draft_year": "2024"}, {"season": "2023"}]
        self.assertEqual(latest_stats_season(stats_rows), 2025)
        self.assertEqual(latest_draft_year(draft_rows), 2024)

    def test_staleness_check(self) -> None:
        self.assertFalse(is_stale_source(2025, None))
        self.assertFalse(is_stale_source(2025, 2025))
        self.assertTrue(is_stale_source(2024, 2025))

    def test_source_metadata_marks_stale(self) -> None:
        metadata = build_source_metadata(
            stats_rows=[{"season": "2024"}],
            draft_rows=[{"season": "2023"}],
            source_mode="seasonal_source",
            expected_latest_season=2025,
            source_notes="fixture",
            stats_source="stats_player",
            stats_url="https://example.com/stats.csv.gz",
        )
        self.assertEqual(metadata["player_stats_row_count"], 1)
        self.assertEqual(metadata["draft_picks_row_count"], 1)
        self.assertEqual(metadata["latest_stats_season"], 2024)
        self.assertEqual(metadata["latest_draft_year"], 2023)
        self.assertEqual(metadata["source_mode"], "seasonal_source")
        self.assertEqual(metadata["stats_source"], "stats_player")
        self.assertTrue(metadata["is_stale_relative_to_expected"])


class StatsSourceSelectionTests(unittest.TestCase):
    def test_discovers_only_season_specific_regular_season_assets(self) -> None:
        assets = discover_stats_player_seasonal_assets(
            [
                "stats_player_week_2025.csv.gz",
                "stats_player_reg_2024.csv.gz",
                "stats_player_reg_2025.csv.gz",
                "stats_player_reg.csv.gz",
                "stats_player_post_2025.csv.gz",
            ]
        )
        self.assertEqual(assets, {2024: "stats_player_reg_2024.csv.gz", 2025: "stats_player_reg_2025.csv.gz"})

    def test_prefers_gzip_when_both_csv_and_csv_gz_exist(self) -> None:
        assets = discover_stats_player_seasonal_assets(
            ["stats_player_reg_2025.csv", "stats_player_reg_2025.csv.gz", "stats_player_reg_2024.csv"]
        )
        self.assertEqual(assets, {2024: "stats_player_reg_2024.csv", 2025: "stats_player_reg_2025.csv.gz"})

    def test_source_metadata_contains_multiseason_fields(self) -> None:
        metadata = build_source_metadata(
            stats_rows=[{"season": "2022"}, {"season": "2024"}],
            draft_rows=[{"season": "2023"}],
            source_mode="seasonal_source",
            expected_latest_season=2025,
            source_notes="fixture",
            stats_source="stats_player",
            stats_urls=["https://example.com/stats_player_reg_2022.csv.gz", "https://example.com/stats_player_reg_2024.csv.gz"],
            stats_seasons_loaded=[2022, 2024],
            missing_stats_seasons=[2023, 2025],
        )
        self.assertEqual(metadata["earliest_stats_season"], 2022)
        self.assertEqual(metadata["latest_stats_season"], 2024)
        self.assertEqual(metadata["stats_seasons_loaded"], [2022, 2024])
        self.assertEqual(metadata["missing_stats_seasons"], [2023, 2025])
        self.assertIn("stats_urls", metadata)

    def test_multiseason_rows_do_not_fallback_when_resolved_stats_url_none(self) -> None:
        args = Namespace(
            stats_source_url=None,
            stats_source="stats_player",
            stats_season_start=2022,
            stats_season_end=None,
            expected_latest_season=2025,
            refresh=False,
            stats_cache=None,
        )
        with (
            patch(
                "scripts.build_nfl_fantasy_outcomes.fetch_release_asset_names",
                return_value=[
                    "stats_player_reg_2022.csv.gz",
                    "stats_player_reg_2023.csv.gz",
                    "stats_player_reg_2024.csv.gz",
                    "stats_player_reg_2025.csv.gz",
                ],
            ),
            patch(
                "scripts.build_nfl_fantasy_outcomes.load_source_rows",
                side_effect=[
                    ([{"season": "2022"}], "cache"),
                    ([{"season": "2023"}], "cache"),
                    ([{"season": "2024"}], "cache"),
                    ([{"season": "2025"}], "cache"),
                ],
            ) as mock_load,
        ):
            (
                stats_rows,
                _stats_mode,
                resolved_stats_source,
                resolved_stats_url,
                resolved_stats_urls,
                stats_seasons_loaded,
                missing_stats_seasons,
                _seasonal_cache_paths,
                _stats_resolution_note,
            ) = resolve_stats_rows(args)

        self.assertEqual(resolved_stats_source, "stats_player")
        self.assertIsNone(resolved_stats_url)
        self.assertEqual(stats_seasons_loaded, [2022, 2023, 2024, 2025])
        self.assertEqual(missing_stats_seasons, [])
        self.assertEqual([row["season"] for row in stats_rows], ["2022", "2023", "2024", "2025"])
        self.assertEqual(len(resolved_stats_urls or []), 4)
        self.assertEqual(mock_load.call_count, 4)

    def test_multiseason_metadata_consistency_and_not_stale(self) -> None:
        stats_rows = [{"season": str(season)} for season in [2022, 2023, 2024, 2025]]
        metadata = build_source_metadata(
            stats_rows=stats_rows,
            draft_rows=[{"season": "2025"}],
            source_mode="seasonal_source",
            expected_latest_season=2025,
            source_notes="fixture",
            stats_source="stats_player",
            stats_urls=[
                "https://example.com/stats_player_reg_2022.csv.gz",
                "https://example.com/stats_player_reg_2023.csv.gz",
                "https://example.com/stats_player_reg_2024.csv.gz",
                "https://example.com/stats_player_reg_2025.csv.gz",
            ],
            stats_seasons_loaded=[2022, 2023, 2024, 2025],
            missing_stats_seasons=[],
        )
        self.assertEqual(metadata["stats_source"], "stats_player")
        self.assertEqual(metadata["earliest_stats_season"], 2022)
        self.assertEqual(metadata["latest_stats_season"], 2025)
        self.assertEqual(metadata["stats_seasons_loaded"], [2022, 2023, 2024, 2025])
        self.assertEqual(metadata["missing_stats_seasons"], [])
        self.assertFalse(metadata["is_stale_relative_to_expected"])


if __name__ == "__main__":
    unittest.main()
