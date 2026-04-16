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

BASELINE_MODEL_FEATURES = {
    "draft_capital_only": ["draft_capital_proxy_0_100"],
    "draft_capital_plus_age": ["draft_capital_proxy_0_100", "age_at_draft"],
    "draft_capital_plus_production": ["draft_capital_proxy_0_100", "production_0_100"],
    "deterministic_grade_only": ["deterministic_grade_0_100"],
    "logistic_full": FEATURE_COLUMNS,
}


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
    for pattern in (r"TOP\s*[-_ ]?(\d+)", r"(?:QB|RB|WR|TE)\s*[-_ ]?(\d+)", r"RANK\s*[:=]?\s*(\d+)"):
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    if text.endswith("1") and text[:2] in {"QB", "RB", "WR", "TE"}:
        return 12
    if text.endswith("2") and text[:2] in {"WR", "RB"}:
        return 24
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
    outcomes_rows: list[dict[str, Any]],
    deterministic_scores: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    outcomes_by_player = {str(row.get("player_id")): row for row in outcomes_rows}
    labeled: list[dict[str, Any]] = []
    for feat in features_rows:
        player_id = str(feat.get("player_id") or "")
        if not player_id:
            continue
        outcome = outcomes_by_player.get(player_id)
        if not outcome:
            continue
        label = _extract_hit_label(outcome)
        if label is None:
            continue

        draft_year = int(feat.get("draft_year") or outcome.get("draft_year") or 0)
        athletic = _to_float(feat.get("athleticism_0_100"))
        if athletic is None:
            athletic = _to_float(feat.get("ras_0_100"))
        speed = _to_float(feat.get("speed_proxy_0_100"))
        if speed is None:
            speed = athletic

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
    validation_year = prior[-1] if prior else test_year
    train_years = [y for y in years if y < validation_year]

    train = [r for r in rows if int(r["draft_year"]) in train_years]
    validation = [r for r in rows if int(r["draft_year"]) == validation_year]
    test = [r for r in rows if int(r["draft_year"]) == test_year]

    if not train and validation:
        train = validation
    if not validation:
        validation = train

    return SplitBundle(train, validation, test, {"train": train_years, "validation": [validation_year], "test": [test_year]})


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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
        "features": feature_names,
        "coefficients": {name: round(w, 6) for name, w in zip(feature_names, model.weights)},
        "bias": round(model.bias, 6),
    }

    scored = _attach_predictions(test, test_probs, model_name)
    return metrics, scored


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

    labeled = build_labeled_rows(features, outcomes, deterministic_scores)
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
        metrics, scored = run_model(model_name, usable, split)
        models_report[model_name] = metrics
        heldout_scores_by_model[model_name] = scored

    non_ml = {
        "draft_capital_rescaled": deterministic_non_ml_baseline(split.test, "draft_capital_proxy_0_100"),
        "deterministic_grade_rescaled": deterministic_non_ml_baseline(split.test, "deterministic_grade_0_100"),
    }
    y_test = [int(r["hit_label"]) for r in split.test]
    non_ml_report = {name: evaluate(y_test, probs) for name, probs in non_ml.items()}

    final_scores = heldout_scores_by_model.get("logistic_full") or next(iter(heldout_scores_by_model.values()))

    output_dir = Path(args.output_dir)
    write_json(output_dir / "historical_labeled_dataset.json", labeled)
    write_csv(output_dir / "historical_labeled_dataset.csv", labeled)
    write_json(output_dir / "feature_table.json", [{k: row.get(k) for k in ["player_id", "draft_year", "position", *FEATURE_COLUMNS, "hit_label"]} for row in labeled])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "parallel_ml_evaluation_only",
        "split_strategy": "time_aware_by_draft_class",
        "split_years": split.years,
        "n_labeled_rows": len(labeled),
        "n_test_rows": len(split.test),
        "ml_models": models_report,
        "non_ml_baselines": non_ml_report,
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
