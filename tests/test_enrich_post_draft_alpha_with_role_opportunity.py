import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.enrich_post_draft_alpha_with_role_opportunity import enrich_rows, load_role_baselines, load_team_role_profiles, write_outputs


class EnrichPostDraftAlphaWithRoleOpportunityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {
                "player_id": "qb-ty-simpson",
                "player_name": "Ty Simpson",
                "position": "QB",
                "team": "Rams",
                "pre_draft_alpha": 70.0,
                "post_draft_alpha": 74.0,
                "post_draft_delta": 4.0,
                "translator_tags": ["round1_qb_capital", "delayed_start_insulation"],
                "remaining_risks": ["Delayed initial runway risk"],
                "combined_context_tags": ["round1_qb_capital", "delayed_start_insulation"],
                "combined_risk_tags": ["Delayed initial runway risk"],
            },
            {
                "player_id": "te-tanner-koziol",
                "player_name": "Tanner Koziol",
                "position": "TE",
                "team": "Jaguars",
                "pre_draft_alpha": 57.0,
                "post_draft_alpha": 58.0,
                "post_draft_delta": 1.0,
                "translator_tags": ["late_round_te_watch", "move_te", "low_capital"],
                "remaining_risks": ["usage volatility"],
            },
            {
                "player_id": "wr-dezhaun-stribling",
                "player_name": "De'Zhaun Stribling",
                "position": "WR",
                "team": "49ers",
                "pre_draft_alpha": 63.0,
                "post_draft_alpha": 66.0,
                "post_draft_delta": 3.0,
                "translator_tags": ["round2_wr_capital", "target_room_competition_watch", "shanahan_role_translation_watch"],
                "remaining_risks": ["role volatility"],
            },
            {
                "player_id": "wr-missing-team",
                "player_name": "No Team Role",
                "position": "WR",
                "team": "ATL",
                "pre_draft_alpha": 40.0,
                "post_draft_alpha": 40.0,
                "post_draft_delta": 0.0,
                "translator_tags": ["wr2_wr3_path"],
                "remaining_risks": [],
            },
        ]

        self.team_profiles_payload = {
            "teams": {
                "LAR": {
                    "roles": [
                        {
                            "role": "QB_developmental",
                            "context_tags": ["scheme_stability"],
                            "risk_tags": ["bench_timeline_risk"],
                        }
                    ]
                },
                "JAX": {
                    "roles": [
                        {"role": "TE2", "context_tags": ["secondary_te_path"]},
                        {"role": "move_te", "context_tags": ["matchup_alignment"]},
                        {"role": "blocking_rotational_te", "context_tags": ["inline_snap_path"]},
                    ]
                },
                "SF": {
                    "roles": [
                        {"role": "WR2", "context_tags": ["secondary_wr_path"]},
                        {"role": "rotational_wr", "context_tags": ["rotation_wr_path"]},
                    ]
                },
            }
        }

        self.role_baselines_payload = {
            "roles": [
                {"role": "QB_developmental", "context_tags": ["qb_dev_baseline"]},
                {"role": "TE2", "context_tags": ["te2_baseline"]},
                {"role": "move_te", "context_tags": ["move_te_baseline"]},
                {"role": "blocking_rotational_te", "context_tags": ["blocking_te_baseline"]},
                {"role": "WR2", "context_tags": ["wr2_baseline"]},
                {"role": "rotational_wr", "context_tags": ["rotational_wr_baseline"]},
            ]
        }

    def _load_profiles(self) -> tuple[dict[str, list[dict[str, object]]], dict[str, dict[str, object]]]:
        with tempfile.TemporaryDirectory() as temp_dir:
            team_profiles_path = Path(temp_dir) / "team_profiles.json"
            role_baselines_path = Path(temp_dir) / "role_baselines.json"
            team_profiles_path.write_text(json.dumps(self.team_profiles_payload), encoding="utf-8")
            role_baselines_path.write_text(json.dumps(self.role_baselines_payload), encoding="utf-8")
            return load_team_role_profiles(team_profiles_path), load_role_baselines(role_baselines_path)

    def test_load_team_role_profiles_supports_pr11_team_profiles_shape(self) -> None:
        pr11_shape_payload = {
            "model": "team-role-opportunity-profiles-v0",
            "season": 2026,
            "source_status": "operator_seeded",
            "team_profiles": [
                {"team": "HOU", "roles": [{"role": "WR2"}]},
                {"team": "CLE", "roles": [{"role": "WR1"}]},
                {"team": "TEN", "roles": [{"role": "WR1"}]},
                {"team": "PHI", "roles": [{"role": "TE2"}]},
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pr11_team_profiles.json"
            path.write_text(json.dumps(pr11_shape_payload), encoding="utf-8")
            profiles_by_team = load_team_role_profiles(path)

        self.assertIn("HOU", profiles_by_team)
        self.assertIn("CLE", profiles_by_team)
        self.assertIn("TEN", profiles_by_team)
        self.assertIn("PHI", profiles_by_team)
        self.assertEqual(profiles_by_team["HOU"][0]["role"], "WR2")

    def test_ty_simpson_maps_to_lar_qb_developmental(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)
        ty = next(row for row in enriched if row["player_name"] == "Ty Simpson")

        self.assertTrue(ty["role_opportunity_found"])
        self.assertTrue(ty["role_team_profile_found"])
        self.assertTrue(ty["role_baseline_found"])
        self.assertIn("QB_developmental", ty["candidate_roles"])
        self.assertEqual([profile["role"] for profile in ty["matched_role_profiles"]], ["QB_developmental"])

    def test_tanner_koziol_maps_to_jax_te2_move_te_and_blocking_roles(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)
        tanner = next(row for row in enriched if row["player_name"] == "Tanner Koziol")

        matched_roles = {profile["role"] for profile in tanner["matched_role_profiles"]}
        self.assertTrue({"TE2", "move_te", "blocking_rotational_te"}.issubset(matched_roles))

    def test_stribling_maps_to_sf_wr2_or_rotational_wr(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)
        stribling = next(row for row in enriched if row["player_name"] == "De'Zhaun Stribling")

        matched_roles = {profile["role"] for profile in stribling["matched_role_profiles"]}
        self.assertTrue("WR2" in matched_roles or "rotational_wr" in matched_roles)

    def test_output_preserves_original_alpha_fields(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)
        original_by_id = {row["player_id"]: row for row in self.rows}

        for row in enriched:
            original = original_by_id[row["player_id"]]
            self.assertEqual(row["pre_draft_alpha"], original["pre_draft_alpha"])
            self.assertEqual(row["post_draft_alpha"], original["post_draft_alpha"])
            self.assertEqual(row["post_draft_delta"], original["post_draft_delta"])

    def test_missing_role_profile_does_not_crash(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)
        missing = next(row for row in enriched if row["player_name"] == "No Team Role")

        self.assertFalse(missing["role_opportunity_found"])
        self.assertFalse(missing["role_team_profile_found"])
        self.assertTrue(missing["role_baseline_found"])
        self.assertEqual(missing["candidate_roles"], ["WR2", "WR3"])
        self.assertEqual(missing["matched_role_profiles"], [])
        self.assertEqual(missing["role_context_notes"], "team_role_profile_not_found:ATL")

    def test_csv_output_preserves_original_plus_role_fields(self) -> None:
        team_profiles, baselines = self._load_profiles()
        enriched = enrich_rows(self.rows, team_profiles, baselines)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_json = Path(temp_dir) / "joined.json"
            output_csv = Path(temp_dir) / "joined.csv"
            write_outputs(enriched, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                header = reader.fieldnames or []

        self.assertIn("player_name", header)
        self.assertIn("post_draft_alpha", header)
        self.assertIn("role_opportunity_found", header)
        self.assertIn("role_team_profile_found", header)
        self.assertIn("role_baseline_found", header)
        self.assertIn("candidate_roles", header)
        self.assertIn("combined_context_tags_with_role", header)


if __name__ == "__main__":
    unittest.main()
