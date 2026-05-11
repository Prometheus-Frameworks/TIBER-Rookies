#!/usr/bin/env python3
"""Inspect-only role/opportunity join for post-draft Rookie Alpha rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

TEAM_NORMALIZATION_MAP = {
    "49ers": "SF",
    "Browns": "CLE",
    "Titans": "TEN",
    "Saints": "NO",
    "Rams": "LAR",
    "Eagles": "PHI",
    "Jets": "NYJ",
    "Seahawks": "SEA",
    "Steelers": "PIT",
    "Dolphins": "MIA",
    "Bears": "CHI",
    "Panthers": "CAR",
    "Buccaneers": "TB",
    "Ravens": "BAL",
    "Giants": "NYG",
    "Commanders": "WAS",
    "Falcons": "ATL",
    "Jaguars": "JAX",
    "Texans": "HOU",
    "Patriots": "NE",
    "Cardinals": "ARI",
    "Chiefs": "KC",
}

ROLE_FIELDS = [
    "role_team_profile_found",
    "role_baseline_found",
    "role_opportunity_found",
    "candidate_roles",
    "matched_role_profiles",
    "matched_role_baselines",
    "role_context_tags",
    "role_risk_tags",
    "role_context_notes",
    "role_context_source_status",
    "combined_context_tags_with_role",
    "combined_risk_tags_with_role",
]

RISK_KEYWORDS = ("risk", "uncertainty", "caution", "volatility", "dependency", "competition")


def ordered_union(left: list[str], right: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in left + right:
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return merged


def normalize_team_code(team: str) -> str:
    value = (team or "").strip()
    if not value:
        return ""
    if value.upper() == "TBD":
        return "TBD"
    upper = value.upper()
    if upper in TEAM_NORMALIZATION_MAP.values():
        return upper
    return TEAM_NORMALIZATION_MAP.get(value, upper)


def _collect_tags(row: dict[str, Any]) -> set[str]:
    raw_tags = [str(tag) for tag in row.get("translator_tags", [])]
    combined_tags = [str(tag) for tag in row.get("combined_context_tags", [])]
    risks = [str(tag) for tag in row.get("remaining_risks", [])]
    return {tag.lower() for tag in raw_tags + combined_tags + risks}


def infer_candidate_roles(row: dict[str, Any]) -> list[str]:
    position = str(row.get("position", "")).upper()
    tags = _collect_tags(row)
    candidate_roles: list[str] = []

    def add(role: str) -> None:
        if role not in candidate_roles:
            candidate_roles.append(role)

    if position == "RB":
        if "round1_rb_capital" in tags or "lead-back" in tags or "lead_back" in tags:
            add("RB1")
        if "passing_down_role_path" in tags:
            add("passing_down_rb")
        if "injury_contingent_upside" in tags:
            add("injury_contingent_rb")
        if "shared_backfield_context_override" in tags:
            add("RB2_change_of_pace")

    if position == "WR":
        if "wr1_depth_chart_path" in tags or "top5_skill_capital" in tags or "top5_wr_opportunity_insulation" in tags:
            add("WR1")
        if "wr2_wr3_path" in tags or "target_room_competition_watch" in tags:
            add("WR2")
            add("WR3")
        if "slot_role_path" in tags:
            add("slot_wr")
        if "round3_wr_capital" in tags and ("role uncertainty" in " ".join(tags) or "year1_volume_uncertainty" in tags):
            add("rotational_wr")
        if "round2_wr_capital" in tags and "shanahan_role_translation_watch" in tags:
            add("WR2")
            add("rotational_wr")

    if position == "TE":
        if "round1_te_capital" in tags or "te1_path" in tags:
            add("TE1")
        if "move_te" in tags or "matchup_te" in tags:
            add("move_te")
        if "late_round_te_watch" in tags or "low_capital" in tags:
            add("blocking_rotational_te")
            add("TE2")

    if position == "QB":
        if "round1_qb_capital" in tags and ("delayed_start_insulation" in tags or "delayed path" in " ".join(tags)):
            add("QB_developmental")
        if "immediate_starter_context" in tags or "qb_starter_path" in tags:
            add("QB_starter")

    return candidate_roles


def _normalize_profile(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {"role": "", "context_tags": [], "risk_tags": [], "source_status": "operator_seeded"}

    role = str(entry.get("role") or entry.get("role_name") or entry.get("archetype") or "").strip()
    context_tags = [str(tag) for tag in (entry.get("context_tags") or entry.get("role_context_tags") or entry.get("tags") or [])]
    risk_tags = [str(tag) for tag in (entry.get("risk_tags") or entry.get("role_risk_tags") or [])]
    if not risk_tags:
        risk_tags = [tag for tag in context_tags if any(keyword in tag.lower() for keyword in RISK_KEYWORDS)]
    source_status = str(entry.get("source_status") or "operator_seeded")

    return {
        **entry,
        "role": role,
        "context_tags": context_tags,
        "risk_tags": risk_tags,
        "source_status": source_status,
    }


def load_team_role_profiles(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if isinstance(payload, dict):
        if isinstance(payload.get("teams"), dict):
            teams_obj = payload["teams"]
            iterable: list[tuple[str, Any]] = list(teams_obj.items())
        elif isinstance(payload.get("team_profiles"), list):
            iterable = []
            for row in payload["team_profiles"]:
                if isinstance(row, dict):
                    iterable.append((str(row.get("team") or row.get("team_code") or ""), row))
        elif isinstance(payload.get("rows"), list):
            iterable = []
            for row in payload["rows"]:
                if isinstance(row, dict):
                    iterable.append((str(row.get("team") or row.get("team_code") or ""), row))
        else:
            iterable = list(payload.items())
    elif isinstance(payload, list):
        iterable = []
        for row in payload:
            if isinstance(row, dict):
                iterable.append((str(row.get("team") or row.get("team_code") or ""), row))
    else:
        iterable = []

    by_team: dict[str, list[dict[str, Any]]] = {}
    for team_code, entry in iterable:
        normalized_team = normalize_team_code(team_code)
        if not normalized_team or normalized_team == "TBD":
            continue

        roles: list[Any]
        if isinstance(entry, dict):
            roles = entry.get("roles") or entry.get("profiles") or entry.get("team_role_profiles") or []
            if not roles and entry.get("role"):
                roles = [entry]
        elif isinstance(entry, list):
            roles = entry
        else:
            roles = []

        normalized_roles: list[dict[str, Any]] = []
        for role in roles:
            normalized_role = _normalize_profile(role)
            if normalized_role["role"]:
                normalized_roles.append(normalized_role)
        by_team[normalized_team] = normalized_roles
    return by_team


def load_role_baselines(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if isinstance(payload, dict) and "roles" in payload and isinstance(payload["roles"], list):
        rows = payload["roles"]
    elif isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = [{"role": key, **value} if isinstance(value, dict) else {"role": key} for key, value in payload.items()]
    else:
        rows = []

    baselines: dict[str, dict[str, Any]] = {}
    for row in rows:
        normalized = _normalize_profile(row)
        role = normalized["role"]
        if role:
            baselines[role] = normalized
    return baselines


def ensure_required_role_artifacts(
    team_role_profiles_path: Path,
    role_baselines_path: Path,
    *,
    allow_missing_role_artifacts: bool,
) -> None:
    if allow_missing_role_artifacts:
        return

    missing_paths = [path for path in (team_role_profiles_path, role_baselines_path) if not path.exists()]
    if not missing_paths:
        return

    missing_paths_formatted = ", ".join(str(path) for path in missing_paths)
    raise FileNotFoundError(
        "Missing required role artifact(s): "
        f"{missing_paths_formatted}. "
        "Suggested fix: git clone https://github.com/Prometheus-Frameworks/Role-and-opportunity-model.git "
        "or rerun with --allow-missing-role-artifacts for explicit partial builds."
    )


def enrich_rows(
    postdraft_rows: list[dict[str, Any]],
    team_role_profiles_by_team: dict[str, list[dict[str, Any]]],
    role_baselines_by_role: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []

    for row in postdraft_rows:
        team_code = normalize_team_code(str(row.get("team", "")))
        team_profiles = team_role_profiles_by_team.get(team_code)
        candidate_roles = infer_candidate_roles(row)

        matched_profiles = []
        if team_profiles:
            matched_profiles = [profile for profile in team_profiles if profile.get("role") in candidate_roles]
        matched_baselines = [role_baselines_by_role[role] for role in candidate_roles if role in role_baselines_by_role]
        role_team_profile_found = team_code not in {"", "TBD"} and team_profiles is not None
        role_baseline_found = bool(matched_baselines)
        role_opportunity_found = bool(matched_profiles) and role_baseline_found

        if team_code in {"", "TBD"}:
            notes = "team_unknown_or_tbd_for_role_profile_lookup"
        elif not role_team_profile_found:
            notes = f"team_role_profile_not_found:{team_code}"
        elif not candidate_roles:
            notes = f"no_heuristic_role_match:{team_code}"
        elif role_opportunity_found:
            notes = f"role_opportunity_joined:{team_code}:{'|'.join(candidate_roles)}"
        elif matched_profiles and not role_baseline_found:
            notes = f"team_role_match_found_baseline_missing:{team_code}"
        elif not matched_profiles and role_baseline_found:
            notes = f"baseline_only_role_context:{team_code}"
        else:
            notes = f"heuristic_roles_not_in_team_profiles:{team_code}"

        role_context_tags = ordered_union(
            [],
            [tag for profile in matched_profiles for tag in profile.get("context_tags", [])],
        )
        role_risk_tags = ordered_union(
            [],
            [tag for profile in matched_profiles for tag in profile.get("risk_tags", [])],
        )
        if matched_baselines:
            role_context_tags = ordered_union(
                role_context_tags,
                [tag for baseline in matched_baselines for tag in baseline.get("context_tags", [])],
            )
            role_risk_tags = ordered_union(
                role_risk_tags,
                [tag for baseline in matched_baselines for tag in baseline.get("risk_tags", [])],
            )

        base_context = list(row.get("combined_context_tags", row.get("translator_tags", [])))
        base_risks = list(row.get("combined_risk_tags", row.get("remaining_risks", [])))
        enriched_rows.append(
            {
                **row,
                "role_team_profile_found": role_team_profile_found,
                "role_baseline_found": role_baseline_found,
                "role_opportunity_found": role_opportunity_found,
                "candidate_roles": candidate_roles,
                "matched_role_profiles": matched_profiles,
                "matched_role_baselines": matched_baselines,
                "role_context_tags": role_context_tags,
                "role_risk_tags": role_risk_tags,
                "role_context_notes": notes,
                "role_context_source_status": "operator_seeded",
                "combined_context_tags_with_role": ordered_union(base_context, role_context_tags),
                "combined_risk_tags_with_role": ordered_union(base_risks, role_risk_tags),
            }
        )

    return enriched_rows


def write_outputs(rows: list[dict[str, Any]], output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "model": "rookie-alpha-postdraft-role-context-v0",
                "season": 2026,
                "doctrine": {
                    "post_draft_scores_unchanged": True,
                    "inspect_only": True,
                    "role_opportunity_join_only": True,
                },
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    if rows:
        fieldnames.extend(list(rows[0].keys()))
    for role_field in ROLE_FIELDS:
        if role_field not in fieldnames:
            fieldnames.append(role_field)

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            for key, value in list(csv_row.items()):
                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        csv_row[key] = json.dumps(value, separators=(",", ":"))
                    else:
                        csv_row[key] = "|".join(str(item) for item in value)
                elif isinstance(value, dict):
                    csv_row[key] = json.dumps(value, separators=(",", ":"))
            writer.writerow(csv_row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect-only role/opportunity join for post-draft alpha rows")
    parser.add_argument(
        "--postdraft-path",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json"),
    )
    parser.add_argument(
        "--team-role-profiles-path",
        type=Path,
        default=Path("../Role-and-opportunity-model/data/processed/2026_team_role_opportunity_profiles.json"),
    )
    parser.add_argument(
        "--role-baselines-path",
        type=Path,
        default=Path("../Role-and-opportunity-model/data/processed/2026_role_to_fantasy_baselines.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.csv"),
    )
    parser.add_argument(
        "--allow-missing-role-artifacts",
        action="store_true",
        help="Allow fallback empty role context when role artifacts are missing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    postdraft_payload = json.loads(args.postdraft_path.read_text(encoding="utf-8"))
    rows = postdraft_payload.get("rows", []) if isinstance(postdraft_payload, dict) else []
    ensure_required_role_artifacts(
        args.team_role_profiles_path,
        args.role_baselines_path,
        allow_missing_role_artifacts=args.allow_missing_role_artifacts,
    )
    team_profiles = load_team_role_profiles(args.team_role_profiles_path)
    baselines = load_role_baselines(args.role_baselines_path)

    enriched_rows = enrich_rows(rows, team_profiles, baselines)
    write_outputs(enriched_rows, args.output_json, args.output_csv)
    print(f"Wrote {len(enriched_rows)} rows to {args.output_json} and {args.output_csv}")


if __name__ == "__main__":
    main()
