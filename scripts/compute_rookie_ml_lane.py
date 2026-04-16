#!/usr/bin/env python3
"""Parallel ML evaluation lane for rookie hit probability (phase 1).

This script intentionally does NOT replace deterministic rookie-alpha scoring.
It builds a labeled historical table, runs interpretable baseline models with
class-year-aware splits, compares against simple non-ML baselines, and exports
held-out scored probabilities.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEATURE_COLUMNS = [
    "draft_capital_proxy_0_100",
    "age_at_draft",
    "breakout_age",
    "production_0_100",
    "athleticism_0_100",
    "size_context_0_100",
    "speed_proxy_0_100",
    "early_declare_flag",
    "deterministic_grade_0_100",
]

FULL_MODEL_FEATURE_COLUMNS = [col for col in FEATURE_COLUMNS if col != "deterministic_grade_0_100"]

BASELINE_MODEL_FEATURES = {
    "draft_capital_only": ["draft_capital_proxy_0_100"],
    "draft_capital_plus_age": ["draft_capital_proxy_0_100", "age_at_draft"],
    "draft_capital_plus_production": ["draft_capital_proxy_0_100", "production_0_100"],
    "deterministic_grade_only": ["deterministic_grade_0_100"],
    "logistic_full": FULL_MODEL_FEATURE_COLUMNS,
}

TRACKED_POSITIONS = ["WR", "RB", "TE", "QB"]
WEAK_COVERAGE_THRESHOLD = 0.60
SPARSE_POSITION_THRESHOLD = 8
MIN_PRIOR_CLASS_COUNT = 2
STRONG_LABEL_SOURCES = {
    "best_season_positional_finish_by_year_3",
    "best_season_positional_finish",
    "top_finish_band",
}
WEAK_LABEL_SOURCES = {
    "years_1_to_3_summary",
    "career_outcome_label",
}
STRONG_FEATURE_COMPLETENESS_THRESHOLD = 0.70


@dataclass
class SplitBundle:
    train: list[dict[str, Any]]
    validation: list[dict[str, Any]]
    test: list[dict[str, Any]]
    years: dict[str, list[int]]


class SimpleLogisticRegression:
    def __init__(self, learning_rate: float = 0.1, epochs: int = 600, l2: float = 0.02) -> None:
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2 = l2
        self.weights: list[float] = []
        self.bias = 0.0

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        z = math.exp(x)
        return z / (1.0 + z)

    def fit(self, x_rows: list[list[float]], y: list[int]) -> None:
        if not x_rows:
            raise ValueError("Cannot fit logistic model on empty dataset")
        n_features = len(x_rows[0])
        self.weights = [0.0] * n_features
        self.bias = 0.0
        n = len(x_rows)
        for _ in range(self.epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for row, target in zip(x_rows, y):
                logit = sum(w * v for w, v in zip(self.weights, row)) + self.bias
                pred = self._sigmoid(logit)
                err = pred - target
                for j in range(n_features):
                    grad_w[j] += err * row[j]
                grad_b += err
            for j in range(n_features):
                grad_w[j] = grad_w[j] / n + self.l2 * self.weights[j]
                self.weights[j] -= self.learning_rate * grad_w[j]
            self.bias -= self.learning_rate * (grad_b / n)

    def predict_proba(self, x_rows: list[list[float]]) -> list[float]:
        if not self.weights:
            raise ValueError("Model not fit")
        probs: list[float] = []
        for row in x_rows:
            logit = sum(w * v for w, v in zip(self.weights, row)) + self.bias
            probs.append(self._sigmoid(logit))
        return probs


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_top_finish_rank(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    text = str(value).upper().strip()
    if not text:
        return None

    tier_match = re.fullmatch(r"(QB|RB|WR|TE)\s*[-_ ]?(\d{1,2})", text)
    if tier_match:
        tier_or_rank = int(tier_match.group(2))
        # Tier-style labels (WR1/WR2/WR3, etc.) are groupings of 12 players.
        # For larger values (e.g. QB15), treat as direct positional rank.
        return tier_or_rank * 12 if tier_or_rank <= 6 else tier_or_rank

    for pattern in (r"TOP\s*[-_ ]?(\d+)", r"RANK\s*[:=]?\s*(\d+)"):
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))

    pos_rank_match = re.search(r"(?:QB|RB|WR|TE)\s*[-_ ]?(\d+)", text)
    if pos_rank_match:
        return int(pos_rank_match.group(1))
    return None


def _extract_hit_label(row: dict[str, Any]) -> int | None:
    position = str(row.get("position") or "").upper().strip()
    threshold = 24 if position in {"WR", "RB"} else 12 if position == "TE" else 15 if position == "QB" else None
    if threshold is None:
        return None

    direct_finish = _parse_top_finish_rank(row.get("best_season_positional_finish"))
    if direct_finish is None:
        direct_finish = _parse_top_finish_rank(row.get("top_finish_band"))
    if direct_finish is None:
        direct_finish = _parse_top_finish_rank(row.get("years_1_to_3_summary"))

    if direct_finish is not None:
        return int(direct_finish <= threshold)

    label_text = str(row.get("career_outcome_label") or "").lower()
    if "hit" in label_text:
        return 1
    if "miss" in label_text:
        return 0
    return None


def _derive_outcome_bucket(hit_label: int | None, best_finish: int | None, threshold: int | None) -> str | None:
    if hit_label is None:
        return None
    if hit_label == 1:
        if best_finish is not None and threshold is not None and best_finish <= max(1, threshold // 2):
            return "high_impact_hit"
        return "hit"
    return "miss"


def build_canonical_historical_outcomes(outcomes_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical_rows: list[dict[str, Any]] = []
    for row in outcomes_rows:
        position = str(row.get("position") or "").upper().strip()
        threshold = 24 if position in {"WR", "RB"} else 12 if position == "TE" else 15 if position == "QB" else None
        label_sources_used: list[str] = []
        best_finish = None
        for field in (
            "best_season_positional_finish_by_year_3",
            "best_season_positional_finish",
            "top_finish_band",
            "years_1_to_3_summary",
        ):
            parsed = _parse_top_finish_rank(row.get(field))
            if parsed is not None:
                best_finish = parsed
                label_sources_used.append(field)
                break

        hit_label = None
        if best_finish is not None and threshold is not None:
            hit_label = int(best_finish <= threshold)
        else:
            label_text = str(row.get("career_outcome_label") or "").lower()
            if "hit" in label_text:
                hit_label = 1
                label_sources_used.append("career_outcome_label")
            elif "miss" in label_text:
                hit_label = 0
                label_sources_used.append("career_outcome_label")

        best_ppr_points = _to_float(row.get("best_ppr_points_by_year_3"))
        if best_ppr_points is None:
            best_ppr_points = _to_float(row.get("best_season_fantasy_ppg"))

        primary_source = label_sources_used[0] if label_sources_used else None
        canonical_rows.append(
            {
                "player_id": str(row.get("player_id") or ""),
                "player_name": row.get("player_name"),
                "position": position or row.get("position"),
                "draft_year": int(row.get("draft_year") or 0),
                "best_season_positional_finish_by_year_3": best_finish,
                "best_ppr_points_by_year_3": best_ppr_points,
                "fantasy_relevant_hit_by_rule": hit_label,
                "outcome_bucket": _derive_outcome_bucket(hit_label, best_finish, threshold),
                "label_source_fields_used": label_sources_used,
                "label_source_primary": primary_source,
                "label_is_weak_fallback": primary_source in WEAK_LABEL_SOURCES if primary_source else False,
                "canonical_label_built": hit_label is not None,
                "target_threshold_rule": "WR/RB<=24, TE<=12, QB<=15 by year 3" if threshold is not None else None,
                "source_snapshot": {
                    "top_finish_band": row.get("top_finish_band"),
                    "years_1_to_3_summary": row.get("years_1_to_3_summary"),
                    "career_outcome_label": row.get("career_outcome_label"),
                },
            }
        )
    return canonical_rows


def _load_deterministic_scores(rookie_alpha_dir: Path) -> dict[tuple[str, int], float]:
    scores: dict[tuple[str, int], float] = {}
    if not rookie_alpha_dir.exists():
        return scores
    for path in rookie_alpha_dir.glob("*_rookie_alpha_predraft_v0.json"):
        payload = load_json(path)
        season = int(payload.get("season") or 0)
        for player in payload.get("players", []):
            pid = str(player.get("player_id") or "")
            score = _to_float((player.get("scores") or {}).get("rookie_alpha_0_100"))
            if pid and score is not None and season > 0:
                scores[(pid, season)] = score
    return scores


def build_labeled_rows(
    features_rows: list[dict[str, Any]],
    canonical_outcomes_rows: list[dict[str, Any]],
    deterministic_scores: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    outcomes_by_player = {str(row.get("player_id")): row for row in canonical_outcomes_rows}
    labeled: list[dict[str, Any]] = []
    for feat in features_rows:
        player_id = str(feat.get("player_id") or "")
        if not player_id:
            continue
        outcome = outcomes_by_player.get(player_id)
        if not outcome:
            continue
        label = outcome.get("fantasy_relevant_hit_by_rule")
        if label is None:
            continue

        draft_year = int(feat.get("draft_year") or outcome.get("draft_year") or 0)
        athletic_source = "athleticism_0_100"
        athletic = _to_float(feat.get("athleticism_0_100"))
        if athletic is None:
            athletic = _to_float(feat.get("ras_0_100"))
            if athletic is not None:
                athletic_source = "ras_0_100"
        speed_source = "speed_proxy_0_100"
        speed = _to_float(feat.get("speed_proxy_0_100"))
        if speed is None:
            speed = athletic
            if speed is not None:
                speed_source = "athleticism_fallback"

        deterministic = deterministic_scores.get((player_id, draft_year))
        row = {
            "player_id": player_id,
            "player_name": feat.get("player_name"),
            "position": feat.get("position"),
            "draft_year": draft_year,
            "hit_label": label,
            "draft_capital_proxy_0_100": _to_float(feat.get("draft_capital_proxy_0_100")),
            "age_at_draft": _to_float(feat.get("age_at_draft")),
            "breakout_age": _to_float(feat.get("breakout_age")),
            "production_0_100": _to_float(feat.get("production_0_100")),
            "athleticism_0_100": athletic,
            "size_context_0_100": _to_float(feat.get("size_context_0_100")),
            "speed_proxy_0_100": speed,
            "early_declare_flag": 1.0 if feat.get("early_declare_flag") else 0.0 if feat.get("early_declare_flag") is not None else None,
            "deterministic_grade_0_100": deterministic,
            "target_threshold": "WR/RB<=24, TE<=12, QB<=15 by year 3",
            "outcome_bucket": outcome.get("outcome_bucket"),
            "label_source_fields_used": outcome.get("label_source_fields_used", []),
            "label_source_primary": outcome.get("label_source_primary"),
            "label_is_weak_fallback": bool(outcome.get("label_is_weak_fallback")),
            "athleticism_source": athletic_source if athletic is not None else None,
            "speed_proxy_source": speed_source if speed is not None else None,
        }
        labeled.append(row)
    return labeled


def time_split(rows: list[dict[str, Any]], holdout_year: int | None = None) -> SplitBundle:
    years = sorted({int(r["draft_year"]) for r in rows})
    if not years:
        return SplitBundle([], [], [], {"train": [], "validation": [], "test": []})

    test_year = holdout_year if holdout_year is not None else years[-1]
    if test_year not in years:
        raise SystemExit(f"Holdout year {test_year} not found in labeled dataset years={years}")

    prior = [y for y in years if y < test_year]
    if not prior:
        raise SystemExit(
            "Time-aware split requires at least one prior class before holdout test year."
        )

    validation_year = prior[-1]
    train_years = [y for y in years if y < validation_year]
    if not train_years:
        raise SystemExit(
            "Time-aware split requires at least two prior classes (train + validation) before holdout test year."
        )

    train = [r for r in rows if int(r["draft_year"]) in train_years]
    validation = [r for r in rows if int(r["draft_year"]) == validation_year]
    test = [r for r in rows if int(r["draft_year"]) == test_year]

    return SplitBundle(
        train,
        validation,
        test,
        {"train": train_years, "validation": [validation_year], "test": [test_year]},
    )


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def fit_imputer_scaler(train_rows: list[dict[str, Any]], feature_names: list[str]) -> tuple[dict[str, float], dict[str, tuple[float, float]]]:
    medians: dict[str, float] = {}
    scale: dict[str, tuple[float, float]] = {}
    for name in feature_names:
        vals = [_to_float(r.get(name)) for r in train_rows]
        clean = [v for v in vals if v is not None]
        med = _median(clean) if clean else 0.0
        mean = sum(clean) / len(clean) if clean else med
        std = (sum((v - mean) ** 2 for v in clean) / len(clean)) ** 0.5 if clean else 1.0
        if std <= 1e-9:
            std = 1.0
        medians[name] = med
        scale[name] = (mean, std)
    return medians, scale


def transform_rows(rows: list[dict[str, Any]], feature_names: list[str], medians: dict[str, float], scale: dict[str, tuple[float, float]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in rows:
        vec: list[float] = []
        for name in feature_names:
            val = _to_float(row.get(name))
            if val is None:
                val = medians[name]
            mean, std = scale[name]
            vec.append((val - mean) / std)
        matrix.append(vec)
    return matrix


def roc_auc(y_true: list[int], y_score: list[float]) -> float | None:
    pos = [s for y, s in zip(y_true, y_score) if y == 1]
    neg = [s for y, s in zip(y_true, y_score) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif math.isclose(p, n):
                wins += 0.5
    return wins / (len(pos) * len(neg))


def pr_auc(y_true: list[int], y_score: list[float]) -> float | None:
    total_pos = sum(y_true)
    if total_pos == 0:
        return None
    order = sorted(range(len(y_score)), key=lambda i: y_score[i], reverse=True)
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for idx in order:
        if y_true[idx] == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / total_pos
        precision = tp / (tp + fp)
        area += (recall - prev_recall) * precision
        prev_recall = recall
    return area


def log_loss(y_true: list[int], y_prob: list[float]) -> float:
    eps = 1e-12
    total = 0.0
    for y, p in zip(y_true, y_prob):
        p2 = min(1 - eps, max(eps, p))
        total += -(y * math.log(p2) + (1 - y) * math.log(1 - p2))
    return total / len(y_true) if y_true else float("nan")


def calibration_error(y_true: list[int], y_prob: list[float], bins: int = 10) -> float | None:
    if not y_true:
        return None
    sized = [[] for _ in range(bins)]
    for y, p in zip(y_true, y_prob):
        idx = min(bins - 1, int(p * bins))
        sized[idx].append((y, p))
    err = 0.0
    count = 0
    for bucket in sized:
        if not bucket:
            continue
        obs = sum(y for y, _ in bucket) / len(bucket)
        pred = sum(p for _, p in bucket) / len(bucket)
        err += abs(obs - pred) * len(bucket)
        count += len(bucket)
    return err / count if count else None


def precision_at_k(y_true: list[int], y_prob: list[float], k: int = 5) -> float | None:
    if not y_true:
        return None
    k = min(k, len(y_true))
    top = sorted(range(len(y_prob)), key=lambda i: y_prob[i], reverse=True)[:k]
    hits = sum(y_true[i] for i in top)
    return hits / k if k > 0 else None


def evaluate(y_true: list[int], y_prob: list[float], k: int = 5) -> dict[str, float | None]:
    return {
        "roc_auc": roc_auc(y_true, y_prob),
        "pr_auc": pr_auc(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob) if y_true else None,
        "calibration_mae": calibration_error(y_true, y_prob),
        "precision_at_k": precision_at_k(y_true, y_prob, k=k),
        "n": len(y_true),
        "positives": sum(y_true),
    }


def _rate(num: int, denom: int) -> float | None:
    if denom <= 0:
        return None
    return round(num / denom, 6)


def _safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _counts_by_keys(
    rows: list[dict[str, Any]],
    key_names: list[str],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = "|".join(str(row.get(name) or "") for name in key_names)
        out[key] = out.get(key, 0) + 1
    return out


def build_dataset_diagnostics(labeled: list[dict[str, Any]], split: SplitBundle) -> dict[str, Any]:
    by_position = _counts_by_keys(labeled, ["position"])
    by_year = _counts_by_keys(labeled, ["draft_year"])
    by_position_year = _counts_by_keys(labeled, ["position", "draft_year"])
    train_by_position = _counts_by_keys(split.train, ["position"])
    val_by_position = _counts_by_keys(split.validation, ["position"])
    test_by_position = _counts_by_keys(split.test, ["position"])

    def _hit_rate(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        hits = sum(int(r["hit_label"]) for r in rows)
        return _rate(hits, len(rows))

    hit_by_position: dict[str, float | None] = {}
    for position in sorted({str(r.get("position") or "") for r in labeled}):
        subset = [r for r in labeled if str(r.get("position") or "") == position]
        hit_by_position[position] = _hit_rate(subset)

    hit_by_year: dict[str, float | None] = {}
    for year in sorted({int(r.get("draft_year") or 0) for r in labeled}):
        subset = [r for r in labeled if int(r.get("draft_year") or 0) == year]
        hit_by_year[str(year)] = _hit_rate(subset)

    return {
        "total_labeled_rows": len(labeled),
        "labeled_row_count_by_position": by_position,
        "labeled_row_count_by_draft_year": by_year,
        "labeled_row_count_by_position_draft_year": by_position_year,
        "split_row_counts": {
            "train": len(split.train),
            "validation": len(split.validation),
            "test": len(split.test),
        },
        "split_row_counts_by_position": {
            "train": train_by_position,
            "validation": val_by_position,
            "test": test_by_position,
        },
        "target_hit_rate_overall": _hit_rate(labeled),
        "target_hit_rate_by_position": hit_by_position,
        "target_hit_rate_by_draft_year": hit_by_year,
    }


def build_feature_coverage_report(rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    positions = sorted({str(r.get("position") or "") for r in rows})
    years = sorted({int(r.get("draft_year") or 0) for r in rows})
    report: dict[str, Any] = {
        "total_rows": len(rows),
        "weak_coverage_threshold": WEAK_COVERAGE_THRESHOLD,
        "features": {},
    }
    for feature in feature_names:
        non_null = sum(1 for r in rows if _to_float(r.get(feature)) is not None)
        null = len(rows) - non_null
        by_position: dict[str, float | None] = {}
        by_year: dict[str, float | None] = {}
        for pos in positions:
            subset = [r for r in rows if str(r.get("position") or "") == pos]
            present = sum(1 for r in subset if _to_float(r.get(feature)) is not None)
            by_position[pos] = _rate(present, len(subset))
        for year in years:
            subset = [r for r in rows if int(r.get("draft_year") or 0) == year]
            present = sum(1 for r in subset if _to_float(r.get(feature)) is not None)
            by_year[str(year)] = _rate(present, len(subset))
        report["features"][feature] = {
            "non_null_count": non_null,
            "null_count": null,
            "coverage_pct_overall": _rate(non_null, len(rows)),
            "coverage_pct_by_position": by_position,
            "coverage_pct_by_draft_year": by_year,
        }
    return report


def build_historical_label_provenance_report(canonical_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_position_source: dict[str, int] = {}
    weak_fallback_rows = 0
    missing = 0
    for row in canonical_rows:
        source = str(row.get("label_source_primary") or "unresolved")
        position = str(row.get("position") or "UNK")
        by_source[source] = by_source.get(source, 0) + 1
        key = f"{position}|{source}"
        by_position_source[key] = by_position_source.get(key, 0) + 1
        if row.get("label_is_weak_fallback"):
            weak_fallback_rows += 1
        if not row.get("canonical_label_built"):
            missing += 1
    return {
        "total_rows": len(canonical_rows),
        "row_count_by_source_field": by_source,
        "row_count_by_position_and_source_field": by_position_source,
        "weak_fallback_label_rows": weak_fallback_rows,
        "rows_without_canonical_label": missing,
    }


def build_historical_feature_consistency_report(rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    positions = sorted({str(r.get("position") or "") for r in rows})
    years = sorted({int(r.get("draft_year") or 0) for r in rows})
    report: dict[str, Any] = {"total_rows": len(rows), "features": {}}
    source_map = {
        "athleticism_0_100": "athleticism_source",
        "speed_proxy_0_100": "speed_proxy_source",
    }
    for feature in feature_names:
        source_field = source_map.get(feature)
        fallback_count = 0
        primary_count = 0
        if source_field:
            for row in rows:
                source = str(row.get(source_field) or "")
                if not source:
                    continue
                if source in {feature, "speed_proxy_0_100"}:
                    primary_count += 1
                else:
                    fallback_count += 1
        detail = build_feature_coverage_report(rows, [feature])["features"][feature]
        by_position_year: dict[str, float | None] = {}
        for position in positions:
            for year in years:
                subset = [r for r in rows if str(r.get("position") or "") == position and int(r.get("draft_year") or 0) == year]
                present = sum(1 for r in subset if _to_float(r.get(feature)) is not None)
                by_position_year[f"{position}|{year}"] = _rate(present, len(subset))
        report["features"][feature] = {
            **detail,
            "coverage_pct_by_position_draft_year": by_position_year,
            "value_source_field": source_field,
            "primary_source_count": primary_count,
            "fallback_source_count": fallback_count,
        }
    return report


def build_historical_class_coverage_report(
    features_rows: list[dict[str, Any]],
    labeled_rows: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    split: SplitBundle,
) -> dict[str, Any]:
    usable_by_year = _counts_by_keys(labeled_rows, ["draft_year"])
    usable_by_position = _counts_by_keys(labeled_rows, ["position"])
    usable_by_year_position = _counts_by_keys(labeled_rows, ["draft_year", "position"])

    complete_by_year: dict[str, int] = {}
    for row in labeled_rows:
        year = str(int(row.get("draft_year") or 0))
        complete = sum(1 for f in FEATURE_COLUMNS if _to_float(row.get(f)) is not None)
        if complete >= 6:
            complete_by_year[year] = complete_by_year.get(year, 0) + 1

    canonical_by_year: dict[str, int] = {}
    for row in canonical_rows:
        if row.get("canonical_label_built"):
            year = str(int(row.get("draft_year") or 0))
            canonical_by_year[year] = canonical_by_year.get(year, 0) + 1

    surviving = {
        "train": _counts_by_keys(split.train, ["draft_year", "position"]),
        "validation": _counts_by_keys(split.validation, ["draft_year", "position"]),
        "test": _counts_by_keys(split.test, ["draft_year", "position"]),
    }
    return {
        "input_feature_rows": len(features_rows),
        "total_usable_historical_rows": len(labeled_rows),
        "usable_rows_by_draft_year": usable_by_year,
        "usable_rows_by_position": usable_by_position,
        "usable_rows_by_draft_year_position": usable_by_year_position,
        "rows_with_strong_feature_completeness_by_draft_year": complete_by_year,
        "rows_with_canonical_outcomes_by_draft_year": canonical_by_year,
        "rows_surviving_ml_lane_filtering_by_stage_draft_year_position": surviving,
    }


def build_historical_position_slices_report(
    labeled_rows: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical_by_player = {str(r.get("player_id") or ""): r for r in canonical_rows}
    positions_report: dict[str, Any] = {}
    for position in TRACKED_POSITIONS:
        subset = [r for r in labeled_rows if str(r.get("position") or "").upper() == position]
        canonical_count = sum(1 for r in subset if canonical_by_player.get(str(r.get("player_id") or ""), {}).get("canonical_label_built"))
        strong_feature = 0
        for row in subset:
            non_null = sum(1 for feature in FEATURE_COLUMNS if _to_float(row.get(feature)) is not None)
            if _rate(non_null, len(FEATURE_COLUMNS)) is not None and float(non_null / len(FEATURE_COLUMNS)) >= STRONG_FEATURE_COMPLETENESS_THRESHOLD:
                strong_feature += 1
        hit_rate = _rate(sum(int(r.get("hit_label") or 0) for r in subset), len(subset))
        years = sorted({int(r.get("draft_year") or 0) for r in subset})
        warnings: list[str] = []
        if len(subset) < SPARSE_POSITION_THRESHOLD:
            warnings.append(f"Thin position coverage: {position} has only {len(subset)} labeled rows.")
        if canonical_count < len(subset):
            warnings.append(f"{position} has {len(subset) - canonical_count} rows without canonical outcomes.")
        if subset and (strong_feature / len(subset)) < STRONG_FEATURE_COMPLETENESS_THRESHOLD:
            warnings.append(f"{position} has weak feature completeness (<{int(STRONG_FEATURE_COMPLETENESS_THRESHOLD * 100)}%).")
        positions_report[position] = {
            "labeled_rows": len(subset),
            "rows_with_canonical_outcomes": canonical_count,
            "rows_with_strong_feature_completeness": strong_feature,
            "hit_rate": hit_rate,
            "draft_years_represented": years,
            "weak_spots": warnings,
            "ready_for_standalone_modeling": len(warnings) == 0,
        }
    return {"positions": positions_report}


def build_data_warnings(
    split: SplitBundle,
    coverage: dict[str, Any],
    diagnostics: dict[str, Any],
    provenance_report: dict[str, Any] | None = None,
    position_slices_report: dict[str, Any] | None = None,
) -> list[str]:
    warnings: list[str] = []
    if len(split.years.get("train", [])) < MIN_PRIOR_CLASS_COUNT:
        warnings.append("Insufficient prior draft classes for robust pre-holdout training signal.")

    for position in TRACKED_POSITIONS:
        n = int(diagnostics["split_row_counts_by_position"]["test"].get(position, 0))
        if n < SPARSE_POSITION_THRESHOLD:
            warnings.append(f"Test slice for {position} is sparse (n={n}); position metrics may be unstable.")

    weak_features = []
    for feature, detail in coverage.get("features", {}).items():
        overall = detail.get("coverage_pct_overall")
        if overall is not None and float(overall) < WEAK_COVERAGE_THRESHOLD:
            weak_features.append(feature)
    if weak_features:
        warnings.append(
            "Weak feature coverage below threshold "
            f"({int(WEAK_COVERAGE_THRESHOLD * 100)}%): {', '.join(sorted(weak_features))}."
        )

    det_cov = coverage.get("features", {}).get("deterministic_grade_0_100", {}).get("coverage_pct_overall")
    if det_cov is not None and float(det_cov) < WEAK_COVERAGE_THRESHOLD:
        warnings.append("Deterministic grade is unavailable for many historical rows.")

    if provenance_report:
        weak = int(provenance_report.get("weak_fallback_label_rows") or 0)
        total = int(provenance_report.get("total_rows") or 0)
        if total > 0 and (weak / total) > 0.20:
            warnings.append(
                f"Label provenance leans on weak fallback sources for {weak}/{total} rows."
            )
        unresolved = int(provenance_report.get("rows_without_canonical_label") or 0)
        if unresolved > 0:
            warnings.append(f"{unresolved} historical rows could not receive canonical labels.")

    if position_slices_report:
        for position, detail in (position_slices_report.get("positions") or {}).items():
            if not detail.get("ready_for_standalone_modeling"):
                warnings.append(
                    f"Position {position} not ready for standalone modeling: {'; '.join(detail.get('weak_spots') or [])}"
                )

    return warnings


def evaluate_by_position(rows: list[dict[str, Any]], probs: list[float]) -> dict[str, Any]:
    slices: dict[str, Any] = {}
    for position in TRACKED_POSITIONS:
        idxs = [i for i, r in enumerate(rows) if str(r.get("position") or "").upper() == position]
        y = [int(rows[i]["hit_label"]) for i in idxs]
        p = [probs[i] for i in idxs]
        slices[position] = evaluate(y, p) if idxs else {"roc_auc": None, "pr_auc": None, "log_loss": None, "calibration_mae": None, "precision_at_k": None, "n": 0, "positives": 0}
    return slices


def build_feature_importance_report(
    model_name: str,
    feature_names: list[str],
    coefficients: dict[str, float],
) -> dict[str, Any]:
    rows = []
    max_abs = max((abs(float(coefficients.get(name, 0.0))) for name in feature_names), default=0.0)
    for name in feature_names:
        coef = float(coefficients.get(name, 0.0))
        abs_coef = abs(coef)
        rows.append(
            {
                "feature": name,
                "coefficient": round(coef, 6),
                "sign": "positive" if coef > 0 else "negative" if coef < 0 else "neutral",
                "abs_magnitude": round(abs_coef, 6),
                "normalized_importance": round((abs_coef / max_abs), 6) if max_abs > 0 else 0.0,
            }
        )
    rows.sort(key=lambda r: r["abs_magnitude"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["abs_magnitude_rank"] = i
    return {"model_name": model_name, "features_ranked": rows}


def build_missingness_summary(coverage: dict[str, Any]) -> dict[str, Any]:
    weak_features: list[dict[str, Any]] = []
    weak_by_position: dict[str, list[str]] = {}
    weak_by_year: dict[str, list[str]] = {}
    for feature, detail in coverage.get("features", {}).items():
        overall = detail.get("coverage_pct_overall")
        if overall is not None and float(overall) < WEAK_COVERAGE_THRESHOLD:
            weak_features.append({"feature": feature, "coverage_pct_overall": overall})

        for position, pct in detail.get("coverage_pct_by_position", {}).items():
            if pct is not None and float(pct) < WEAK_COVERAGE_THRESHOLD:
                weak_by_position.setdefault(position, []).append(feature)
        for year, pct in detail.get("coverage_pct_by_draft_year", {}).items():
            if pct is not None and float(pct) < WEAK_COVERAGE_THRESHOLD:
                weak_by_year.setdefault(year, []).append(feature)

    warnings = [
        f"{item['feature']} coverage below {int(WEAK_COVERAGE_THRESHOLD * 100)}% (overall={item['coverage_pct_overall']})"
        for item in sorted(weak_features, key=lambda x: x["coverage_pct_overall"])
    ]
    return {
        "coverage_threshold": WEAK_COVERAGE_THRESHOLD,
        "weak_features_overall": weak_features,
        "thin_positions": {k: sorted(v) for k, v in weak_by_position.items()},
        "thin_draft_years": {k: sorted(v) for k, v in weak_by_year.items()},
        "warnings": warnings,
    }


def deterministic_non_ml_baseline(rows: list[dict[str, Any]], key: str) -> list[float]:
    probs = []
    for row in rows:
        v = _to_float(row.get(key))
        probs.append((v / 100.0) if v is not None else 0.5)
    return probs


def _attach_predictions(rows: list[dict[str, Any]], probs: list[float], model_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row, p in zip(rows, probs):
        confidence = abs(p - 0.5) * 2.0
        out.append(
            {
                "player_id": row["player_id"],
                "player_name": row.get("player_name"),
                "position": row.get("position"),
                "draft_year": row.get("draft_year"),
                "hit_probability": round(p, 6),
                "miss_probability": round(1.0 - p, 6),
                "model_confidence": round(confidence, 6),
                "model_name": model_name,
                "deterministic_grade_0_100": row.get("deterministic_grade_0_100"),
                "deterministic_disagreement": None
                if row.get("deterministic_grade_0_100") is None
                else round(p - (float(row["deterministic_grade_0_100"]) / 100.0), 6),
                "hit_label": row.get("hit_label"),
            }
        )
    return out


def run_model(
    model_name: str,
    feature_names: list[str],
    split: SplitBundle,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[float]]:
    train = split.train
    validation = split.validation
    test = split.test
    y_train = [int(r["hit_label"]) for r in train]
    y_val = [int(r["hit_label"]) for r in validation]
    y_test = [int(r["hit_label"]) for r in test]

    medians, scale = fit_imputer_scaler(train, feature_names)
    x_train = transform_rows(train, feature_names, medians, scale)
    x_val = transform_rows(validation, feature_names, medians, scale)
    x_test = transform_rows(test, feature_names, medians, scale)

    model = SimpleLogisticRegression()
    model.fit(x_train, y_train)
    val_probs = model.predict_proba(x_val)
    test_probs = model.predict_proba(x_test)

    metrics = {
        "validation": evaluate(y_val, val_probs),
        "test": evaluate(y_test, test_probs),
        "test_by_position": evaluate_by_position(test, test_probs),
        "features": feature_names,
        "coefficients": {name: round(w, 6) for name, w in zip(feature_names, model.weights)},
        "bias": round(model.bias, 6),
    }

    scored = _attach_predictions(test, test_probs, model_name)
    return metrics, scored, test_probs


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for row in rows for k in row.keys()}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and evaluate parallel ML rookie lane.")
    parser.add_argument("--historical-features", default="data/historical/historical_prospect_features.sample.json")
    parser.add_argument("--historical-outcomes", default="data/historical/historical_player_outcomes.ml_sample.json")
    parser.add_argument("--rookie-alpha-dir", default="exports/promoted/rookie-alpha")
    parser.add_argument("--holdout-year", type=int, default=None)
    parser.add_argument("--output-dir", default="exports/promoted/rookie-ml-lane")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    features = load_json(Path(args.historical_features))
    outcomes = load_json(Path(args.historical_outcomes))
    deterministic_scores = _load_deterministic_scores(Path(args.rookie_alpha_dir))
    canonical_outcomes = build_canonical_historical_outcomes(outcomes)

    labeled = build_labeled_rows(features, canonical_outcomes, deterministic_scores)
    if not labeled:
        raise SystemExit("No labeled rows available. Populate historical outcomes with finish info/labels first.")

    split = time_split(labeled, holdout_year=args.holdout_year)
    if not split.test:
        raise SystemExit("No test rows available for selected holdout year.")

    models_report: dict[str, Any] = {}
    heldout_scores_by_model: dict[str, list[dict[str, Any]]] = {}

    for model_name, feature_names in BASELINE_MODEL_FEATURES.items():
        usable = [name for name in feature_names if any(_to_float(r.get(name)) is not None for r in split.train)]
        if not usable:
            continue
        metrics, scored, _ = run_model(model_name, usable, split)
        models_report[model_name] = metrics
        heldout_scores_by_model[model_name] = scored

    non_ml = {
        "draft_capital_rescaled": deterministic_non_ml_baseline(split.test, "draft_capital_proxy_0_100"),
        "deterministic_grade_rescaled": deterministic_non_ml_baseline(split.test, "deterministic_grade_0_100"),
    }
    y_test = [int(r["hit_label"]) for r in split.test]
    non_ml_report = {
        name: {
            "test": evaluate(y_test, probs),
            "test_by_position": evaluate_by_position(split.test, probs),
        }
        for name, probs in non_ml.items()
    }

    diagnostics = build_dataset_diagnostics(labeled, split)
    coverage = build_feature_coverage_report(labeled, FEATURE_COLUMNS)
    provenance_report = build_historical_label_provenance_report(canonical_outcomes)
    feature_consistency_report = build_historical_feature_consistency_report(labeled, FEATURE_COLUMNS)
    class_coverage_report = build_historical_class_coverage_report(features, labeled, canonical_outcomes, split)
    position_slices_report = build_historical_position_slices_report(labeled, canonical_outcomes)
    warnings = build_data_warnings(split, coverage, diagnostics, provenance_report, position_slices_report)
    missingness_summary = build_missingness_summary(coverage)

    final_scores = heldout_scores_by_model.get("logistic_full") or next(iter(heldout_scores_by_model.values()))
    full_model_metrics = models_report.get("logistic_full", {}).get("test", {})
    baseline_delta = {}
    for baseline in ("draft_capital_only", "draft_capital_plus_production", "deterministic_grade_only"):
        if baseline in models_report:
            baseline_pr_auc = models_report[baseline]["test"]["pr_auc"]
            full_pr_auc = full_model_metrics.get("pr_auc")
            baseline_delta[baseline] = {
                "test_pr_auc_delta_vs_logistic_full": _safe_round(
                    None if baseline_pr_auc is None or full_pr_auc is None else float(full_pr_auc) - float(baseline_pr_auc)
                )
            }

    feature_importance_report = (
        build_feature_importance_report(
            "logistic_full",
            models_report["logistic_full"]["features"],
            models_report["logistic_full"]["coefficients"],
        )
        if "logistic_full" in models_report
        else {"model_name": None, "features_ranked": []}
    )

    output_dir = Path(args.output_dir)
    write_json(output_dir / "historical_outcomes_canonical.json", canonical_outcomes)
    write_json(output_dir / "historical_label_provenance_report.json", provenance_report)
    write_json(output_dir / "historical_feature_consistency_report.json", feature_consistency_report)
    write_json(output_dir / "historical_class_coverage_report.json", class_coverage_report)
    write_json(output_dir / "historical_position_slices_report.json", position_slices_report)
    write_json(output_dir / "historical_labeled_dataset.json", labeled)
    write_csv(output_dir / "historical_labeled_dataset.csv", labeled)
    write_json(output_dir / "feature_table.json", [{k: row.get(k) for k in ["player_id", "draft_year", "position", *FEATURE_COLUMNS, "hit_label"]} for row in labeled])

    write_json(output_dir / "dataset_diagnostics.json", diagnostics)
    write_json(output_dir / "feature_coverage_report.json", coverage)
    write_json(output_dir / "feature_importance_report.json", feature_importance_report)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "parallel_ml_evaluation_only",
        "split_strategy": "time_aware_by_draft_class",
        "split_years": split.years,
        "n_labeled_rows": len(labeled),
        "n_test_rows": len(split.test),
        "dataset_warnings": warnings,
        "historical_truth_summary": {
            "weak_label_fallback_rows": provenance_report["weak_fallback_label_rows"],
            "rows_without_canonical_label": provenance_report["rows_without_canonical_label"],
            "positions_not_ready_for_standalone_modeling": [
                position
                for position, detail in position_slices_report["positions"].items()
                if not detail.get("ready_for_standalone_modeling")
            ],
        },
        "missingness_summary": missingness_summary,
        "ml_models": models_report,
        "non_ml_baselines": non_ml_report,
        "draft_capital_dominance_check": baseline_delta,
        "winning_model_by_test_pr_auc": max(
            models_report.keys(),
            key=lambda name: (models_report[name]["test"]["pr_auc"] if models_report[name]["test"]["pr_auc"] is not None else -1),
        )
        if models_report
        else None,
    }

    write_json(output_dir / "evaluation_report.json", report)
    write_json(output_dir / "heldout_probabilities.json", final_scores)
    write_csv(output_dir / "heldout_probabilities.csv", final_scores)

    print(f"Wrote ML lane outputs to {output_dir}")


if __name__ == "__main__":
    main()
