import json
import tempfile
import unittest
from pathlib import Path

from scripts.enrich_post_draft_alpha_with_team_context import enrich_rows, load_team_context, write_outputs


class EnrichPostDraftAlphaWithTeamContextTests(unittest.TestCase):
    def setUp(self) -> None:
        postdraft_payload = json.loads(
            Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json").read_text(encoding="utf-8")
        )
        self.rows = postdraft_payload["rows"]
        self.teamstate_payload = {
            "teams": {
                "SF": {
                    "team_context_tags": [
                        "shanahan_efficiency_environment",
                        "yac_creation_scheme",
                        "low_pass_volume_risk",
                        "role_specific_usage_dependency",
                        "day2_49ers_skill_pick_hit_rate_caution",
                    ],
                    "source_status": "operator_seeded",
                },
                "CLE": {
                    "team_context_tags": [
                        "concentrated_wr_investment",
                        "rookie_wr_priority_signal",
                        "browns_offensive_volatility",
                        "target_competition_between_rookies",
                        "qb_environment_uncertainty",
                    ],
                    "source_status": "operator_seeded",
                },
                "TEN": {
                    "team_context_tags": [
                        "wr1_depth_chart_path",
                        "top5_wr_opportunity_insulation",
                        "young_qb_development_dependency",
                        "offensive_environment_uncertainty",
                    ],
                    "source_status": "operator_seeded",
                },
            }
        }

    def _build_context(self) -> dict[str, dict[str, object]]:
        with tempfile.TemporaryDirectory() as temp_dir:
            teamstate_path = Path(temp_dir) / "teamstate.json"
            teamstate_path.write_text(json.dumps(self.teamstate_payload), encoding="utf-8")
            return load_team_context(teamstate_path)

    def test_stribling_joins_to_sf_and_expected_tags(self) -> None:
        context = self._build_context()
        enriched = enrich_rows(self.rows, context)
        stribling = next(row for row in enriched if row["player_name"] == "De'Zhaun Stribling")

        self.assertTrue(stribling["team_context_found"])
        self.assertEqual(stribling["team_context_notes"], "team_context_joined:SF")
        self.assertIn("shanahan_efficiency_environment", stribling["team_context_tags"])
        self.assertIn("low_pass_volume_risk", stribling["team_context_tags"])
        self.assertIn("role_specific_usage_dependency", stribling["team_context_tags"])
        self.assertIn("day2_49ers_skill_pick_hit_rate_caution", stribling["team_context_tags"])

    def test_kcc_joins_to_cle_and_includes_expected_tags(self) -> None:
        context = self._build_context()
        enriched = enrich_rows(self.rows, context)
        kc = next(row for row in enriched if row["player_name"] == "KC Concepcion")

        self.assertTrue(kc["team_context_found"])
        self.assertIn("concentrated_wr_investment", kc["team_context_tags"])
        self.assertIn("browns_offensive_volatility", kc["team_context_tags"])
        self.assertIn("target_competition_between_rookies", kc["team_context_tags"])

    def test_team_tbd_row_has_no_team_context(self) -> None:
        context = self._build_context()
        enriched = enrich_rows(self.rows, context)
        tbd_row = next(row for row in enriched if row["team"] == "TBD")

        self.assertFalse(tbd_row["team_context_found"])
        self.assertEqual(tbd_row["team_context_tags"], [])
        self.assertEqual(tbd_row["team_context_notes"], "team_context_not_found_or_team_tbd")

    def test_scores_unchanged_after_enrichment(self) -> None:
        context = self._build_context()
        enriched = enrich_rows(self.rows, context)
        by_id = {row["player_id"]: row for row in self.rows}

        for row in enriched:
            original = by_id[row["player_id"]]
            self.assertEqual(row["pre_draft_alpha"], original["pre_draft_alpha"])
            self.assertEqual(row["post_draft_alpha"], original["post_draft_alpha"])
            self.assertEqual(row["post_draft_delta"], original["post_draft_delta"])

    def test_combined_context_tags_deduplicates(self) -> None:
        rows = [
            {
                "player_id": "x",
                "player_name": "Example",
                "position": "WR",
                "pre_draft_alpha": 50.0,
                "post_draft_alpha": 51.0,
                "post_draft_delta": 1.0,
                "draft_round": 2,
                "draft_pick": 40,
                "team": "SF",
                "source_profile": "day2",
                "source_status": "operator_seeded",
                "delta_reason_codes": [],
                "translator_tags": ["shared_tag", "translator_only"],
                "remaining_risks": ["Sentence risk"],
            }
        ]
        context = {
            "SF": {
                "team_context_tags": ["shared_tag", "team_only"],
                "positive_team_context_tags": ["shared_tag", "team_only"],
                "risk_team_context_tags": [],
                "team_context_source_status": "operator_seeded",
            }
        }

        enriched = enrich_rows(rows, context)
        self.assertEqual(enriched[0]["combined_context_tags"], ["shared_tag", "translator_only", "team_only"])

    def test_already_normalized_team_codes_join(self) -> None:
        rows = [
            {
                "player_id": "x",
                "player_name": "Code Team",
                "position": "WR",
                "pre_draft_alpha": 60.0,
                "post_draft_alpha": 60.0,
                "post_draft_delta": 0.0,
                "draft_round": 1,
                "draft_pick": 20,
                "team": "CLE",
                "source_profile": "round1",
                "source_status": "operator_seeded",
                "delta_reason_codes": [],
                "translator_tags": [],
                "remaining_risks": [],
            }
        ]
        context = {
            "CLE": {
                "team_context_tags": ["concentrated_wr_investment"],
                "positive_team_context_tags": ["concentrated_wr_investment"],
                "risk_team_context_tags": [],
                "team_context_source_status": "operator_seeded",
            }
        }

        enriched = enrich_rows(rows, context)
        self.assertTrue(enriched[0]["team_context_found"])
        self.assertIn("concentrated_wr_investment", enriched[0]["team_context_tags"])

    def test_write_outputs_contract(self) -> None:
        context = self._build_context()
        enriched = enrich_rows(self.rows, context)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_json = Path(temp_dir) / "enriched.json"
            output_csv = Path(temp_dir) / "enriched.csv"
            write_outputs(enriched, output_json, output_csv)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["model"], "rookie-alpha-postdraft-team-context-v0")
            self.assertEqual(len(payload["rows"]), len(self.rows))
            self.assertTrue(output_csv.exists())


if __name__ == "__main__":
    unittest.main()
