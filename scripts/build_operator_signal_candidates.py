#!/usr/bin/env python3
"""Build operator journal signal candidates from raw notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/operator-journal/raw/2026_rookie_journal_entries.json")
DEFAULT_OUTPUT = Path("data/operator-journal/processed/2026_operator_signal_candidates.json")


class UnmappedJournalEntriesError(ValueError):
    """Raised when one or more raw operator notes do not map to candidate rules."""


def _extract_segment(text: str, start_marker: str, end_marker: str | None = None) -> str:
    if start_marker not in text:
        return ""

    segment = text.split(start_marker, maxsplit=1)[1]
    if end_marker and end_marker in segment:
        segment = segment.split(end_marker, maxsplit=1)[0]

    return segment.strip().strip(".")


def _split_entities(segment: str) -> list[str]:
    return [value.strip() for value in segment.split(",") if value.strip()]


def _base_candidate(entry: dict[str, Any], suffix: str, entity_type: str) -> dict[str, Any]:
    return {
        "candidate_id": f"cand_{entry['entry_id']}_{suffix}",
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
        candidate = _base_candidate(entry, "context", "player")
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
        candidate = _base_candidate(entry, "team_meta", "team_meta")
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

        candidate = _base_candidate(entry, "market_watchlist", "market_watchlist")
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
        candidate = _base_candidate(entry, "experience_risk", "player")
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

    if entry_id == "oj_2026_012_tanner_koziol_jaguars":
        receiving_move_te = _base_candidate(entry, "receiving_move_te_archetype_correction", "player")
        receiving_move_te.update(
            {
                "player_name": "Tanner Koziol",
                "team": "Jaguars",
                "position": "TE",
                "candidate_theme": "receiving_move_te_archetype_correction",
                "claim_summary": (
                    "Tanner Koziol should be evaluated primarily as a receiving/move TE with blocking risk, "
                    "not as a blocking-heavy rotational TE."
                ),
                "positive_signal_tags": [
                    "receiving_te_archetype",
                    "move_te_candidate",
                    "elite_te_reception_volume",
                    "non_screen_reception_volume_signal",
                    "contested_catch_strength",
                    "red_zone_target_candidate",
                    "body_control_at_size",
                    "high_ras_size_adjusted_signal",
                    "short_intermediate_target_earner",
                ],
                "risk_tags": [
                    "blocking_risk",
                    "day3_capital_risk",
                    "low_deep_usage_risk",
                    "limited_yac_profile",
                    "role_ceiling_uncertainty",
                    "year1_route_share_uncertainty",
                ],
                "context_tags": [
                    "jaguars_te_room_watch",
                    "tiber_role_archetype_correction",
                    "receiving_role_over_blocking_role",
                    "late_round_te_watch",
                ],
                "model_impact": (
                    "review_role_mapping_to_prioritize_move_te_receiving_role_over_blocking_rotational_te"
                ),
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "high",
            }
        )

        red_zone_fit_watch = _base_candidate(entry, "jaguars_red_zone_fit_watch", "player")
        red_zone_fit_watch.update(
            {
                "player_name": "Tanner Koziol",
                "team": "Jaguars",
                "position": "TE",
                "candidate_theme": "jaguars_red_zone_fit_watch",
                "claim_summary": (
                    "Koziol's contested-catch profile and size may create a Jaguars red-zone role path, but "
                    "Trevor Lawrence / Jacksonville TE red-zone tendency needs play-by-play verification "
                    "before promotion."
                ),
                "positive_signal_tags": [
                    "contested_catch_strength",
                    "red_zone_target_candidate",
                    "size_mismatch_te",
                    "trevor_lawrence_te_usage_watch",
                    "evan_engram_usage_comp_watch",
                ],
                "risk_tags": [
                    "requires_red_zone_target_verification",
                    "day3_capital_risk",
                    "depth_chart_path_uncertain",
                    "usage_projection_uncertainty",
                ],
                "context_tags": [
                    "red_zone_play_by_play_needed",
                    "jaguars_landing_spot_fit_watch",
                    "operator_signal_needs_verification",
                ],
                "model_impact": "flag_for_red_zone_usage_research_before_adjusting_role_confidence",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity", "TIBER-Teamstate"],
                "confidence": "medium",
            }
        )

        low_deep_usage_risk = _base_candidate(entry, "low_deep_usage_te_risk", "player")
        low_deep_usage_risk.update(
            {
                "player_name": "Tanner Koziol",
                "team": "Jaguars",
                "position": "TE",
                "candidate_theme": "low_deep_usage_te_risk",
                "claim_summary": (
                    "Koziol's low deep-yardage share may cap his NFL receiving ceiling despite elite "
                    "short/intermediate volume."
                ),
                "positive_signal_tags": [
                    "elite_short_intermediate_volume",
                    "power_conference_yptpa_signal",
                    "high_reception_share_te",
                ],
                "risk_tags": [
                    "low_deep_usage_risk",
                    "historical_deep_usage_threshold_risk",
                    "role_ceiling_uncertainty",
                    "fantasy_ceiling_risk",
                ],
                "context_tags": [
                    "under_10_percent_deep_yard_share",
                    "drafted_te_low_deep_usage_cohort",
                    "cade_otton_dalton_schultz_exception_watch",
                ],
                "model_impact": "track_as_volume_floor_te_with_deep_usage_ceiling_risk",
                "downstream_repos": ["TIBER-Rookies"],
                "confidence": "medium",
            }
        )

        return [receiving_move_te, red_zone_fit_watch, low_deep_usage_risk]

    if entry_id == "oj_2026_005_tanner_koziol":
        candidate = _base_candidate(entry, "model_edge_validation", "player")
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

    if "nick_singleton_titans" in entry_id:
        candidate = _base_candidate(entry, "landing_spot_missing_data_audit", "player")
        candidate.update(
            {
                "player_name": "Nick Singleton",
                "team": "Titans",
                "position": "RB",
                "claim_summary": (
                    "Negative pre-draft model-edge context with landing-spot opportunity and missing-data "
                    "audit note for profile completeness review."
                ),
                "positive_signal_tags": [
                    "athletic_rb_profile",
                    "early_age_production_signal",
                    "receiving_efficiency_signal",
                    "titans_backfield_opportunity",
                    "pollard_contract_year",
                    "spears_workload_size_question",
                ],
                "risk_tags": [
                    "mid_late_round_capital_risk",
                    "longshot_backfield_takeover",
                    "predraft_model_negative_edge",
                    "incomplete_profile_data_risk",
                    "role_projection_uncertainty",
                ],
                "context_tags": [
                    "model_edge_minus_10",
                    "missing_data_audit",
                    "post_draft_landing_spot_watch",
                ],
                "model_impact": "review_profile_data_completeness_before_final_take",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "emmett_johnson_chiefs" in entry_id:
        candidate = _base_candidate(entry, "passing_down_role_watch", "player")
        candidate.update(
            {
                "player_name": "Emmett Johnson",
                "team": "Chiefs",
                "position": "RB",
                "claim_summary": (
                    "Late-round role-path watch focused on passing-down deployment and injury-contingent "
                    "upside in a high-powered offense."
                ),
                "positive_signal_tags": [
                    "high_powered_offense",
                    "passing_down_role_path",
                    "injury_contingent_upside",
                    "late_round_role_watch",
                ],
                "risk_tags": [
                    "round5_insulation_risk",
                    "low_predraft_alpha",
                    "limited_model_evidence",
                    "role_projection_uncertainty",
                    "depth_chart_dependency",
                ],
                "context_tags": [
                    "predraft_alpha_36_4",
                    "chiefs_passing_down_watch",
                    "post_draft_watchlist",
                ],
                "model_impact": "track_as_late_round_role_path_candidate",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "low_medium",
            }
        )
        return [candidate]

    if "skyler_bell_bills_model_edge" in entry_id:
        candidate = _base_candidate(entry, "model_edge_landing_spot_validation", "player")
        candidate.update(
            {
                "player_name": "Skyler Bell",
                "team": "Bills",
                "position": "WR",
                "claim_summary": (
                    "Positive model-edge note with favorable NFL landing spot and role opportunity, tracked "
                    "as validation-watch only."
                ),
                "positive_signal_tags": [
                    "model_edge_confirmed_by_landing_spot",
                    "wr2_wr3_path",
                    "available_target_opportunity",
                    "strong_landing_spot",
                    "post_draft_role_opportunity",
                ],
                "risk_tags": [
                    "late_selection_urgency_concern",
                    "low_draft_capital_insulation",
                    "role_competition_risk",
                    "model_edge_validation_needed",
                ],
                "context_tags": [
                    "predraft_alpha_62_3",
                    "tiber_edge_plus_18",
                    "bills_wr_room_watch",
                    "post_draft_watchlist",
                ],
                "model_impact": "track_as_model_edge_role_opportunity_candidate",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "germie_bernard_mccarthy_slot" in entry_id:
        candidate = _base_candidate(entry, "slot_role_context", "player")
        candidate.update(
            {
                "player_name": "Germie Bernard",
                "team": "Steelers",
                "position": "WR",
                "claim_summary": (
                    "Early Round 2 trade-up with positive model-edge and slot-role coaching-context note for "
                    "role-opportunity review."
                ),
                "positive_signal_tags": [
                    "early_round2_trade_up",
                    "slot_role_coaching_signal",
                    "mccarthy_slot_wr_history",
                    "model_edge_positive",
                    "role_archetype_fit_watch",
                ],
                "risk_tags": [
                    "coach_context_transfer_risk",
                    "steelers_wr_room_watch",
                    "qb_room_uncertainty",
                    "year1_volume_uncertainty",
                ],
                "context_tags": [
                    "predraft_alpha_55_5",
                    "tiber_edge_plus_6_5",
                    "mccarthy_slot_fpg_signal",
                    "post_draft_role_watch",
                ],
                "model_impact": "review_slot_role_context_in_role_opportunity_layer",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity", "TIBER-Teamstate"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "malachi_fields_giants" in entry_id:
        candidate = _base_candidate(entry, "landing_spot_over_profile", "player")
        candidate.update(
            {
                "player_name": "Malachi Fields",
                "team": "Giants",
                "position": "WR",
                "claim_summary": (
                    "Landing-spot opportunity note despite weaker profile and negative model-edge; tracked "
                    "as landing-spot-over-profile watch candidate."
                ),
                "positive_signal_tags": [
                    "year1_route_path",
                    "full_time_route_runner_opportunity",
                    "improved_offense_watch",
                    "landing_spot_opportunity",
                ],
                "risk_tags": [
                    "low_predraft_alpha",
                    "negative_model_edge",
                    "college_efficiency_concern",
                    "man_coverage_struggle",
                    "role_competition_risk",
                ],
                "context_tags": [
                    "predraft_alpha_39_5",
                    "pick_74_context",
                    "giants_wr_room_watch",
                    "post_draft_landing_spot_watch",
                ],
                "model_impact": "track_as_landing_spot_opportunity_over_profile_candidate",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )
        return [candidate]

    if "brenen_thompson_chargers" in entry_id:
        vertical_role_watch = _base_candidate(entry, "vertical_role_watch", "player")
        vertical_role_watch.update(
            {
                "player_name": "Brenen Thompson",
                "team": "Chargers",
                "position": "WR",
                "candidate_theme": "vertical_field_stretcher_role_watch",
                "claim_summary": (
                    "Brenen Thompson has legitimate elite-speed vertical-stretcher traits and SEC "
                    "production, but likely opens as a rotational WR4 whose fantasy path depends on a "
                    "future Chargers depth-chart opening."
                ),
                "positive_signal_tags": [
                    "elite_speed_archetype",
                    "vertical_field_stretcher",
                    "sec_receiving_yardage_leader",
                    "explosive_yards_per_catch",
                    "power4_yprr_signal",
                    "cushion_creator",
                    "ball_tracking_downfield",
                    "adjusted_contested_target_rate_signal",
                ],
                "risk_tags": [
                    "rotational_wr4_path",
                    "low_volume_role_risk",
                    "undersized_frame_risk",
                    "durability_risk",
                    "limited_target_earning_profile",
                    "limited_prior_production",
                    "contested_catch_risk",
                    "drop_rate_risk",
                    "chargers_depth_chart_block",
                    "deep_protection_dependency",
                ],
                "context_tags": [
                    "predraft_alpha_44_2",
                    "tiber_edge_plus_4_7",
                    "chargers_vertical_role_watch",
                    "qj_future_departure_contingency",
                ],
                "model_impact": "track_as_vertical_role_watch_not_immediate_fantasy_bump",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )

        profile_completeness_audit = _base_candidate(entry, "profile_completeness_audit", "player")
        profile_completeness_audit.update(
            {
                "player_name": "Brenen Thompson",
                "team": "Chargers",
                "position": "WR",
                "candidate_theme": "profile_completeness_audit",
                "claim_summary": (
                    "TIBER profile may be incomplete or stale because the writeup says production profile "
                    "pending CFBD fetch and no translation evidence tags available, despite available 2025 "
                    "production/YPRR/aDOT/separation evidence."
                ),
                "positive_signal_tags": [
                    "production_data_available",
                    "translation_evidence_available",
                    "sec_2025_breakout",
                    "vertical_efficiency_signal",
                ],
                "risk_tags": [
                    "stale_profile_writeup",
                    "missing_translation_evidence_tags",
                    "possible_undergraded_production",
                    "profile_data_completeness_risk",
                ],
                "context_tags": [
                    "missing_data_audit",
                    "production_profile_pending_conflict",
                    "no_translation_tags_conflict",
                    "predraft_alpha_44_2",
                    "production_grade_43_7",
                ],
                "model_impact": "review_player_profile_data_completeness_before_final_role_take",
                "downstream_repos": ["TIBER-Rookies"],
                "confidence": "high",
            }
        )
        return [vertical_role_watch, profile_completeness_audit]

    if entry_id == "oj_2026_013_jordyn_tyson_saints":
        kellen_moore_environment = _base_candidate(entry, "kellen_moore_premium_wr_environment", "player")
        kellen_moore_environment.update(
            {
                "player_name": "Jordyn Tyson",
                "team": "Saints",
                "position": "WR",
                "candidate_theme": "kellen_moore_premium_wr_environment",
                "claim_summary": (
                    "Jordyn Tyson’s Saints landing spot may deserve a premium environment tag because "
                    "Kellen Moore’s offense projects as pass-aggressive, scheme-flexible, and capable "
                    "of supporting multiple productive WRs."
                ),
                "positive_signal_tags": [
                    "kellen_moore_environment",
                    "premium_wr_capital",
                    "pass_volume_projection_watch",
                    "scheme_flexibility_signal",
                    "multiple_wr_production_environment",
                    "target_consolidation_path",
                    "high_value_route_environment",
                ],
                "risk_tags": [
                    "offense_projection_uncertainty",
                    "rookie_wr_ramp_risk",
                    "scheme_assumption_needs_verification",
                    "saints_2026_environment_variance",
                ],
                "context_tags": [
                    "pick_8_overall",
                    "saints_landing_spot",
                    "kellen_moore_pass_game_watch",
                    "non_generic_landing_spot_context",
                ],
                "model_impact": "upgrade_landing_context_review_priority_without_auto_adjusting_alpha",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity", "TIBER-Teamstate"],
                "confidence": "medium",
            }
        )

        olave_hierarchy_challenge = _base_candidate(entry, "olave_hierarchy_challenge_wr1_path", "player")
        olave_hierarchy_challenge.update(
            {
                "player_name": "Jordyn Tyson",
                "team": "Saints",
                "position": "WR",
                "candidate_theme": "olave_hierarchy_challenge_wr1_path",
                "claim_summary": (
                    "Tyson has a plausible long-term WR1 outcome path if his premium draft capital and "
                    "talent allow him to challenge Chris Olave in a thin Saints WR room."
                ),
                "positive_signal_tags": [
                    "wr1_outcome_path",
                    "olave_hierarchy_challenge",
                    "thin_wr_room_behind_olave",
                    "target_share_consolidation_watch",
                    "premium_rookie_role_path",
                ],
                "risk_tags": [
                    "olave_target_hierarchy",
                    "rookie_target_share_uncertainty",
                    "year1_role_uncertainty",
                    "bold_take_requires_verification",
                ],
                "context_tags": [
                    "olave_tyson_two_wr_consolidation_watch",
                    "saints_wr_room_watch",
                    "operator_bullish_thesis",
                ],
                "model_impact": "track_as_high_upside_hierarchy_challenge_not_base_projection",
                "downstream_repos": ["TIBER-Rookies", "Role-and-Opportunity"],
                "confidence": "medium",
            }
        )

        shough_fit_watch = _base_candidate(entry, "shough_tyson_qb_fit_watch", "player")
        shough_fit_watch.update(
            {
                "player_name": "Jordyn Tyson",
                "team": "Saints",
                "position": "WR",
                "candidate_theme": "shough_tyson_qb_fit_watch",
                "claim_summary": (
                    "The operator is above consensus on Tyler Shough and views Shough’s "
                    "accuracy/intermediate profile as a potential positive fit for Tyson, but the QB "
                    "stability assumption needs verification before promotion."
                ),
                "positive_signal_tags": [
                    "operator_above_consensus_qb_take",
                    "shough_accuracy_fit_watch",
                    "intermediate_passing_fit",
                    "moore_qb_development_environment",
                ],
                "risk_tags": [
                    "qb_stability_needs_verification",
                    "shough_market_disagreement",
                    "small_sample_qb_projection_risk",
                    "td_rate_growth_needed",
                ],
                "context_tags": [
                    "tyler_shough_fit_watch",
                    "saints_qb_context_watch",
                    "qb_wr_pairing_hypothesis",
                ],
                "model_impact": "flag_qb_environment_as_operator_watch_not_confirmed_context",
                "downstream_repos": ["TIBER-Rookies", "TIBER-Teamstate"],
                "confidence": "medium",
            }
        )
        return [kellen_moore_environment, olave_hierarchy_challenge, shough_fit_watch]

    return []


def build_candidates(entries: list[dict[str, Any]], allow_unmapped: bool = False) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    unmapped_entry_ids: list[str] = []
    for entry in entries:
        mapped_candidates = build_candidates_for_entry(entry)
        if not mapped_candidates:
            unmapped_entry_ids.append(entry["entry_id"])
            continue
        candidates.extend(mapped_candidates)

    if unmapped_entry_ids and not allow_unmapped:
        message = (
            "Unmapped operator journal entries detected. Add mapping rules or pass --allow-unmapped. "
            f"entry_ids={', '.join(unmapped_entry_ids)}"
        )
        raise UnmappedJournalEntriesError(message)

    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Duplicate candidate_id values detected; candidate IDs must be unique.")

    return sorted(candidates, key=lambda value: value["candidate_id"])


def write_candidates(input_path: Path, output_path: Path, allow_unmapped: bool = False) -> list[dict[str, Any]]:
    entries = json.loads(input_path.read_text(encoding="utf-8"))
    candidates = build_candidates(entries, allow_unmapped=allow_unmapped)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
    return candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Raw operator journal entries JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Candidate signal output JSON")
    parser.add_argument(
        "--allow-unmapped",
        action="store_true",
        help="Allow unmapped entries without failing the build (unmapped entries are skipped).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_candidates(args.input, args.output, allow_unmapped=args.allow_unmapped)


if __name__ == "__main__":
    main()
