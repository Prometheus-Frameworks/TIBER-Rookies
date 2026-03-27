#!/usr/bin/env python3
"""Standalone pre-draft Rookie Alpha pipeline (v0).

Reads artifact-only JSON inputs and writes promoted JSON + CSV outputs.
No DB writes. No runtime dependencies on TIBER-Fantasy services.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
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


@dataclass(frozen=True)
class MergeDiagnostics:
    duplicate_rows_skipped: int
    identity_conflicts_skipped: int
    excluded_for_missing_sources: dict[str, int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read input file {path}: {exc}") from exc


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


def coerce_float(
    value: Any,
    field_name: str,
    player_id: str,
    source_name: str,
    warned_invalid_values: set[tuple[str, str, str, str]] | None = None,
) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        warning_key = (field_name, repr(value), player_id, source_name)
        if warned_invalid_values is None or warning_key not in warned_invalid_values:
            logging.warning(
                "Skipping invalid %s value %r for player_id=%s in %s; field will be treated as missing.",
                field_name,
                value,
                player_id,
                source_name,
            )
            if warned_invalid_values is not None:
                warned_invalid_values.add(warning_key)
        return None


def normalize_row(
    row: dict[str, Any],
    source_name: str,
    row_number: int,
) -> tuple[str, str, str] | None:
    player_id_raw = row.get("player_id")
    if player_id_raw is None or str(player_id_raw).strip() == "":
        logging.warning(
            "Skipping row %s in %s because required field player_id is missing.",
            row_number,
            source_name,
        )
        return None
    player_id = str(player_id_raw)
    player_name = str(row.get("player_name", player_id))
    position = str(row.get("position", "UNK"))
    return (player_id, player_name, position)


def compute_ras_scores(combine_rows: list[dict[str, Any]]) -> dict[str, float]:
    by_position: dict[str, list[dict[str, Any]]] = {}
    warned_invalid_values: set[tuple[str, str, str, str]] = set()
    for idx, row in enumerate(combine_rows, start=1):
        normalized = normalize_row(row, "combine input", idx)
        if normalized is None:
            continue
        pid, _, position = normalized
        by_position.setdefault(position, []).append({"player_id": pid, **row})

    scores: dict[str, float] = {}
    for position, rows in by_position.items():
        forties = [
            value
            for r in rows
            for value in [
                coerce_float(r.get("forty"), "forty", str(r["player_id"]), "combine input", warned_invalid_values)
            ]
            if value is not None
        ]
        verticals = [
            value
            for r in rows
            for value in [
                coerce_float(r.get("vertical"), "vertical", str(r["player_id"]), "combine input", warned_invalid_values)
            ]
            if value is not None
        ]
        broads = [
            value
            for r in rows
            for value in [
                coerce_float(r.get("broad"), "broad", str(r["player_id"]), "combine input", warned_invalid_values)
            ]
            if value is not None
        ]
        heights = [
            value
            for r in rows
            for value in [
                coerce_float(r.get("height_in"), "height_in", str(r["player_id"]), "combine input", warned_invalid_values)
            ]
            if value is not None
        ]
        weights = [
            value
            for r in rows
            for value in [
                coerce_float(r.get("weight_lb"), "weight_lb", str(r["player_id"]), "combine input", warned_invalid_values)
            ]
            if value is not None
        ]

        forty_mu, forty_sd = safe_stats(forties)
        vert_mu, vert_sd = safe_stats(verticals)
        broad_mu, broad_sd = safe_stats(broads)
        h_mu, h_sd = safe_stats(heights)
        w_mu, w_sd = safe_stats(weights)

        for r in rows:
            components: list[tuple[float, float]] = []
            forty = coerce_float(r.get("forty"), "forty", str(r["player_id"]), "combine input", warned_invalid_values)
            vertical = coerce_float(
                r.get("vertical"),
                "vertical",
                str(r["player_id"]),
                "combine input",
                warned_invalid_values,
            )
            broad = coerce_float(r.get("broad"), "broad", str(r["player_id"]), "combine input", warned_invalid_values)
            height = coerce_float(
                r.get("height_in"),
                "height_in",
                str(r["player_id"]),
                "combine input",
                warned_invalid_values,
            )
            weight = coerce_float(
                r.get("weight_lb"),
                "weight_lb",
                str(r["player_id"]),
                "combine input",
                warned_invalid_values,
            )

            if forty is not None:
                z = (forty_mu - forty) / forty_sd  # lower is better
                components.append((0.35, z_to_score(z)))
            if vertical is not None:
                z = (vertical - vert_mu) / vert_sd
                components.append((0.25, z_to_score(z)))
            if broad is not None:
                z = (broad - broad_mu) / broad_sd
                components.append((0.25, z_to_score(z)))

            size_parts: list[float] = []
            if height is not None:
                size_parts.append(z_to_score((height - h_mu) / h_sd))
            if weight is not None:
                size_parts.append(z_to_score((weight - w_mu) / w_sd))
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
) -> tuple[list[PlayerInputs], MergeDiagnostics]:
    def build_identity_map(
        rows: list[dict[str, Any]],
        source_name: str,
    ) -> tuple[dict[str, tuple[str, str]], int, int]:
        identities: dict[str, tuple[str, str]] = {}
        duplicate_rows_skipped = 0
        identity_conflicts_skipped = 0
        for idx, row in enumerate(rows, start=1):
            normalized = normalize_row(row, source_name, idx)
            if normalized is None:
                continue
            player_id, player_name, position = normalized
            incoming = (player_name, position)
            if player_id in identities:
                if identities[player_id] == incoming:
                    duplicate_rows_skipped += 1
                    logging.warning(
                        "Skipping duplicate row for player_id=%s in %s (row %s).",
                        player_id,
                        source_name,
                        idx,
                    )
                else:
                    identity_conflicts_skipped += 1
                    logging.warning(
                        "Skipping conflicting identity for player_id=%s in %s (row %s): existing=%s incoming=%s.",
                        player_id,
                        source_name,
                        idx,
                        identities[player_id],
                        incoming,
                    )
                continue
            identities[player_id] = incoming
        return identities, duplicate_rows_skipped, identity_conflicts_skipped

    combine_identities, combine_duplicates, combine_conflicts = build_identity_map(combine_rows, "combine input")
    production_identities, production_duplicates, production_conflicts = build_identity_map(
        production_rows,
        "production input",
    )
    draft_identities, draft_duplicates, draft_conflicts = build_identity_map(draft_proxy_rows, "draft proxy input")

    conflicting_across_sources: set[str] = set()
    for player_id in sorted(set(combine_identities) | set(production_identities) | set(draft_identities)):
        seen = [m[player_id] for m in (combine_identities, production_identities, draft_identities) if player_id in m]
        if len(set(seen)) > 1:
            conflicting_across_sources.add(player_id)
            logging.warning(
                "Excluding player_id=%s due to cross-source identity mismatch: %s",
                player_id,
                seen,
            )

    ras_by_id = compute_ras_scores(combine_rows)
    warned_invalid_values: set[tuple[str, str, str, str]] = set()
    prod_by_id: dict[str, float] = {}
    for idx, row in enumerate(production_rows, start=1):
        normalized = normalize_row(row, "production input", idx)
        if normalized is None:
            continue
        player_id, _, _ = normalized
        value = coerce_float(
            row.get("production_score_0_100"),
            "production_score_0_100",
            player_id,
            "production input",
            warned_invalid_values,
        )
        if value is not None:
            prod_by_id[player_id] = value

    draft_by_id: dict[str, float] = {}
    for idx, row in enumerate(draft_proxy_rows, start=1):
        normalized = normalize_row(row, "draft proxy input", idx)
        if normalized is None:
            continue
        player_id, _, _ = normalized
        value = coerce_float(
            row.get("draft_capital_proxy_0_100"),
            "draft_capital_proxy_0_100",
            player_id,
            "draft proxy input",
            warned_invalid_values,
        )
        if value is not None:
            draft_by_id[player_id] = value

    common_ids = sorted(set(ras_by_id) & set(prod_by_id) & set(draft_by_id))
    missing_combine = (set(prod_by_id) | set(draft_by_id)) - set(ras_by_id)
    missing_production = (set(ras_by_id) | set(draft_by_id)) - set(prod_by_id)
    missing_draft = (set(ras_by_id) | set(prod_by_id)) - set(draft_by_id)
    excluded_ids = (set(ras_by_id) | set(prod_by_id) | set(draft_by_id)) - set(common_ids)

    players: list[PlayerInputs] = []
    for pid in common_ids:
        if pid in conflicting_across_sources:
            continue
        name, position = combine_identities.get(pid) or production_identities.get(pid) or draft_identities.get(pid) or (
            pid,
            "UNK",
        )
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
    diagnostics = MergeDiagnostics(
        duplicate_rows_skipped=combine_duplicates + production_duplicates + draft_duplicates,
        identity_conflicts_skipped=combine_conflicts + production_conflicts + draft_conflicts + len(conflicting_across_sources),
        excluded_for_missing_sources={
            "missing_combine": len(missing_combine),
            "missing_production": len(missing_production),
            "missing_draft_proxy": len(missing_draft),
            "total_excluded": len(excluded_ids | conflicting_across_sources),
        },
    )
    return players, diagnostics


def rookie_alpha_score(player: PlayerInputs) -> float:
    ras = player.ras_score_0_100 if player.ras_score_0_100 is not None else 50.0
    production = player.production_score_0_100 if player.production_score_0_100 is not None else 50.0
    draft = player.draft_capital_proxy_0_100 if player.draft_capital_proxy_0_100 is not None else 50.0
    return clamp_0_100((0.35 * ras) + (0.45 * production) + (0.20 * draft))


def write_outputs(
    players: list[PlayerInputs],
    merge_diagnostics: MergeDiagnostics,
    season: int,
    combine_path: Path,
    production_path: Path,
    draft_proxy_path: Path,
    output_json: Path,
    output_csv: Path,
    output_manifest: Path,
) -> None:
    generated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    run_id = f"rookie-alpha-{season}-{generated_at}"

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
            logging.warning(
                "Missing model inputs for player_id=%s (%s): %s. Defaulting missing inputs to 50.0.",
                p.player_id,
                p.player_name,
                ",".join(missing_components),
            )
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
        "run_id": run_id,
        "season": season,
        "coverage_summary": {
            "players_total": len(ranked),
            "players_with_any_missing_input": missing_any,
            "players_with_full_inputs": len(ranked) - missing_any,
            "input_alignment": {
                "duplicate_rows_skipped": merge_diagnostics.duplicate_rows_skipped,
                "identity_conflicts_skipped": merge_diagnostics.identity_conflicts_skipped,
                **merge_diagnostics.excluded_for_missing_sources,
            },
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
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

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

    input_files = [
        {
            "path": str(combine_path),
            "sha256": sha256_file(combine_path),
            "row_count": len(load_json(combine_path)),
        },
        {
            "path": str(production_path),
            "sha256": sha256_file(production_path),
            "row_count": len(load_json(production_path)),
        },
        {
            "path": str(draft_proxy_path),
            "sha256": sha256_file(draft_proxy_path),
            "row_count": len(load_json(draft_proxy_path)),
        },
    ]
    output_files = [
        {"path": str(output_json), "sha256": sha256_file(output_json)},
        {"path": str(output_csv), "sha256": sha256_file(output_csv)},
    ]
    manifest = {
        "season": season,
        "model_version": payload["model"]["model_version"],
        "generated_at": generated_at,
        "run_id": run_id,
        "input_files": input_files,
        "coverage_summary": payload["coverage_summary"],
        "output_files": output_files,
        "export_metadata": {},
    }
    exported_payload = load_json(output_json)
    manifest["export_metadata"] = {
        "season": exported_payload["season"],
        "model_version": exported_payload["model"]["model_version"],
        "generated_at": exported_payload["generated_at"],
        "run_id": exported_payload["run_id"],
        "coverage_summary": exported_payload["coverage_summary"],
        "source_files_used": exported_payload["source_files_used"],
    }
    expected_export_metadata = {
        "season": manifest["season"],
        "model_version": manifest["model_version"],
        "generated_at": manifest["generated_at"],
        "run_id": manifest["run_id"],
        "coverage_summary": manifest["coverage_summary"],
        "source_files_used": [entry["path"] for entry in manifest["input_files"]],
    }
    if manifest["export_metadata"] != expected_export_metadata:
        raise RuntimeError("Manifest export_metadata does not match top-level manifest metadata.")

    with output_manifest.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute standalone Rookie Alpha promoted export")
    parser.add_argument("--season", type=int, default=datetime.now(tz=timezone.utc).year)
    parser.add_argument(
        "--combine-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--production-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--draft-proxy-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    combine_input = args.combine_input or Path(f"data/raw/{args.season}_combine_results.json")
    production_input = args.production_input or Path(f"data/processed/{args.season}_college_production.json")
    draft_proxy_input = args.draft_proxy_input or Path(f"data/processed/{args.season}_draft_capital_proxy.json")
    output_json = args.output_json or Path(f"exports/promoted/rookie-alpha/{args.season}_rookie_alpha_predraft_v0.json")
    output_csv = args.output_csv or Path(f"exports/promoted/rookie-alpha/{args.season}_rookie_alpha_predraft_v0.csv")
    output_manifest = args.output_manifest or Path(f"exports/promoted/rookie-alpha/{args.season}_manifest.json")

    combine_rows = load_json(combine_input)
    production_rows = load_json(production_input)
    draft_rows = load_json(draft_proxy_input)
    if not isinstance(combine_rows, list):
        raise SystemExit(f"Expected list JSON in {combine_input}, got {type(combine_rows).__name__}")
    if not isinstance(production_rows, list):
        raise SystemExit(f"Expected list JSON in {production_input}, got {type(production_rows).__name__}")
    if not isinstance(draft_rows, list):
        raise SystemExit(f"Expected list JSON in {draft_proxy_input}, got {type(draft_rows).__name__}")
    players, merge_diagnostics = merge_inputs(combine_rows, production_rows, draft_rows)
    write_outputs(
        players=players,
        merge_diagnostics=merge_diagnostics,
        season=args.season,
        combine_path=combine_input,
        production_path=production_input,
        draft_proxy_path=draft_proxy_input,
        output_json=output_json,
        output_csv=output_csv,
        output_manifest=output_manifest,
    )


if __name__ == "__main__":
    main()
