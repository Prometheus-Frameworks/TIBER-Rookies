import unittest
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from scripts.compute_rookie_ml_lane import (
    BASELINE_MODEL_FEATURES,
    DEFAULT_OUTPUT_DIR,
    SplitBundle,
    _extract_hit_label,
    build_canonical_historical_outcomes,
    build_data_warnings,
    build_dataset_diagnostics,
    build_feature_coverage_report,
    build_feature_importance_report,
    build_historical_class_coverage_report,
    build_historical_feature_consistency_report,
    build_historical_label_provenance_report,
    build_historical_position_slices_report,
    build_missingness_summary,
    build_labeled_rows,
    pr_auc,
    reject_protected_output_dir,
    roc_auc,
    time_split,
)


class RookieMlLaneTests(unittest.TestCase):
    def test_extract_hit_label_by_position_thresholds(self) -> None:
        self.assertEqual(_extract_hit_label({"position": "WR", "top_finish_band": "TOP-24"}), 1)
        self.assertEqual(_extract_hit_label({"position": "RB", "top_finish_band": "RB25"}), 0)
        self.assertEqual(_extract_hit_label({"position": "TE", "top_finish_band": "TE12"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB15"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB16"}), 0)


    def test_tier_labels_do_not_parse_as_literal_ranks(self) -> None:
        self.assertEqual(_extract_hit_label({"position": "WR", "top_finish_band": "WR3"}), 0)
        self.assertEqual(_extract_hit_label({"position": "RB", "top_finish_band": "RB2"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB15"}), 1)

    def test_build_labeled_rows_filters_unlabeled(self) -> None:
        features = [
            {
                "player_id": "a",
                "player_name": "A",
                "position": "WR",
                "draft_year": 2020,
                "draft_capital_proxy_0_100": 80,
                "production_0_100": 70,
                "ras_0_100": 60,
            },
            {
                "player_id": "b",
                "player_name": "B",
                "position": "WR",
                "draft_year": 2021,
                "draft_capital_proxy_0_100": 70,
                "production_0_100": 50,
                "ras_0_100": 40,
            },
        ]
        outcomes = build_canonical_historical_outcomes([
            {"player_id": "a", "position": "WR", "top_finish_band": "TOP-24"},
            {"player_id": "b", "position": "WR", "top_finish_band": None},
        ])
        rows = build_labeled_rows(features, outcomes, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_id"], "a")
        self.assertEqual(rows[0]["hit_label"], 1)

    def test_canonical_historical_outcomes_builds_provenance(self) -> None:
        outcomes = [
            {"player_id": "a", "position": "WR", "draft_year": 2020, "top_finish_band": "TOP-24"},
            {"player_id": "b", "position": "RB", "draft_year": 2020, "years_1_to_3_summary": "RB40"},
            {"player_id": "c", "position": "TE", "draft_year": 2020, "career_outcome_label": "miss"},
        ]
        canonical = build_canonical_historical_outcomes(outcomes)
        self.assertEqual(canonical[0]["label_source_primary"], "top_finish_band")
        self.assertFalse(canonical[0]["label_is_weak_fallback"])
        self.assertTrue(canonical[1]["label_is_weak_fallback"])
        self.assertEqual(canonical[2]["fantasy_relevant_hit_by_rule"], 0)

    def test_label_provenance_reporting_structure(self) -> None:
        canonical = build_canonical_historical_outcomes(
            [
                {"player_id": "a", "position": "WR", "draft_year": 2020, "top_finish_band": "TOP-24"},
                {"player_id": "b", "position": "WR", "draft_year": 2021, "career_outcome_label": "hit"},
                {"player_id": "c", "position": "RB", "draft_year": 2022},
            ]
        )
        report = build_historical_label_provenance_report(canonical)
        self.assertIn("row_count_by_source_field", report)
        self.assertGreaterEqual(report["weak_fallback_label_rows"], 1)
        self.assertGreaterEqual(report["rows_without_canonical_label"], 1)

    def test_time_split_uses_class_years(self) -> None:
        rows = [
            {"player_id": "a", "draft_year": 2019, "hit_label": 1},
            {"player_id": "b", "draft_year": 2020, "hit_label": 0},
            {"player_id": "c", "draft_year": 2021, "hit_label": 1},
            {"player_id": "d", "draft_year": 2022, "hit_label": 1},
        ]
        split = time_split(rows, holdout_year=2022)
        self.assertEqual(split.years["test"], [2022])
        self.assertEqual(split.years["validation"], [2021])
        self.assertEqual(split.years["train"], [2019, 2020])

    def test_time_split_does_not_reuse_validation_as_training(self) -> None:
        rows = [
            {"player_id": "a", "draft_year": 2021, "hit_label": 1},
            {"player_id": "b", "draft_year": 2022, "hit_label": 0},
        ]
        with self.assertRaises(SystemExit):
            time_split(rows, holdout_year=2022)

    def test_auc_helpers(self) -> None:
        y = [0, 0, 1, 1]
        p = [0.1, 0.4, 0.6, 0.9]
        self.assertGreater(roc_auc(y, p), 0.9)
        self.assertGreater(pr_auc(y, p), 0.8)

    def test_logistic_full_excludes_deterministic_grade_feature(self) -> None:
        self.assertNotIn("deterministic_grade_0_100", BASELINE_MODEL_FEATURES["logistic_full"])

    def test_dataset_diagnostics_structure(self) -> None:
        rows = [
            {"player_id": "a", "position": "WR", "draft_year": 2020, "hit_label": 1},
            {"player_id": "b", "position": "RB", "draft_year": 2020, "hit_label": 0},
            {"player_id": "c", "position": "WR", "draft_year": 2021, "hit_label": 1},
            {"player_id": "d", "position": "RB", "draft_year": 2022, "hit_label": 0},
        ]
        split = time_split(rows, holdout_year=2022)
        diagnostics = build_dataset_diagnostics(rows, split)
        self.assertEqual(diagnostics["total_labeled_rows"], 4)
        self.assertIn("WR", diagnostics["labeled_row_count_by_position"])
        self.assertIn("2020", diagnostics["target_hit_rate_by_draft_year"])
        self.assertIn("train", diagnostics["split_row_counts_by_position"])

    def test_feature_coverage_report_structure(self) -> None:
        rows = [
            {"position": "WR", "draft_year": 2020, "draft_capital_proxy_0_100": 70, "age_at_draft": 21},
            {"position": "RB", "draft_year": 2021, "draft_capital_proxy_0_100": None, "age_at_draft": 22},
        ]
        coverage = build_feature_coverage_report(rows, ["draft_capital_proxy_0_100", "age_at_draft"])
        detail = coverage["features"]["draft_capital_proxy_0_100"]
        self.assertEqual(detail["non_null_count"], 1)
        self.assertEqual(detail["null_count"], 1)
        self.assertIn("WR", detail["coverage_pct_by_position"])
        self.assertIn("2020", detail["coverage_pct_by_draft_year"])

    def test_missingness_summary_and_warnings_for_weak_coverage(self) -> None:
        rows = [
            {"position": "WR", "draft_year": 2020, "deterministic_grade_0_100": None},
            {"position": "WR", "draft_year": 2021, "deterministic_grade_0_100": None},
            {"position": "RB", "draft_year": 2022, "deterministic_grade_0_100": 80},
        ]
        coverage = build_feature_coverage_report(rows, ["deterministic_grade_0_100"])
        summary = build_missingness_summary(coverage)
        self.assertTrue(summary["warnings"])

        split = SplitBundle(
            train=[{"position": "WR", "draft_year": 2020, "hit_label": 1}],
            validation=[{"position": "WR", "draft_year": 2021, "hit_label": 0}],
            test=[{"position": "WR", "draft_year": 2022, "hit_label": 1}],
            years={"train": [2020], "validation": [2021], "test": [2022]},
        )
        diagnostics = build_dataset_diagnostics(split.train + split.validation + split.test, split)
        warnings = build_data_warnings(split, coverage, diagnostics)
        self.assertTrue(any("Deterministic grade" in w for w in warnings))

    def test_feature_consistency_and_class_coverage_reports(self) -> None:
        features = [
            {"player_id": "a", "position": "WR", "draft_year": 2020, "draft_capital_proxy_0_100": 70, "ras_0_100": 80},
            {"player_id": "b", "position": "RB", "draft_year": 2021, "draft_capital_proxy_0_100": 65, "athleticism_0_100": 75, "speed_proxy_0_100": 74},
            {"player_id": "c", "position": "TE", "draft_year": 2022, "draft_capital_proxy_0_100": 62},
        ]
        canonical = build_canonical_historical_outcomes(
            [
                {"player_id": "a", "position": "WR", "draft_year": 2020, "top_finish_band": "TOP-24"},
                {"player_id": "b", "position": "RB", "draft_year": 2021, "top_finish_band": "RB30"},
                {"player_id": "c", "position": "TE", "draft_year": 2022, "career_outcome_label": "miss"},
            ]
        )
        labeled = build_labeled_rows(features, canonical, {})
        split = time_split(labeled, holdout_year=2022)
        consistency = build_historical_feature_consistency_report(labeled, ["athleticism_0_100", "speed_proxy_0_100"])
        self.assertIn("fallback_source_count", consistency["features"]["athleticism_0_100"])
        coverage = build_historical_class_coverage_report(features, labeled, canonical, split)
        self.assertIn("usable_rows_by_draft_year_position", coverage)

    def test_position_slice_report_and_thin_warning(self) -> None:
        features = [
            {"player_id": "a", "player_name": "A", "position": "WR", "draft_year": 2020, "draft_capital_proxy_0_100": 70},
            {"player_id": "b", "player_name": "B", "position": "RB", "draft_year": 2021, "draft_capital_proxy_0_100": 68},
            {"player_id": "c", "player_name": "C", "position": "QB", "draft_year": 2022, "draft_capital_proxy_0_100": 74},
        ]
        canonical = build_canonical_historical_outcomes(
            [
                {"player_id": "a", "position": "WR", "draft_year": 2020, "top_finish_band": "TOP-24"},
                {"player_id": "b", "position": "RB", "draft_year": 2021, "top_finish_band": "RB30"},
                {"player_id": "c", "position": "QB", "draft_year": 2022, "top_finish_band": "QB20"},
            ]
        )
        labeled = build_labeled_rows(features, canonical, {})
        report = build_historical_position_slices_report(labeled, canonical)
        self.assertIn("WR", report["positions"])
        self.assertFalse(report["positions"]["WR"]["ready_for_standalone_modeling"])

    def test_feature_importance_ordering(self) -> None:
        report = build_feature_importance_report(
            "logistic_full",
            ["a", "b", "c"],
            {"a": 0.1, "b": -0.5, "c": 0.2},
        )
        ranked = report["features_ranked"]
        self.assertEqual(ranked[0]["feature"], "b")
        self.assertEqual(ranked[0]["sign"], "negative")
        self.assertEqual(ranked[0]["abs_magnitude_rank"], 1)

    def test_end_to_end_report_contains_position_slices_and_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            features_path = root / "features.json"
            outcomes_path = root / "outcomes.json"
            alpha_dir = root / "alpha"
            output_dir = root / "out"
            alpha_dir.mkdir(parents=True)

            positions = ["WR", "RB", "TE", "QB"]
            features = []
            outcomes = []
            years = [2020, 2021, 2022, 2023]
            for year_idx, year in enumerate(years):
                for pos_idx, position in enumerate(positions):
                    player_id = f"{position.lower()}-{year}"
                    features.append(
                        {
                            "player_id": player_id,
                            "player_name": player_id,
                            "position": position,
                            "draft_year": year,
                            "draft_capital_proxy_0_100": 80 - (pos_idx * 5) - year_idx,
                            "age_at_draft": 21 + pos_idx,
                            "breakout_age": 19 + pos_idx,
                            "production_0_100": 60 + (pos_idx * 3),
                            "athleticism_0_100": 70 - pos_idx,
                            "size_context_0_100": 55 + pos_idx,
                            "speed_proxy_0_100": 65 - pos_idx,
                            "early_declare_flag": 1 if pos_idx % 2 == 0 else 0,
                        }
                    )
                    outcomes.append(
                        {
                            "player_id": player_id,
                            "position": position,
                            "top_finish_band": "TOP-24" if position in {"WR", "RB"} and year_idx % 2 == 0 else "QB15" if position == "QB" and year_idx % 2 == 0 else "TE20" if position == "TE" else "WR30",
                        }
                    )

            features_path.write_text(json.dumps(features), encoding="utf-8")
            outcomes_path.write_text(json.dumps(outcomes), encoding="utf-8")

            cmd = [
                "python3",
                "scripts/compute_rookie_ml_lane.py",
                "--historical-features",
                str(features_path),
                "--historical-outcomes",
                str(outcomes_path),
                "--rookie-alpha-dir",
                str(alpha_dir),
                "--holdout-year",
                "2023",
                "--output-dir",
                str(output_dir),
            ]
            subprocess.run(cmd, check=True)

            report = json.loads((output_dir / "evaluation_report.json").read_text(encoding="utf-8"))
            self.assertIn("missingness_summary", report)
            self.assertIn("draft_capital_dominance_check", report)
            self.assertIn("draft_capital_only", report["draft_capital_dominance_check"])
            self.assertIn("test_by_position", report["ml_models"]["logistic_full"])
            self.assertEqual(set(report["ml_models"]["logistic_full"]["test_by_position"].keys()), {"WR", "RB", "TE", "QB"})
            self.assertTrue((output_dir / "historical_outcomes_canonical.json").exists())
            self.assertTrue((output_dir / "historical_label_provenance_report.json").exists())
            self.assertTrue((output_dir / "historical_feature_consistency_report.json").exists())
            self.assertTrue((output_dir / "historical_class_coverage_report.json").exists())
            self.assertTrue((output_dir / "historical_position_slices_report.json").exists())


class ExperimentalOutputSemanticsTests(unittest.TestCase):
    """A generated future result must not read as promoted or calibrated (#286 WP-2)."""

    def test_default_output_dir_is_a_run_destination(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_DIR, "runs/rookie-ml-lane")
        self.assertNotIn("exports/promoted", DEFAULT_OUTPUT_DIR)
        # Critically, not the frozen archive: the documented default command
        # must not overwrite immutable historical bytes.
        self.assertNotEqual(DEFAULT_OUTPUT_DIR, "exports/experimental/rookie-ml-lane")

    def test_promoted_output_dir_is_refused(self) -> None:
        """Negative control: redirecting the producer must fail explicitly."""
        for candidate in (
            "exports/promoted/rookie-ml-lane",
            "exports/promoted",
            "exports/promoted/rookie-alpha",
            "exports/promoted/nested/deeper",
        ):
            with self.subTest(output_dir=candidate):
                with self.assertRaises(SystemExit) as raised:
                    reject_protected_output_dir(Path(candidate))
                self.assertIn("Refusing to write", str(raised.exception))

    def test_frozen_archive_output_dir_is_refused(self) -> None:
        """Negative control: a run must never target the immutable archive."""
        for candidate in (
            "exports/experimental/rookie-ml-lane",
            "exports/experimental/rookie-ml-lane/nested",
            "/somewhere/else/exports/experimental/rookie-ml-lane",
        ):
            with self.subTest(output_dir=candidate):
                with self.assertRaises(SystemExit) as raised:
                    reject_protected_output_dir(Path(candidate))
                self.assertIn("frozen migration archive", str(raised.exception))

    def test_run_output_dirs_are_allowed(self) -> None:
        for candidate in ("runs/rookie-ml-lane", "exports/candidate/x"):
            with self.subTest(output_dir=candidate):
                reject_protected_output_dir(Path(candidate))

    def test_promoted_redirect_fails_before_writing_anything(self) -> None:
        """The guard must refuse at the CLI boundary, not after producing files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            promoted_target = root / "exports/promoted/rookie-ml-lane"
            result = subprocess.run(
                [
                    "python3",
                    "scripts/compute_rookie_ml_lane.py",
                    "--output-dir",
                    str(promoted_target),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, "producer should exit non-zero")
            self.assertIn("Refusing to write", result.stdout + result.stderr)
            self.assertFalse(promoted_target.exists(), "no artifact may be written")

    def test_generated_report_and_sidecar_carry_experimental_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    "python3",
                    "scripts/compute_rookie_ml_lane.py",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            report = json.loads((output_dir / "evaluation_report.json").read_text(encoding="utf-8"))
            sidecar_path = output_dir / "experimental_status_v0.json"
            self.assertTrue(sidecar_path.is_file(), "status sidecar must accompany every run")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

            for payload, label in ((report, "evaluation_report"), (sidecar, "status sidecar")):
                with self.subTest(payload=label):
                    self.assertEqual(
                        payload["artifact_class"], "experimental_fixture_evaluation"
                    )
                    self.assertIs(payload["is_calibrated_probability"], False)
                    self.assertIs(payload["eligible_for_promotion"], False)
                    self.assertIn(
                        "not calibrated",
                        payload["uncalibrated_probability_warning"].lower(),
                    )

            self.assertEqual(sidecar["schema_version"], "experimental-status-v0.1.0")
            self.assertEqual(sidecar["status_kind"], "generated_run")
            self.assertIs(sidecar["replaces_deterministic_rookie_alpha"], False)
            # A run has performed no migration and must not claim archive provenance.
            self.assertNotIn("migration", sidecar)
            self.assertNotIn("frozen_historical_artifacts", sidecar)
            # The sidecar must inventory the run it accompanies, recursively and
            # with digests, so a nested file cannot hide and a byte edit cannot
            # pass on filename alone.
            produced = sorted(
                p.relative_to(output_dir).as_posix()
                for p in output_dir.rglob("*")
                if p.is_file() and p.name != "experimental_status_v0.json"
            )
            declared = sidecar["generated_artifacts"]
            self.assertEqual([a["path"] for a in declared], produced)
            for entry in declared:
                with self.subTest(artifact=entry["path"]):
                    target = output_dir / entry["path"]
                    self.assertEqual(entry["bytes"], target.stat().st_size)
                    self.assertEqual(
                        entry["sha256"],
                        hashlib.sha256(target.read_bytes()).hexdigest(),
                    )


if __name__ == "__main__":
    unittest.main()
