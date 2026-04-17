import tempfile
import unittest
from pathlib import Path

from scripts.compute_rookie_alpha import (
    MergeDiagnostics,
    PlayerInputs,
    SPORQ_TRUST,
    _extract_sporq,
    _ras_confidence,
    load_context_by_player_id,
    coerce_float,
    compute_ras_scores,
    load_json,
    merge_inputs,
    resolve_athletic_input,
    rookie_alpha_score,
    sha256_file,
    write_outputs,
)


class RookieAlphaTests(unittest.TestCase):
    def test_ras_scoring_behavior(self) -> None:
        combine_rows = [
            {
                "player_id": "rb_fast",
                "player_name": "Fast Back",
                "position": "RB",
                "forty": 4.4,
                "vertical": 38,
                "broad": 125,
                "height_in": 71,
                "weight_lb": 210,
            },
            {
                "player_id": "rb_slow",
                "player_name": "Slow Back",
                "position": "RB",
                "forty": 4.65,
                "vertical": 31,
                "broad": 113,
                "height_in": 70,
                "weight_lb": 208,
            },
        ]

        scores, _, _, _ = compute_ras_scores(combine_rows)
        self.assertIn("rb_fast", scores)
        self.assertIn("rb_slow", scores)
        self.assertGreater(scores["rb_fast"], scores["rb_slow"])

    def test_rookie_alpha_score(self) -> None:
        player = PlayerInputs(
            player_id="p1",
            player_name="Player 1",
            position="WR",
            ras_score_0_100=80.0,
            production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
            age_adjusted_production_0_100=58.0,
        )
        self.assertAlmostEqual(rookie_alpha_score(player), 69.0)

    def test_rookie_alpha_applies_production_fallback_when_age_adjusted_missing(self) -> None:
        player = PlayerInputs(
            player_id="p1",
            player_name="Player 1",
            position="WR",
            ras_score_0_100=80.0,
            production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
            age_adjusted_production_0_100=None,
        )
        # effective production = 60 * 0.85 = 51
        self.assertAlmostEqual(rookie_alpha_score(player), 64.95)

    def test_rookie_alpha_keeps_production_when_age_adjusted_present(self) -> None:
        player = PlayerInputs(
            player_id="p1",
            player_name="Player 1",
            position="WR",
            ras_score_0_100=80.0,
            production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
            age_adjusted_production_0_100=58.0,
        )
        self.assertAlmostEqual(rookie_alpha_score(player), 69.0)

    def test_merge_inputs(self) -> None:
        combine_rows = [
            {
                "player_id": "p1",
                "player_name": "One",
                "position": "WR",
                "forty": 4.4,
            }
        ]
        production_rows = [
            {
                "player_id": "p2",
                "player_name": "Two",
                "position": "RB",
                "production_score_0_100": 75,
            }
        ]
        draft_rows = [
            {
                "player_id": "p3",
                "player_name": "Three",
                "position": "TE",
                "draft_capital_proxy_0_100": 85,
            }
        ]

        players, diagnostics, _ = merge_inputs(combine_rows, production_rows, draft_rows)
        self.assertEqual(players, [])
        # RAS (combine) is optional — only prod+draft are required.
        # p2 has prod but no draft; p3 has draft but no prod → both excluded.
        # p1 (combine only) is not in the prod/draft universe at all.
        self.assertEqual(diagnostics.excluded_for_missing_sources["total_excluded"], 2)

    def test_merge_inputs_excludes_cross_source_identity_mismatches(self) -> None:
        combine_rows = [
            {"player_id": "p1", "player_name": "Name One", "position": "WR", "forty": 4.4},
        ]
        production_rows = [
            {"player_id": "p1", "player_name": "Name Two", "position": "WR", "production_score_0_100": 80},
        ]
        draft_rows = [
            {"player_id": "p1", "player_name": "Name One", "position": "WR", "draft_capital_proxy_0_100": 70},
        ]
        players, diagnostics, _ = merge_inputs(combine_rows, production_rows, draft_rows)
        self.assertEqual(players, [])
        self.assertEqual(diagnostics.identity_conflicts_skipped, 1)

    def test_draft_capital_proxy_handling(self) -> None:
        players = [
            PlayerInputs("p1", "One", "WR", 80, 80, None),
            PlayerInputs("p2", "Two", "WR", 80, 80, 100),
        ]
        self.assertLess(rookie_alpha_score(players[0]), rookie_alpha_score(players[1]))

    def test_missing_input_behavior_and_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_json = tmp_path / "out.json"
            out_csv = tmp_path / "out.csv"
            out_manifest = tmp_path / "manifest.json"
            combine = tmp_path / "combine.json"
            production = tmp_path / "production.json"
            draft = tmp_path / "draft.json"
            combine.write_text("[]\n", encoding="utf-8")
            production.write_text("[]\n", encoding="utf-8")
            draft.write_text("[]\n", encoding="utf-8")
            player = PlayerInputs(
                player_id="p_missing",
                player_name="Missing Inputs",
                position="QB",
                ras_score_0_100=None,
                production_score_0_100=60.0,
                draft_capital_proxy_0_100=None,
            )
            with self.assertLogs(level="WARNING") as cm:
                write_outputs(
                    players=[player],
                    merge_diagnostics=MergeDiagnostics(0, 0, {"missing_combine": 0, "missing_production": 0, "missing_draft_proxy": 0, "total_excluded": 0}),
                    season=2026,
                    combine_path=combine,
                    production_path=production,
                    draft_proxy_path=draft,
                    output_json=out_json,
                    output_csv=out_csv,
                    output_manifest=out_manifest,
                )
            self.assertTrue(any("Defaulting missing inputs to 50.0" in line for line in cm.output))

    def test_write_outputs_creates_manifest_with_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            combine = tmp_path / "combine.json"
            production = tmp_path / "production.json"
            draft = tmp_path / "draft.json"
            combine.write_text("[]\n", encoding="utf-8")
            production.write_text("[]\n", encoding="utf-8")
            draft.write_text("[]\n", encoding="utf-8")
            out_json = tmp_path / "out.json"
            out_csv = tmp_path / "out.csv"
            out_manifest = tmp_path / "manifest.json"

            write_outputs(
                players=[],
                merge_diagnostics=MergeDiagnostics(0, 0, {"missing_combine": 0, "missing_production": 0, "missing_draft_proxy": 0, "total_excluded": 0}),
                season=2026,
                combine_path=combine,
                production_path=production,
                draft_proxy_path=draft,
                output_json=out_json,
                output_csv=out_csv,
                output_manifest=out_manifest,
            )
            manifest = load_json(out_manifest)
            self.assertEqual(manifest["season"], 2026)
            self.assertEqual(manifest["output_files"][0]["sha256"], sha256_file(out_json))
            self.assertEqual(manifest["output_files"][1]["sha256"], sha256_file(out_csv))
            self.assertEqual(manifest["input_files"][0]["row_count"], 0)
            self.assertEqual(manifest["export_metadata"]["coverage_summary"], manifest["coverage_summary"])
            self.assertEqual(manifest["model_version"], "rookie-alpha-predraft-v0.4.0")

    def test_context_is_additive_and_optional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            combine = tmp_path / "combine.json"
            production = tmp_path / "production.json"
            draft = tmp_path / "draft.json"
            context = tmp_path / "context.json"
            combine.write_text("[]\n", encoding="utf-8")
            production.write_text("[]\n", encoding="utf-8")
            draft.write_text("[]\n", encoding="utf-8")
            context.write_text(
                '[{"player_id":"p1","player_name":"One","position":"WR","school":"School","class_year":2026,"evidence_tags":["early_declare"],"context_flags":["limited_multi_season_data"],"evidence_summary":"Summary."}]',
                encoding="utf-8",
            )
            out_json = tmp_path / "out.json"
            out_csv = tmp_path / "out.csv"
            out_manifest = tmp_path / "manifest.json"
            player = PlayerInputs("p1", "One", "WR", 80.0, 70.0, 60.0)
            write_outputs(
                players=[player],
                merge_diagnostics=MergeDiagnostics(0, 0, {"missing_combine": 0, "missing_production": 0, "missing_draft_proxy": 0, "total_excluded": 0}),
                season=2026,
                combine_path=combine,
                production_path=production,
                draft_proxy_path=draft,
                output_json=out_json,
                output_csv=out_csv,
                output_manifest=out_manifest,
                context_path=context,
                context_by_id=load_context_by_player_id(context),
            )
            payload = load_json(out_json)
            self.assertIn("context", payload["players"][0])
            self.assertIn("evidence", payload["players"][0])
            self.assertEqual(payload["coverage_summary"]["players_with_context_fields"], 1)
            self.assertIn(str(context), payload["source_files_used"])

    def test_missing_context_file_does_not_fail(self) -> None:
        context_map = load_context_by_player_id(Path("/tmp/missing-context-file.json"))
        self.assertEqual(context_map, {})

    def test_missing_required_player_fields_are_skipped(self) -> None:
        players, _, _ = merge_inputs(
            combine_rows=[{"player_name": "No Id", "position": "WR", "forty": 4.5}],
            production_rows=[],
            draft_proxy_rows=[],
        )
        self.assertEqual(players, [])

    def test_load_json_errors_are_friendly(self) -> None:
        with self.assertRaises(SystemExit) as missing_file_error:
            load_json(Path("/tmp/does-not-exist.json"))
        self.assertIn("Input file not found", str(missing_file_error.exception))

        with tempfile.TemporaryDirectory() as tmp:
            invalid_json = Path(tmp) / "bad.json"
            invalid_json.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(SystemExit) as invalid_json_error:
                load_json(invalid_json)
            self.assertIn("Invalid JSON", str(invalid_json_error.exception))

    def test_coerce_float_warning_dedup_is_call_scoped(self) -> None:
        with self.assertLogs(level="WARNING") as cm:
            coerce_float("bad", "forty", "p1", "combine input")
            coerce_float("bad", "forty", "p1", "combine input")
        self.assertEqual(len(cm.output), 2)


class ExtractSporqTests(unittest.TestCase):
    def test_extracts_sporq_from_exceptional_metrics(self) -> None:
        context = {
            "exceptional_metrics": [
                {"metric": "sporq_percentile", "value": 99.0, "context": "Elite SPORQ"},
            ]
        }
        val, ctx = _extract_sporq(context)
        self.assertAlmostEqual(val, 99.0)
        self.assertEqual(ctx, "Elite SPORQ")

    def test_returns_none_for_no_sporq(self) -> None:
        context = {"exceptional_metrics": [{"metric": "other", "value": 50}]}
        val, ctx = _extract_sporq(context)
        self.assertIsNone(val)
        self.assertIsNone(ctx)

    def test_returns_none_for_empty_context(self) -> None:
        val, ctx = _extract_sporq(None)
        self.assertIsNone(val)
        self.assertIsNone(ctx)

    def test_returns_none_for_missing_value(self) -> None:
        context = {"exceptional_metrics": [{"metric": "sporq_percentile", "value": None}]}
        val, ctx = _extract_sporq(context)
        self.assertIsNone(val)


class RasConfidenceTests(unittest.TestCase):
    def test_five_components_full_confidence(self) -> None:
        self.assertAlmostEqual(_ras_confidence(5), 1.0)

    def test_four_components(self) -> None:
        self.assertAlmostEqual(_ras_confidence(4), 0.95)

    def test_three_components(self) -> None:
        self.assertAlmostEqual(_ras_confidence(3), 0.85)

    def test_two_components(self) -> None:
        self.assertAlmostEqual(_ras_confidence(2), 0.80)

    def test_monotonic_increase(self) -> None:
        self.assertLessEqual(_ras_confidence(2), _ras_confidence(3))
        self.assertLessEqual(_ras_confidence(3), _ras_confidence(4))
        self.assertLessEqual(_ras_confidence(4), _ras_confidence(5))


class ResolveAthleticInputTests(unittest.TestCase):
    def test_ras_is_preferred_over_sporq(self) -> None:
        context = {"exceptional_metrics": [{"metric": "sporq_percentile", "value": 99.0}]}
        score, source, conf, explainer, sporq_used = resolve_athletic_input(
            "p1", "TE", ras_score=80.0, ras_metric_count=5,
            combine_fallback_entry=None, context=context,
        )
        self.assertAlmostEqual(score, 80.0)
        self.assertEqual(source, "RAS")
        self.assertAlmostEqual(conf, 1.0)
        self.assertFalse(sporq_used)

    def test_sporq_used_for_te_when_no_ras(self) -> None:
        context = {"exceptional_metrics": [{"metric": "sporq_percentile", "value": 95.0, "context": "Top SPORQ"}]}
        score, source, conf, explainer, sporq_used = resolve_athletic_input(
            "p1", "TE", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=None, context=context,
        )
        self.assertAlmostEqual(score, 95.0)
        self.assertEqual(source, "SPORQ")
        self.assertAlmostEqual(conf, 0.75)
        self.assertTrue(sporq_used)

    def test_sporq_ignored_for_wr(self) -> None:
        context = {"exceptional_metrics": [{"metric": "sporq_percentile", "value": 95.0}]}
        score, source, conf, explainer, sporq_used = resolve_athletic_input(
            "p1", "WR", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=None, context=context,
        )
        self.assertIsNone(score)
        self.assertIsNone(source)
        self.assertFalse(sporq_used)

    def test_sporq_ignored_for_rb(self) -> None:
        context = {"exceptional_metrics": [{"metric": "sporq_percentile", "value": 95.0}]}
        score, source, conf, _, sporq_used = resolve_athletic_input(
            "p1", "RB", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=None, context=context,
        )
        self.assertIsNone(score)
        self.assertFalse(sporq_used)

    def test_combine_fallback_used_when_no_ras_or_sporq(self) -> None:
        score, source, conf, explainer, sporq_used = resolve_athletic_input(
            "p1", "WR", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=(55.0, 2), context=None,
        )
        self.assertAlmostEqual(score, 55.0)
        self.assertEqual(source, "COMBINE_FALLBACK")
        # confidence = 0.30 + 0.10 * min(2, 2) = 0.50
        self.assertAlmostEqual(conf, 0.50)
        self.assertFalse(sporq_used)

    def test_combine_fallback_confidence_for_one_metric(self) -> None:
        _, _, conf, _, _ = resolve_athletic_input(
            "p1", "WR", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=(45.0, 1), context=None,
        )
        # confidence = 0.30 + 0.10 * min(1, 2) = 0.40
        self.assertAlmostEqual(conf, 0.40)

    def test_no_data_returns_none(self) -> None:
        score, source, conf, explainer, sporq_used = resolve_athletic_input(
            "p1", "WR", ras_score=None, ras_metric_count=0,
            combine_fallback_entry=None, context=None,
        )
        self.assertIsNone(score)
        self.assertIsNone(source)
        self.assertAlmostEqual(conf, 0.0)
        self.assertIsNone(explainer)
        self.assertFalse(sporq_used)

    def test_ras_confidence_varies_by_metric_count(self) -> None:
        _, _, conf5, _, _ = resolve_athletic_input(
            "p1", "WR", ras_score=80.0, ras_metric_count=5,
            combine_fallback_entry=None, context=None,
        )
        _, _, conf3, _, _ = resolve_athletic_input(
            "p1", "WR", ras_score=80.0, ras_metric_count=3,
            combine_fallback_entry=None, context=None,
        )
        self.assertGreater(conf5, conf3)


class AthleticScoreInAlphaTests(unittest.TestCase):
    def test_athletic_score_used_in_alpha_when_set(self) -> None:
        player_with_ath = PlayerInputs(
            player_id="p1", player_name="Player", position="WR",
            ras_score_0_100=None, production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
            athletic_score_0_100=90.0, athletic_source="SPORQ",
            athletic_confidence=0.75,
        )
        player_no_ath = PlayerInputs(
            player_id="p2", player_name="Player2", position="WR",
            ras_score_0_100=None, production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
            athletic_score_0_100=None, athletic_source=None,
            athletic_confidence=0.0,
        )
        score_with = rookie_alpha_score(player_with_ath)
        score_without = rookie_alpha_score(player_no_ath)
        # Higher athletic score should produce higher alpha
        self.assertGreater(score_with, score_without)

    def test_ras_still_works_as_fallback(self) -> None:
        player = PlayerInputs(
            player_id="p1", player_name="Player", position="WR",
            ras_score_0_100=80.0, production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
        )
        # With no athletic_score_0_100 set, should fall back to ras_score_0_100
        score = rookie_alpha_score(player)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0)


class SporqTrustConfigTests(unittest.TestCase):
    def test_te_is_preferred(self) -> None:
        self.assertEqual(SPORQ_TRUST["TE"], "preferred")

    def test_wr_is_supplemental(self) -> None:
        self.assertEqual(SPORQ_TRUST["WR"], "supplemental")

    def test_rb_qb_are_ignore(self) -> None:
        self.assertEqual(SPORQ_TRUST["RB"], "ignore")
        self.assertEqual(SPORQ_TRUST["QB"], "ignore")


if __name__ == "__main__":
    unittest.main()
