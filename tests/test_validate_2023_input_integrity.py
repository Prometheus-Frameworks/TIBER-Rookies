"""Regression coverage for issue #285 candidate input remediation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validate_2023_input_integrity import (
    DEFAULT_ARCHIVE,
    DEFAULT_MANIFEST,
    REPO_ROOT,
    validate_bundle,
    validate_candidate_documents,
)


CANDIDATE_DIR = REPO_ROOT / "data/candidate/2023_input_integrity/v0.1.0"


def load(name: str) -> dict:
    return json.loads((CANDIDATE_DIR / name).read_text(encoding="utf-8"))


def candidate_documents() -> tuple[dict, dict, dict, dict, dict]:
    return (
        load("combine_results_corrections.json"),
        load("pro_day_results_candidate.json"),
        load("college_production_corrections.json"),
        load("prospect_context_corrections.json"),
        load("nfl_outcome_regular_season_inputs.json"),
    )


class CandidateBundleTests(unittest.TestCase):
    def test_real_candidate_bundle_and_archive_validate(self) -> None:
        self.assertEqual(validate_bundle(REPO_ROOT, DEFAULT_MANIFEST, DEFAULT_ARCHIVE), [])

    def test_combine_and_pro_day_conflation_is_rejected(self) -> None:
        combine, pro_day, production, context, outcomes = map(copy.deepcopy, candidate_documents())
        puka = next(row for row in combine["records"] if row["player_id"] == "wr-puka-nacua")
        puka["forty"] = 4.55

        errors = validate_candidate_documents(combine, pro_day, production, context, outcomes)

        self.assertTrue(any("possible pro-day conflation" in error for error in errors))

    def test_aggregate_stat_scope_without_semantics_is_rejected(self) -> None:
        combine, pro_day, production, context, outcomes = map(copy.deepcopy, candidate_documents())
        production["records"][0]["stat_scope"] = "aggregate"

        errors = validate_candidate_documents(combine, pro_day, production, context, outcomes)

        self.assertTrue(any("aggregates are ambiguous" in error for error in errors))

    def test_ambiguous_and_post_cutoff_context_summary_is_rejected(self) -> None:
        combine, pro_day, production, context, outcomes = map(copy.deepcopy, candidate_documents())
        puka = next(row for row in context["records"] if row["player_id"] == "wr-puka-nacua")
        puka["candidate_evidence_summary"] = (
            "BYU WR — 1594 yds/10 TDs in 2022; 105 catches as NFL rookie."
        )

        errors = validate_candidate_documents(combine, pro_day, production, context, outcomes)

        self.assertTrue(any("ambiguous or post-cutoff" in error for error in errors))

    def test_four_season_player_cannot_be_marked_early_declare(self) -> None:
        combine, pro_day, production, context, outcomes = map(copy.deepcopy, candidate_documents())
        flowers = next(row for row in context["records"] if row["player_id"] == "wr-zay-flowers")
        flowers["early_declare_flag"] = True

        errors = validate_candidate_documents(combine, pro_day, production, context, outcomes)

        self.assertTrue(any("four-season player cannot be early_declare" in error for error in errors))

    def test_postseason_input_is_rejected(self) -> None:
        combine, pro_day, production, context, outcomes = map(copy.deepcopy, candidate_documents())
        outcomes["records"][0]["season_type"] = "POST"

        errors = validate_candidate_documents(combine, pro_day, production, context, outcomes)

        self.assertTrue(any("REG/POST mixing is forbidden" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
