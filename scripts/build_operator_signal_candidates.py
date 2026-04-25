#!/usr/bin/env python3
"""Build operator journal signal candidates from raw notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/operator-journal/raw/2026_rookie_journal_entries.json")
DEFAULT_OUTPUT = Path("data/operator-journal/processed/2026_operator_signal_candidates.json")


def _extract_segment(text: str, start_marker: str, end_marker: str | None = None) -> str:
    if start_marker not in text:
        return ""

    segment = text.split(start_marker, maxsplit=1)[1]
    if end_marker and end_marker in segment:
        segment = segment.split(end_marker, maxsplit=1)[0]

    return segment.strip().strip(".")


def _split_entities(segment: str) -> list[str]:
    return [value.strip() for value in segment.split(",") if value.strip()]


def _base_candidate(entry: dict[str, Any], candidate_id: str, entity_type: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_entry_id": entry["entry_id"],
        "entity_type": entity_type,
        "player_name": None,
        "team": None,
        "position": None,
        "related_entities": [],
        "claim_summary": "",
        "positive_signal_tags": [],
        "risk_tags": [],
        "context_tags": [],
        "model_impact": "",
        "downstream_repos": [],
        "confidence": "medium",
        "needs_verification": True,
        "source_type": "operator_journal",
        "review_status": "needs_human_review",
    }


def build_candidates_for_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    entry_id = entry["entry_id"]

    if "antonio_williams" in entry_id:
        candidate = _base_candidate(entry, "cand_2026_antonio_williams_context", "player")
        candidate.update(
            {
                "player_name": "Antonio Williams",
                "team": "Commanders",
                "position": "WR",
                "claim_summary": (
                    "Landing spot and role-path note indicating immediate slot-path opportunity in a "
                    "high-upside offense context."
                ),
                "positive_signal_tags": [
                    "available_target_opportunity",
                    "high_upside_offense",
                    "jayden_daniels_environment",
                    "slot_role_path",
                    "freshman_contributor_signal",
                    "separator_profile",
                ],
                "risk_tags": [
                    "size_concern",
                    "round3_insulation_risk",
                    "role_projection_uncertainty",
                ],
                "context_tags": ["operator_note", "post_draft_context"],
                "model_impact": "review_for_post_draft_context_bump",
                "downstream_repos": ["TIBER-Rookies"],
                "confidence": "medium_high",
            }
        )
        return [candidate]

    if "13_personnel" in entry_id:
        candidate = _base_candidate(entry, "cand_2026_heavy_te_meta", "team_meta")
        candidate.update(
            {
                "team": "Rams",
                "claim_summary": (
                    "Heavy 13-personnel usage and efficiency note; possible offensive meta with two-WR "
                    "target concentration dynamics."
                ),
                "positive_signal_tags": ["heavy_te_personnel_meta", "13_personnel_efficiency_signal"],
                "risk_tags": [
                    "te_target_suppression_possible",
                    "scheme_dependency",
                    "role_specific_usage_dependency",
                ],
                "context_tags": ["wr_target_consolidation_possible", "two_wr_set_target_focus"],
                "downstream_repos": ["TIBER-Teamstate", "Role-and-Opportunity", "TIBER-Rookies"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "post_draft_watchlist" in entry_id:
        stock_up = _split_entities(_extract_segment(entry["entry_text"], "Stock up:", "Stock down:"))
        stock_down = _split_entities(_extract_segment(entry["entry_text"], "Stock down:", "Treat this"))

        candidate = _base_candidate(entry, "cand_2026_post_draft_market_watchlist", "market_watchlist")
        candidate.update(
            {
                "claim_summary": "Post-draft market reaction watchlist from operator journal.",
                "related_entities": stock_up + stock_down,
                "positive_signal_tags": ["stock_up", "stock_down"],
                "context_tags": ["post_draft_market_reaction", "opportunity_shift_watch"],
                "risk_tags": ["reaction_noise_risk"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "ty_simpson" in entry_id:
        candidate = _base_candidate(entry, "cand_2026_ty_simpson_experience_risk", "player")
        candidate.update(
            {
                "player_name": "Ty Simpson",
                "position": "QB",
                "related_entities": [
                    "Carson Wentz",
                    "Mark Sanchez",
                    "Mac Jones",
                    "Mitch Trubisky",
                    "Dwayne Haskins",
                ],
                "claim_summary": "Low-experience Round 1 QB historical cohort with developmental variance risk.",
                "positive_signal_tags": ["round1_qb_capital", "mcvay_developmental_environment"],
                "risk_tags": [
                    "low_college_attempt_sample",
                    "limited_dual_threat_floor",
                    "round1_qb_experience_risk",
                    "developmental_qb_variance",
                ],
                "context_tags": ["historical_comparison_candidate", "verification_required"],
                "model_impact": "cap_aggressive_ty_simpson_bump",
                "downstream_repos": ["TIBER-Rookies"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "tanner_koziol" in entry_id:
        candidate = _base_candidate(entry, "cand_2026_tanner_koziol_model_edge_validation", "player")
        candidate.update(
            {
                "player_name": "Tanner Koziol",
                "team": "Jaguars",
                "position": "TE",
                "claim_summary": "Round 5 selection aligning with prior +18 TIBER model-edge note.",
                "positive_signal_tags": [
                    "model_edge_confirmed_by_draft_capital",
                    "late_round_te_watch",
                    "data_savvy_org_validation",
                    "jaguars_te_depth_watch",
                ],
                "risk_tags": [
                    "round5_insulation_risk",
                    "delayed_te_translation_watch",
                    "low_draft_capital_volume_uncertainty",
                    "depth_chart_path_uncertain",
                ],
                "context_tags": ["tiber_edge_plus_18", "round5_te_capital", "post_draft_watchlist"],
                "model_impact": "track_as_late_round_model_edge_validation_candidate",
                "downstream_repos": ["TIBER-Rookies", "TIBER-Teamstate", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )
        return [candidate]

    return []


def build_candidates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        candidates.extend(build_candidates_for_entry(entry))

    return sorted(candidates, key=lambda value: value["candidate_id"])


def write_candidates(input_path: Path, output_path: Path) -> list[dict[str, Any]]:
    entries = json.loads(input_path.read_text(encoding="utf-8"))
    candidates = build_candidates(entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
    return candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Raw operator journal entries JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Candidate signal output JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_candidates(args.input, args.output)


if __name__ == "__main__":
    main()
