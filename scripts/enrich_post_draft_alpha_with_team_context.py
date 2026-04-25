#!/usr/bin/env python3
"""Join Teamstate landing-context tags onto post-draft Rookie Alpha rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROW_FIELDS = [
    "player_id",
    "player_name",
    "position",
    "pre_draft_alpha",
    "post_draft_alpha",
    "post_draft_delta",
    "draft_round",
    "draft_pick",
    "team",
    "talent_confirmation_signal",
    "opportunity_insulation_signal",
    "short_term_fantasy_runway",
    "source_profile",
    "source_status",
    "delta_reason_codes",
    "translator_tags",
    "remaining_risks",
    "team_context_found",
    "team_context_tags",
    "positive_team_context_tags",
    "risk_team_context_tags",
    "team_context_notes",
    "team_context_source_status",
    "combined_context_tags",
    "combined_risk_tags",
]

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
}

RISK_KEYWORDS = ("risk", "uncertainty", "caution", "volatility", "dependency", "competition")


def ordered_union(left: list[str], right: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for tag in left + right:
        if tag in seen:
            continue
        merged.append(tag)
        seen.add(tag)
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


def classify_risk_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    risks: list[str] = []
    for tag in tags:
        if any(keyword in tag for keyword in RISK_KEYWORDS):
            risks.append(tag)
        else:
            positive.append(tag)
    return positive, risks


def extract_team_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, list):
        tags = [str(tag) for tag in entry]
        positive, risks = classify_risk_tags(tags)
        return {
            "team_context_tags": tags,
            "positive_team_context_tags": positive,
            "risk_team_context_tags": risks,
            "team_context_source_status": "operator_seeded",
        }

    if isinstance(entry, dict):
        tags = [str(tag) for tag in (entry.get("team_context_tags") or entry.get("context_tags") or entry.get("tags") or [])]
        positive_tags = [str(tag) for tag in (entry.get("positive_team_context_tags") or entry.get("positive_tags") or [])]
        risk_tags = [str(tag) for tag in (entry.get("risk_team_context_tags") or entry.get("risk_tags") or [])]

        if not positive_tags and not risk_tags:
            positive_tags, risk_tags = classify_risk_tags(tags)

        return {
            "team_context_tags": tags,
            "positive_team_context_tags": positive_tags,
            "risk_team_context_tags": risk_tags,
            "team_context_source_status": entry.get("source_status", "operator_seeded"),
        }

    return {
        "team_context_tags": [],
        "positive_team_context_tags": [],
        "risk_team_context_tags": [],
        "team_context_source_status": "operator_seeded",
    }


def load_team_context(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "teams" in payload:
        teams = payload["teams"]
    else:
        teams = payload

    context_by_team: dict[str, dict[str, Any]] = {}
    if isinstance(teams, dict):
        iterable = teams.items()
    elif isinstance(teams, list):
        iterable = []
        for row in teams:
            if not isinstance(row, dict):
                continue
            team_code = row.get("team") or row.get("team_code") or row.get("code")
            if team_code:
                iterable.append((team_code, row))
    else:
        iterable = []

    for team_code, entry in iterable:
        normalized = normalize_team_code(str(team_code))
        if not normalized or normalized == "TBD":
            continue
        context_by_team[normalized] = extract_team_entry(entry)
    return context_by_team


def enrich_rows(
    postdraft_rows: list[dict[str, Any]],
    team_context_by_team: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in postdraft_rows:
        team_code = normalize_team_code(str(row.get("team", "")))
        team_context = team_context_by_team.get(team_code)

        team_context_found = team_code not in {"", "TBD"} and team_context is not None
        if team_context_found:
            context_tags = team_context["team_context_tags"]
            positive_context_tags = team_context["positive_team_context_tags"]
            risk_context_tags = team_context["risk_team_context_tags"]
            team_context_notes = f"team_context_joined:{team_code}"
            team_context_source_status = team_context.get("team_context_source_status", "operator_seeded")
        else:
            context_tags = []
            positive_context_tags = []
            risk_context_tags = []
            team_context_notes = "team_context_not_found_or_team_tbd"
            team_context_source_status = "operator_seeded"

        translator_tags = list(row.get("translator_tags", []))
        remaining_risks = list(row.get("remaining_risks", []))

        enriched_row = {
            **row,
            "team_context_found": team_context_found,
            "team_context_tags": context_tags,
            "positive_team_context_tags": positive_context_tags,
            "risk_team_context_tags": risk_context_tags,
            "team_context_notes": team_context_notes,
            "team_context_source_status": team_context_source_status,
            "combined_context_tags": ordered_union(translator_tags, context_tags),
            "combined_risk_tags": ordered_union(remaining_risks, risk_context_tags),
        }
        enriched.append(enriched_row)
    return enriched


def write_outputs(rows: list[dict[str, Any]], output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "rookie-alpha-postdraft-team-context-v0",
        "season": 2026,
        "doctrine": {
            "post_draft_scores_unchanged": True,
            "teamstate_context_join_only": True,
            "inspect_only": True,
        },
        "rows": rows,
    }
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = {
                **row,
                "delta_reason_codes": "|".join(row.get("delta_reason_codes", [])),
                "translator_tags": "|".join(row.get("translator_tags", [])),
                "remaining_risks": "|".join(row.get("remaining_risks", [])),
                "team_context_tags": "|".join(row.get("team_context_tags", [])),
                "positive_team_context_tags": "|".join(row.get("positive_team_context_tags", [])),
                "risk_team_context_tags": "|".join(row.get("risk_team_context_tags", [])),
                "combined_context_tags": "|".join(row.get("combined_context_tags", [])),
                "combined_risk_tags": "|".join(row.get("combined_risk_tags", [])),
            }
            writer.writerow(csv_row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich post-draft Rookie Alpha with Teamstate landing context")
    parser.add_argument(
        "--postdraft-path",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json"),
    )
    parser.add_argument(
        "--teamstate-context-path",
        type=Path,
        default=Path("../TIBER-Teamstate/data/processed/2026_team_landing_context_tags.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    postdraft_payload = json.loads(args.postdraft_path.read_text(encoding="utf-8"))
    team_context_by_team = load_team_context(args.teamstate_context_path)
    rows = enrich_rows(postdraft_payload.get("rows", []), team_context_by_team)
    write_outputs(rows, args.output_json, args.output_csv)
    print(f"Wrote {len(rows)} rows to {args.output_json} and {args.output_csv}")


if __name__ == "__main__":
    main()
