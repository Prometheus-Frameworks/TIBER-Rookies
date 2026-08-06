#!/usr/bin/env python3
"""Build the 2023 drafted skill-class coverage census (issue #283, Phase 1).

Audit-only artifact producer. Reads the nflverse draft_picks public release
(cached under data/external/nflverse/) plus existing in-repo artifacts, and
classifies every 2023 drafted QB/RB/WR/TE by current TIBER-Rookies coverage:

- governed_profile_available: player has a standalone row in the promoted
  2023 rookie-alpha export (renderable as a card by the standalone lab).
- partial_reconstructable: no standalone card, but in-repo governed sources
  cover athletic testing AND at least one college production season.
- reference_only: appears only in reference/comparison/outcome rows.
- missing: appears in no in-repo artifact.

This script does not modify any promoted artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DRAFT_PICKS_CACHE = Path("data/external/nflverse/draft_picks.csv")
DRAFT_PICKS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv.gz"
)

ALPHA_EXPORT_2023 = Path("exports/promoted/rookie-alpha/2023_rookie_alpha_predraft_v0.json")
SPORQ_HISTORICAL = Path("data/historical/sporq_historical.json")
WR_REF_POP_DIR = Path("data/historical/wr_reference_populations")
TE_REF_POP_DIR = Path("data/historical/te_reference_populations")
OUTCOMES_EXPORT = Path("exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.json")

OUTPUT_DIR = Path("data/historical/reconstruction_2023")
OUTPUT_JSON = OUTPUT_DIR / "2023_skill_class_census_v0.json"
OUTPUT_CSV = OUTPUT_DIR / "2023_skill_class_census_v0.csv"

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}

# Deterministic name overrides between nflverse pfr_player_name and repo
# display names (per docs/draft-results-provenance.md: explicit, never fuzzy).
NAME_OVERRIDES = {
    # nflverse normalized -> repo normalized
    "nathaniel dell": "tank dell",
}


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace(".", " ").replace("'", "")
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", text)
    text = re.sub(r"[^a-z ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug_id(position: str, name: str) -> str:
    return f"{position.lower()}-{normalize_name(name).replace(' ', '-')}"


def load_draft_class() -> list[dict]:
    if not DRAFT_PICKS_CACHE.exists():
        raise SystemExit(
            f"Missing {DRAFT_PICKS_CACHE}. Download {DRAFT_PICKS_URL} and "
            "extract it there first (data/external/ is gitignored cache space)."
        )
    with DRAFT_PICKS_CACHE.open() as fh:
        rows = [
            row
            for row in csv.DictReader(fh)
            if row["season"] == "2023" and row["position"] in SKILL_POSITIONS
        ]
    rows.sort(key=lambda r: int(r["pick"]))
    return rows


def collect_membership() -> dict[str, dict]:
    """Map normalized player name -> in-repo artifact evidence."""
    evidence: dict[str, dict] = {}

    def add(name: str, artifact: str, kind: str, extra: dict | None = None) -> None:
        key = normalize_name(name)
        entry = evidence.setdefault(
            key,
            {"artifacts": [], "alpha_export_row": None, "sporq_tested": False,
             "governed_production_seasons": [], "outcome_rows": 0},
        )
        entry["artifacts"].append(artifact)
        if extra:
            entry.update(extra)
        if kind == "sporq_tested":
            entry["sporq_tested"] = True

    alpha = json.loads(ALPHA_EXPORT_2023.read_text())
    for player in alpha["players"]:
        add(
            player["player_name"],
            str(ALPHA_EXPORT_2023),
            "alpha",
            {"alpha_export_row": player["player_id"]},
        )

    sporq = json.loads(SPORQ_HISTORICAL.read_text())
    for row in sporq["players"]:
        if row.get("year") == 2023:
            kind = "sporq_tested" if row.get("sporq") is not None else "sporq_dnq"
            add(row["name"], str(SPORQ_HISTORICAL), kind)

    for pop_dir in (WR_REF_POP_DIR, TE_REF_POP_DIR):
        for path in sorted(pop_dir.glob("*_population.json")):
            for row in json.loads(path.read_text()):
                key = normalize_name(row["player_name"])
                add(row["player_name"], str(path), "ref_pop")
                evidence[key]["governed_production_seasons"].append(row["source_season"])

    for row in json.loads(OUTCOMES_EXPORT.read_text()):
        if row.get("draft_year") == 2023:
            key = normalize_name(row["player_name"])
            # outcomes use abbreviated names (e.g. "P.Nacua"); match on
            # first-initial + last name against nothing here — instead store
            # under gsis id for join by draft slot in classify().
            evidence.setdefault(
                f"gsis:{row['player_id']}",
                {"artifacts": [], "alpha_export_row": None, "sporq_tested": False,
                 "governed_production_seasons": [], "outcome_rows": 0},
            )
            evidence[f"gsis:{row['player_id']}"]["artifacts"].append(str(OUTCOMES_EXPORT))
            evidence[f"gsis:{row['player_id']}"]["outcome_rows"] += 1

    return evidence


def classify(pick: dict, evidence: dict[str, dict]) -> dict:
    name = pick["pfr_player_name"]
    key = NAME_OVERRIDES.get(normalize_name(name), normalize_name(name))
    ev = evidence.get(key, {
        "artifacts": [], "alpha_export_row": None, "sporq_tested": False,
        "governed_production_seasons": [], "outcome_rows": 0,
    })
    gsis_ev = evidence.get(f"gsis:{pick['gsis_id']}") if pick.get("gsis_id") else None
    artifacts = list(dict.fromkeys(ev["artifacts"] + (gsis_ev["artifacts"] if gsis_ev else [])))
    outcome_rows = gsis_ev["outcome_rows"] if gsis_ev else 0

    has_card = ev["alpha_export_row"] is not None
    has_athletic = ev["sporq_tested"]
    production_seasons = sorted(set(ev["governed_production_seasons"]))

    gaps: list[str] = []
    if has_card:
        classification = "governed_profile_available"
        gaps.append(
            "2023 alpha inputs are manual_historical_seed rows: draft-capital "
            "proxy holds actual draft outcome and several evidence strings "
            "contain post-draft NFL information (hindsight contamination)."
        )
        gaps.append("No verifiable per-stat source lineage on production/context seeds.")
    elif has_athletic and production_seasons:
        classification = "partial_reconstructable"
        gaps.append("No standalone card or alpha-export row.")
        if 2022 not in production_seasons:
            gaps.append(
                "Final college season (2022) absent from governed reference "
                "populations (populations end at 2021)."
            )
    elif artifacts:
        classification = "reference_only"
        gaps.append("Appears only in reference/outcome rows; no model-input coverage.")
    else:
        classification = "missing"
        gaps.append("No in-repo artifact contains this player.")

    if pick["position"] == "QB" and not has_card:
        gaps.append("SPORQ table has no QB coverage; no in-repo QB athletic layer.")
    if pick["position"] == "TE" and not has_card and not production_seasons:
        gaps.append("TE reference population files exist but are empty.")

    return {
        "canonical_player_id": ev["alpha_export_row"] or slug_id(pick["position"], name),
        "canonical_id_status": "existing_repo_id" if has_card else "proposed_slug",
        "gsis_id": pick.get("gsis_id") or None,
        "player_name": name,
        "position": pick["position"],
        "college": pick["college"],
        "draft_round": int(pick["round"]),
        "overall_pick": int(pick["pick"]),
        "draft_team": pick["team"],
        "coverage_classification": classification,
        "artifacts_containing_player": artifacts,
        "standalone_card_renderable": has_card,
        "source_lineage_complete": False if has_card else bool(production_seasons),
        "historical_model_inputs_reproducible": (
            "yes_with_hindsight_contamination" if has_card
            else ("partial" if (has_athletic or production_seasons) else "no")
        ),
        "governed_production_seasons": production_seasons,
        "nfl_outcome_rows_available": outcome_rows,
        "gaps_blocking_reconstruction": gaps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    picks = load_draft_class()
    evidence = collect_membership()
    census = [classify(pick, evidence) for pick in picks]

    counts: dict[str, int] = {}
    for row in census:
        counts[row["coverage_classification"]] = counts.get(row["coverage_classification"], 0) + 1

    payload = {
        "artifact": "2023_skill_class_census_v0",
        "issue": "Prometheus-Frameworks/TIBER-Rookies#283",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "draft_class": 2023,
        "positions": sorted(SKILL_POSITIONS),
        "census_source": {
            "source_name": "nflverse draft_picks public release",
            "source_url": DRAFT_PICKS_URL,
            "note": (
                "Draft facts here are audit census data, not the governed "
                "TIBER-Data nfl_draft_results artifact (issue #242 still open). "
                "This census is not a model input and must not be promoted."
            ),
        },
        "classification_rules": {
            "governed_profile_available": "standalone row in promoted 2023 rookie-alpha export",
            "partial_reconstructable": "in-repo athletic testing + >=1 governed college production season",
            "reference_only": "appears only in reference/comparison/outcome rows",
            "missing": "no in-repo artifact contains the player",
        },
        "summary": {
            "players_total": len(census),
            "by_position": {
                pos: sum(1 for r in census if r["position"] == pos)
                for pos in ("QB", "RB", "WR", "TE")
            },
            "by_classification": counts,
        },
        "players": census,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")

    csv_fields = [
        "canonical_player_id", "gsis_id", "player_name", "position", "college",
        "draft_round", "overall_pick", "draft_team", "coverage_classification",
        "standalone_card_renderable", "source_lineage_complete",
        "historical_model_inputs_reproducible", "nfl_outcome_rows_available",
        "gaps_blocking_reconstruction",
    ]
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields)
        writer.writeheader()
        for row in census:
            flat = {k: row[k] for k in csv_fields if k != "gaps_blocking_reconstruction"}
            flat["gaps_blocking_reconstruction"] = " | ".join(row["gaps_blocking_reconstruction"])
            writer.writerow(flat)

    print(f"Census rows: {len(census)}")
    print(f"By classification: {counts}")
    print(f"Wrote {OUTPUT_JSON} and {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
