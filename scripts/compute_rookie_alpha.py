#!/usr/bin/env python3
"""Standalone pre-draft Rookie Alpha pipeline (v0).

Reads artifact-only JSON inputs and writes promoted JSON + CSV outputs.
No DB writes. No runtime dependencies on TIBER-Fantasy services.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class PlayerInputs:
    player_id: str
    player_name: str
    position: str
    ras_score_0_100: float | None
    production_score_0_100: float | None
    draft_capital_proxy_0_100: float | None


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def z_to_score(z: float) -> float:
    # 50 at average, ~16.7 points per standard deviation.
    return clamp_0_100(50.0 + (z * 16.6667))


def safe_stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 1.0)
    if len(values) == 1:
        return (values[0], 1.0)
    sd = pstdev(values)
    return (mean(values), sd if sd > 1e-9 else 1.0)


def compute_ras_scores(combine_rows: list[dict[str, Any]]) -> dict[str, float]:
    by_position: dict[str, list[dict[str, Any]]] = {}
    for row in combine_rows:
        by_position.setdefault(str(row.get("position", "UNK")), []).append(row)

    scores: dict[str, float] = {}
    for position, rows in by_position.items():
        forties = [float(r["forty"]) for r in rows if r.get("forty") is not None]
        verticals = [float(r["vertical"]) for r in rows if r.get("vertical") is not None]
        broads = [float(r["broad"]) for r in rows if r.get("broad") is not None]
        heights = [float(r["height_in"]) for r in rows if r.get("height_in") is not None]
        weights = [float(r["weight_lb"]) for r in rows if r.get("weight_lb") is not None]

        forty_mu, forty_sd = safe_stats(forties)
        vert_mu, vert_sd = safe_stats(verticals)
        broad_mu, broad_sd = safe_stats(broads)
        h_mu, h_sd = safe_stats(heights)
        w_mu, w_sd = safe_stats(weights)

        for r in rows:
            components: list[tuple[float, float]] = []
            if r.get("forty") is not None:
                z = (forty_mu - float(r["forty"])) / forty_sd  # lower is better
                components.append((0.35, z_to_score(z)))
            if r.get("vertical") is not None:
                z = (float(r["vertical"]) - vert_mu) / vert_sd
                components.append((0.25, z_to_score(z)))
            if r.get("broad") is not None:
                z = (float(r["broad"]) - broad_mu) / broad_sd
                components.append((0.25, z_to_score(z)))

            size_parts: list[float] = []
            if r.get("height_in") is not None:
                size_parts.append(z_to_score((float(r["height_in"]) - h_mu) / h_sd))
            if r.get("weight_lb") is not None:
                size_parts.append(z_to_score((float(r["weight_lb"]) - w_mu) / w_sd))
            if size_parts:
                components.append((0.15, mean(size_parts)))

            if components:
                weight_sum = sum(weight for weight, _ in components)
                weighted = sum(weight * score for weight, score in components) / weight_sum
                scores[str(r["player_id"])] = clamp_0_100(weighted)
            else:
                scores[str(r["player_id"])] = 50.0

    return scores


def merge_inputs(
    combine_rows: list[dict[str, Any]],
    production_rows: list[dict[str, Any]],
    draft_proxy_rows: list[dict[str, Any]],
) -> list[PlayerInputs]:
    ras_by_id = compute_ras_scores(combine_rows)
    prod_by_id = {str(r["player_id"]): float(r["production_score_0_100"]) for r in production_rows}
    draft_by_id = {str(r["player_id"]): float(r["draft_capital_proxy_0_100"]) for r in draft_proxy_rows}

    names_positions: dict[str, tuple[str, str]] = {}
    for row in combine_rows:
        pid = str(row["player_id"])
        names_positions[pid] = (str(row.get("player_name", pid)), str(row.get("position", "UNK")))
    for row in production_rows:
        pid = str(row["player_id"])
        names_positions.setdefault(pid, (str(row.get("player_name", pid)), str(row.get("position", "UNK"))))
    for row in draft_proxy_rows:
        pid = str(row["player_id"])
        names_positions.setdefault(pid, (str(row.get("player_name", pid)), str(row.get("position", "UNK"))))

    all_ids = sorted(set(ras_by_id) | set(prod_by_id) | set(draft_by_id))
    players: list[PlayerInputs] = []
    for pid in all_ids:
        name, position = names_positions.get(pid, (pid, "UNK"))
        players.append(
            PlayerInputs(
                player_id=pid,
                player_name=name,
                position=position,
                ras_score_0_100=ras_by_id.get(pid),
                production_score_0_100=prod_by_id.get(pid),
                draft_capital_proxy_0_100=draft_by_id.get(pid),
            )
        )
    return players


def rookie_alpha_score(player: PlayerInputs) -> float:
    ras = player.ras_score_0_100 if player.ras_score_0_100 is not None else 50.0
    production = player.production_score_0_100 if player.production_score_0_100 is not None else 50.0
    draft = player.draft_capital_proxy_0_100 if player.draft_capital_proxy_0_100 is not None else 50.0
    return clamp_0_100((0.35 * ras) + (0.45 * production) + (0.20 * draft))


def write_outputs(
    players: list[PlayerInputs],
    season: int,
    combine_path: Path,
    production_path: Path,
    draft_proxy_path: Path,
    output_json: Path,
    output_csv: Path,
) -> None:
    generated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    ranked: list[dict[str, Any]] = []
    missing_any = 0
    for p in players:
        alpha = rookie_alpha_score(p)
        missing_components = [
            key
            for key, value in {
                "ras": p.ras_score_0_100,
                "production": p.production_score_0_100,
                "draft_capital_proxy": p.draft_capital_proxy_0_100,
            }.items()
            if value is None
        ]
        if missing_components:
            missing_any += 1
        ranked.append(
            {
                "player_id": p.player_id,
                "player_name": p.player_name,
                "position": p.position,
                "scores": {
                    "ras_0_100": round(p.ras_score_0_100 if p.ras_score_0_100 is not None else 50.0, 4),
                    "production_0_100": round(
                        p.production_score_0_100 if p.production_score_0_100 is not None else 50.0,
                        4,
                    ),
                    "draft_capital_proxy_0_100": round(
                        p.draft_capital_proxy_0_100 if p.draft_capital_proxy_0_100 is not None else 50.0,
                        4,
                    ),
                    "rookie_alpha_0_100": round(alpha, 4),
                },
                "model_inputs_missing": missing_components,
            }
        )

    ranked.sort(key=lambda r: r["scores"]["rookie_alpha_0_100"], reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rookie_alpha_rank"] = i

    payload = {
        "model": {
            "name": "tiber-rookie-alpha",
            "stage": "pre-draft",
            "label": "pre-draft v0",
            "model_version": "rookie-alpha-predraft-v0.1.0",
            "formula": {
                "ras_weight": 0.35,
                "production_weight": 0.45,
                "draft_capital_proxy_weight": 0.20,
                "age_at_entry_supported": False,
            },
        },
        "generated_at": generated_at,
        "season": season,
        "coverage_summary": {
            "players_total": len(ranked),
            "players_with_any_missing_input": missing_any,
            "players_with_full_inputs": len(ranked) - missing_any,
        },
        "source_files_used": [
            str(combine_path),
            str(production_path),
            str(draft_proxy_path),
        ],
        "players": ranked,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rookie_alpha_rank",
                "player_id",
                "player_name",
                "position",
                "ras_0_100",
                "production_0_100",
                "draft_capital_proxy_0_100",
                "rookie_alpha_0_100",
                "model_inputs_missing",
            ],
        )
        writer.writeheader()
        for row in ranked:
            writer.writerow(
                {
                    "rookie_alpha_rank": row["rookie_alpha_rank"],
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "position": row["position"],
                    "ras_0_100": row["scores"]["ras_0_100"],
                    "production_0_100": row["scores"]["production_0_100"],
                    "draft_capital_proxy_0_100": row["scores"]["draft_capital_proxy_0_100"],
                    "rookie_alpha_0_100": row["scores"]["rookie_alpha_0_100"],
                    "model_inputs_missing": ",".join(row["model_inputs_missing"]),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute standalone Rookie Alpha promoted export")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--combine-input",
        type=Path,
        default=Path("data/raw/2026_combine_results.json"),
    )
    parser.add_argument(
        "--production-input",
        type=Path,
        default=Path("data/processed/2026_college_production.json"),
    )
    parser.add_argument(
        "--draft-proxy-input",
        type=Path,
        default=Path("data/processed/2026_draft_capital_proxy.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    combine_rows = load_json(args.combine_input)
    production_rows = load_json(args.production_input)
    draft_rows = load_json(args.draft_proxy_input)
    players = merge_inputs(combine_rows, production_rows, draft_rows)
    write_outputs(
        players=players,
        season=args.season,
        combine_path=args.combine_input,
        production_path=args.production_input,
        draft_proxy_path=args.draft_proxy_input,
        output_json=args.output_json,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    main()
