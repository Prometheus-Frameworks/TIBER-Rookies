"""Target-evidence qualification tests for WR/TE route profiles (#303)."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts import compute_yoy_trends
from scripts.compute_age_adjusted_production import season_volume
from scripts.compute_yoy_trends import compute_wr_te_trend, validate_wr_te_rows
from scripts.fetch_wr_route_profiles import build_profile
from scripts.target_evidence import qualify_profile, target_status, validate_target_evidence

PROFILE_DIR = Path("data/processed/wr_route_profiles")
PLAYER = {"player_id": "wr-test-player", "player_name": "Test Player", "school": "Test State"}
STORED_STATUS_FIELDS = ("qualification_origin", "targets.status", "receptions.status", "scheme_fields.status")


def load(name: str) -> dict:
    return json.loads((PROFILE_DIR / name).read_text(encoding="utf-8"))


def legacy_estimated(targets: int, receptions: int, ypt: float) -> dict:
    return {
        "targets": targets,
        "receptions": receptions,
        "yards_per_target": ypt,
        "screen_targets": 0,
        "screen_target_rate": None,
        "source_name": "Grok/Sports-Reference (season=2024, team=X); targets estimated (REC / 0.70)",
        "source_url": None,
        "methodology_notes": "Targets estimated as receptions / 0.70.",
    }


class LegacyQualificationTests(unittest.TestCase):
    def test_hurst_targets_are_estimated_not_measured(self) -> None:
        profile = load("wr-ted-hurst_2025.json")
        q = qualify_profile(profile)
        self.assertEqual(q["qualification_origin"], "legacy_inferred")
        self.assertEqual(q["targets"]["status"], "estimated")
        self.assertEqual(q["targets"]["method"], "receptions_div_assumed_catch_rate")
        self.assertEqual(q["targets"]["assumed_catch_rate"], 0.70)
        self.assertEqual(q["yards_per_target"]["denominator_status"], "estimated")
        self.assertFalse(q["yards_per_target"]["observed_denominator"])
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")
        self.assertIn("screen_targets", q["scheme_fields"]["fields"])
        self.assertIn("REC / 0.70", q["lineage"]["source_name"])
        # Raw legacy values are retained untouched.
        self.assertEqual((profile["targets"], profile["yards_per_target"], profile["screen_targets"]), (101, 9.9, 0))

    def test_play_by_play_row_is_parsed_partial_with_unsupported_scheme(self) -> None:
        q = qualify_profile(load("wr-carnell-tate_2024.json"))
        self.assertEqual(q["targets"]["status"], "parsed_partial")
        self.assertTrue(q["yards_per_target"]["observed_denominator"])
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")

    def test_synthetic_row_is_estimated_including_receptions(self) -> None:
        q = qualify_profile(load("wr-antonio-williams_2024.json"))
        self.assertEqual(q["targets"]["status"], "estimated")
        self.assertEqual(q["receptions"]["status"], "estimated")
        self.assertEqual(q["targets"]["assumed_catch_rate"], 0.70)
        # Stored screen_target_rate 0.0 is not an observation.
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")

    def test_invalidated_null_row_is_unavailable(self) -> None:
        self.assertEqual(target_status(load("te-kenyon-sadiq_2025.json")), "unavailable")

    def test_ambiguous_legacy_row_stays_unknown(self) -> None:
        profile = {"targets": 40, "receptions": 30, "source_name": "Some notes", "methodology_notes": ""}
        self.assertEqual(target_status(profile), "unknown")

    def test_parsed_scheme_observation_not_marked_unsupported(self) -> None:
        profile = {
            "targets": 50,
            "receptions": 35,
            "screen_targets": 4,
            "screen_target_rate": 0.08,
            "source_name": "CFBD play-by-play (year=2023, team=X)",
            "methodology_notes": "",
        }
        q = qualify_profile(profile)
        self.assertEqual(q["targets"]["status"], "parsed_partial")
        self.assertNotEqual(q["scheme_fields"]["status"], "unsupported")

    def test_prior_producer_reported_tgt_row_is_not_estimated(self) -> None:
        # Pre-#303 producer shape: no block, standard conditional fallback note.
        reported = build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})
        estimated = build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})
        for profile in (reported, estimated):
            del profile["target_evidence"]
            self.assertIn("If CFBD does not supply a TGT stat type", profile["methodology_notes"])
        self.assertEqual(target_status(reported), "source_reported")
        self.assertTrue(qualify_profile(reported)["yards_per_target"]["observed_denominator"])
        q = qualify_profile(estimated)
        self.assertEqual(q["targets"]["status"], "estimated")
        self.assertEqual(q["targets"]["assumed_catch_rate"], 0.70)

    def test_every_committed_profile_gets_a_status(self) -> None:
        for path in sorted(PROFILE_DIR.glob("*.json")):
            with self.subTest(path=path.name):
                self.assertNotEqual(target_status(json.loads(path.read_text())), "unknown")


class ProducerEvidenceTests(unittest.TestCase):
    def test_reported_tgt(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})
        self.assertEqual(profile["targets"], 90)
        self.assertEqual(profile["yards_per_target"], 10.0)
        ev = profile["target_evidence"]
        self.assertEqual(ev["qualification_origin"], "producer")
        self.assertEqual(ev["targets"]["status"], "source_reported")
        self.assertTrue(ev["yards_per_target"]["observed_denominator"])
        self.assertEqual(ev["scheme_fields"]["status"], "unsupported")

    def test_reported_zero_is_observed_zero(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 0.0, "YDS": 0.0, "TGT": 0.0})
        self.assertEqual(profile["targets"], 0)
        self.assertEqual(profile["target_evidence"]["targets"]["status"], "source_reported")

    def test_estimated_fallback_keeps_numbers(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})
        self.assertEqual(profile["targets"], 101)  # round(71 / 0.70), unchanged policy
        self.assertEqual(profile["yards_per_target"], round(1000.0 / 101, 1))
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "estimated")
        self.assertEqual(ev["targets"]["assumed_catch_rate"], 0.70)
        self.assertEqual(ev["receptions"]["status"], "source_reported")
        self.assertFalse(ev["yards_per_target"]["observed_denominator"])

    def test_player_not_found_is_unavailable_not_zero(self) -> None:
        profile = build_profile(PLAYER, 2025, None)
        self.assertEqual(profile["targets"], 0)  # legacy placeholder retained
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "unavailable")
        self.assertEqual(ev["receptions"]["status"], "unavailable")

    def test_missing_rec_with_tgt_does_not_invent_reported_receptions(self) -> None:
        profile = build_profile(PLAYER, 2025, {"TGT": 90.0, "YDS": 900.0})
        self.assertEqual((profile["targets"], profile["receptions"]), (90, 0))  # placeholders unchanged
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "source_reported")
        self.assertEqual(ev["receptions"]["status"], "unavailable")

    def test_missing_rec_and_tgt_is_not_an_estimate(self) -> None:
        profile = build_profile(PLAYER, 2025, {"YDS": 1000.0})
        self.assertEqual((profile["targets"], profile["receptions"]), (0, 0))  # placeholders unchanged
        self.assertIsNone(profile["yards_per_target"])
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "unavailable")
        self.assertNotIn("assumed_catch_rate", ev["targets"])
        self.assertEqual(ev["receptions"]["status"], "unavailable")
        self.assertEqual(validate_target_evidence(ev, profile), [])

    def test_producer_blocks_pass_validation(self) -> None:
        for stats in ({"REC": 60.0, "YDS": 900.0, "TGT": 90.0}, {"REC": 71.0, "YDS": 1000.0}, None):
            profile = build_profile(PLAYER, 2025, stats)
            self.assertEqual(validate_target_evidence(profile["target_evidence"], profile), [])

    def test_qualification_survives_serialization(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 50.0, "YDS": 600.0})
        reloaded = json.loads(json.dumps(profile))
        self.assertEqual(qualify_profile(reloaded), profile["target_evidence"])


class StoredBlockValidationTests(unittest.TestCase):
    def valid_reported(self) -> dict:
        return build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})

    def malformed_profile(self, field: str, value: object) -> dict:
        profile = self.valid_reported()
        block = profile["target_evidence"]
        keys = field.split(".")
        for key in keys[:-1]:
            block = block[key]
        block[keys[-1]] = deepcopy(value)
        return profile

    def test_array_and_object_statuses_return_errors_and_degrade(self) -> None:
        for field in STORED_STATUS_FIELDS:
            for value in ([], {}):
                for targets, expected in ((90, "unknown"), (None, "unavailable")):
                    with self.subTest(field=field, value=value, targets=targets):
                        profile = self.malformed_profile(field, value)
                        profile["targets"] = targets
                        original = deepcopy(profile)
                        errors = validate_target_evidence(profile["target_evidence"], profile)
                        self.assertTrue(any(field in error for error in errors))
                        q = qualify_profile(profile)
                        self.assertEqual(q["targets"]["status"], expected)
                        self.assertEqual(q["yards_per_target"]["denominator_status"], expected)
                        self.assertIs(q["yards_per_target"]["observed_denominator"], False)
                        self.assertEqual(q["receptions"]["status"], "unknown")
                        self.assertEqual(q["scheme_fields"]["status"], "unknown")
                        self.assertEqual(q["invalid_stored_block"], errors)
                        self.assertEqual(validate_target_evidence(q, profile), [])
                        self.assertEqual(profile, original)

    def test_yoy_generation_degrades_array_and_object_statuses(self) -> None:
        for field in STORED_STATUS_FIELDS:
            for value in ([], {}):
                for season in (2024, 2025):
                    for targets, expected in ((90, "unknown"), (None, "unavailable")):
                        with self.subTest(field=field, value=value, season=season, targets=targets):
                            profiles = {year: self.valid_reported() for year in (2024, 2025)}
                            profiles[season] = self.malformed_profile(field, value)
                            profiles[season]["targets"] = targets
                            with tempfile.TemporaryDirectory() as tmp:
                                root = Path(tmp)
                                profile_dir = root / "profiles"
                                profile_dir.mkdir()
                                for year, profile in profiles.items():
                                    (profile_dir / f"wr-test-player_{year}.json").write_text(json.dumps(profile))
                                output = root / "yoy.json"
                                with patch.multiple(compute_yoy_trends, WR_TE_PROFILE_DIR=profile_dir,
                                                    RB_PROFILE_DIR=root / "no-rb-profiles", OUTPUT_PATH=output):
                                    compute_yoy_trends.main()
                                rows = json.loads(output.read_text())
                            self.assertEqual(len(rows), 1)
                            row = rows[0]
                            self.assertEqual(row[f"target_status_{season}"], expected)
                            self.assertEqual(row[f"target_status_{2025 if season == 2024 else 2024}"],
                                             "source_reported")
                            self.assertEqual(row["target_basis"], "mixed")
                            self.assertIs(row["efficiency_observed_denominators"], False)
                            self.assertEqual(row[f"volume_{season}"], targets)
                            self.assertEqual((row["efficiency_2024"], row["efficiency_2025"]), (10.0, 10.0))
                            validate_wr_te_rows(rows)

    def test_partial_block_is_degraded_not_trusted(self) -> None:
        profile = {"targets": None, "receptions": None, "yards_per_target": None,
                   "target_evidence": {"targets": {"status": "source_reported"}}}
        q = qualify_profile(profile)
        self.assertEqual(q["targets"]["status"], "unavailable")
        self.assertFalse(q["yards_per_target"]["observed_denominator"])
        self.assertTrue(q["invalid_stored_block"])

    def test_unknown_contract_version_is_degraded(self) -> None:
        profile = self.valid_reported()
        profile["target_evidence"]["contract_version"] = "wr_te_target_evidence_v9"
        q = qualify_profile(profile)
        self.assertEqual(q["targets"]["status"], "unknown")
        self.assertFalse(q["yards_per_target"]["observed_denominator"])

    def test_mismatched_denominator_is_degraded(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})
        profile["target_evidence"]["yards_per_target"]["observed_denominator"] = True
        self.assertEqual(target_status(profile), "unknown")
        profile = self.valid_reported()
        profile["target_evidence"]["yards_per_target"]["denominator_status"] = "estimated"
        self.assertEqual(target_status(profile), "unknown")

    def test_estimate_without_assumption_is_degraded(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})
        del profile["target_evidence"]["targets"]["assumed_catch_rate"]
        self.assertEqual(target_status(profile), "unknown")

    def test_non_object_block_is_degraded(self) -> None:
        profile = self.valid_reported()
        profile["target_evidence"] = "source_reported"
        self.assertEqual(target_status(profile), "unknown")

    def test_invalid_blocks_cannot_become_observed_yoy_evidence(self) -> None:
        bad = {"targets": None, "receptions": None, "yards_per_target": None,
               "target_evidence": {"targets": {"status": "source_reported"}}}
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "wr-x_2024.json").write_text(json.dumps(bad))
            (d / "wr-x_2025.json").write_text(json.dumps(bad))
            row = compute_wr_te_trend("wr-x", d)
        self.assertFalse(row["efficiency_observed_denominators"])
        validate_wr_te_rows([row])


class DownstreamCompatibilityTests(unittest.TestCase):
    def test_yoy_mixed_source_comparison_is_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            p24 = legacy_estimated(70, 49, 9.1)
            p25 = build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})
            (d / "wr-test-player_2024.json").write_text(json.dumps(p24))
            (d / "wr-test-player_2025.json").write_text(json.dumps(p25))
            row = compute_wr_te_trend("wr-test-player", d)
        self.assertEqual(row["target_status_2024"], "estimated")
        self.assertEqual(row["target_status_2025"], "source_reported")
        self.assertEqual(row["target_basis"], "mixed")
        self.assertFalse(row["efficiency_observed_denominators"])
        # Numeric calculation unchanged.
        self.assertEqual((row["volume_2024"], row["volume_2025"]), (70, 90))
        self.assertEqual(row["volume_change_pct"], round((90 - 70) / 70, 4))
        self.assertEqual(row["efficiency_change_pct"], round((10.0 - 9.1) / 9.1, 4))
        validate_wr_te_rows([row])

    def test_yoy_validation_rejects_lost_status(self) -> None:
        row = {"player_id": "x", "position_group": "WR_TE", "target_status_2024": "estimated"}
        with self.assertRaises(ValueError):
            validate_wr_te_rows([row])
        validate_wr_te_rows([{"player_id": "rb", "position_group": "RB"}])

    def test_yoy_validation_rejects_inconsistent_couplings(self) -> None:
        base = {"player_id": "x", "position_group": "WR_TE",
                "target_status_2024": "estimated", "target_status_2025": "estimated",
                "target_basis": "estimated", "efficiency_observed_denominators": False}
        validate_wr_te_rows([base])
        for override in ({"target_basis": None}, {"target_basis": "mixed"},
                         {"efficiency_observed_denominators": True},
                         {"efficiency_observed_denominators": 0}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                validate_wr_te_rows([{**base, **override}])
        mixed = {**base, "target_status_2025": "parsed_partial", "target_basis": "mixed"}
        validate_wr_te_rows([mixed])
        with self.assertRaises(ValueError):
            validate_wr_te_rows([{**mixed, "target_basis": "estimated"}])

    def test_age_adjusted_volume_reads_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "wr-a_2025.json").write_text(json.dumps(build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})))
            (d / "wr-b_2025.json").write_text(json.dumps(build_profile(PLAYER, 2025, None)))
            self.assertEqual(season_volume("wr-a", 2025, "targets", d), 101.0)
            # Retained legacy behavior (deferred to migration): unavailable reads as 0.
            self.assertEqual(season_volume("wr-b", 2025, "targets", d), 0.0)
            self.assertEqual(season_volume("wr-missing", 2025, "targets", d), 0.0)


if __name__ == "__main__":
    unittest.main()
