from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_csv, read_jsonl
from .schema import PREDICTED_STRENGTHS, VALID_BASES, VALID_VERDICTS

STRENGTH_ORDER = ["none", "contested", "weak-proxy", "strong-proxy", "direct"]


def cohen_kappa(gold: list[str], predicted: list[str]) -> float | None:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted labels must have equal length")
    if not gold:
        return None
    labels = sorted(set(gold) | set(predicted))
    total = len(gold)
    observed = (
        sum(left == right for left, right in zip(gold, predicted, strict=True)) / total
    )
    gold_counts = Counter(gold)
    predicted_counts = Counter(predicted)
    expected = sum(
        (gold_counts[label] / total) * (predicted_counts[label] / total)
        for label in labels
    )
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def quadratic_weighted_kappa(
    gold: list[str], predicted: list[str], order: list[str]
) -> float | None:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted labels must have equal length")
    if not gold:
        return None
    index = {label: position for position, label in enumerate(order)}
    unknown = (set(gold) | set(predicted)) - set(index)
    if unknown:
        raise ValueError(
            f"labels are missing from the ordinal scale: {sorted(unknown)}"
        )
    denominator = max(len(order) - 1, 1) ** 2
    observed = sum(
        ((index[left] - index[right]) ** 2) / denominator
        for left, right in zip(gold, predicted, strict=True)
    ) / len(gold)
    gold_counts = Counter(gold)
    predicted_counts = Counter(predicted)
    expected = 0.0
    for left in order:
        for right in order:
            weight = ((index[left] - index[right]) ** 2) / denominator
            expected += (
                weight * gold_counts[left] * predicted_counts[right] / (len(gold) ** 2)
            )
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - observed / expected


def accuracy(gold: list[str], predicted: list[str]) -> float | None:
    if not gold:
        return None
    return sum(
        left == right for left, right in zip(gold, predicted, strict=True)
    ) / len(gold)


def macro_f1(gold: list[str], predicted: list[str]) -> float | None:
    if not gold:
        return None
    labels = sorted(set(gold) | set(predicted))
    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            left == label and right == label
            for left, right in zip(gold, predicted, strict=True)
        )
        false_positive = sum(
            left != label and right == label
            for left, right in zip(gold, predicted, strict=True)
        )
        false_negative = sum(
            left == label and right != label
            for left, right in zip(gold, predicted, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(scores) / len(scores)


def score_rows(
    gold_rows: list[dict[str, str]], prediction_rows: list[dict[str, Any]]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    completed_gold = {
        row["edge_id"]: row
        for row in gold_rows
        if row.get("annotation_status", "").casefold() == "complete"
        or row.get("gold_verdict", "")
    }
    for edge_id, row in completed_gold.items():
        if row.get("gold_verdict") not in VALID_VERDICTS:
            raise ValueError(f"gold edge {edge_id} has an invalid verdict")
        if row.get("gold_strength") not in PREDICTED_STRENGTHS:
            raise ValueError(f"gold edge {edge_id} has an invalid strength")
        if row.get("gold_basis") not in VALID_BASES:
            raise ValueError(f"gold edge {edge_id} has an invalid basis")
        if not row.get("gold_reason", "").strip():
            raise ValueError(f"gold edge {edge_id} is missing a reason")
    predictions = {
        str(row.get("edge_id", "")): row
        for row in prediction_rows
        if not row.get("parse_error")
    }
    edge_ids = sorted(set(completed_gold) & set(predictions))

    gold_verdict = [completed_gold[edge]["gold_verdict"] for edge in edge_ids]
    predicted_verdict = [str(predictions[edge].get("verdict", "")) for edge in edge_ids]
    gold_strength = [completed_gold[edge]["gold_strength"] for edge in edge_ids]
    predicted_strength = [
        str(predictions[edge].get("corrected_strength", "")) for edge in edge_ids
    ]
    gold_basis = [completed_gold[edge]["gold_basis"] for edge in edge_ids]
    predicted_basis = [
        str(predictions[edge].get("corrected_basis", "")) for edge in edge_ids
    ]

    metrics: dict[str, object] = {
        "gold_rows": len(completed_gold),
        "scored_rows": len(edge_ids),
        "missing_predictions": len(set(completed_gold) - set(predictions)),
        "parse_errors": sum(bool(row.get("parse_error")) for row in prediction_rows),
        "verdict_accuracy": accuracy(gold_verdict, predicted_verdict),
        "verdict_kappa": cohen_kappa(gold_verdict, predicted_verdict),
        "verdict_macro_f1": macro_f1(gold_verdict, predicted_verdict),
        "strength_accuracy": accuracy(gold_strength, predicted_strength),
        "strength_kappa": cohen_kappa(gold_strength, predicted_strength),
        "strength_weighted_kappa": quadratic_weighted_kappa(
            gold_strength, predicted_strength, STRENGTH_ORDER
        )
        if edge_ids
        else None,
        "basis_accuracy": accuracy(gold_basis, predicted_basis),
        "basis_kappa": cohen_kappa(gold_basis, predicted_basis),
    }
    disagreements: list[dict[str, object]] = []
    for edge_id in edge_ids:
        gold = completed_gold[edge_id]
        prediction = predictions[edge_id]
        if (
            gold["gold_verdict"] == prediction.get("verdict")
            and gold["gold_strength"] == prediction.get("corrected_strength")
            and gold["gold_basis"] == prediction.get("corrected_basis")
        ):
            continue
        disagreements.append(
            {
                "edge_id": edge_id,
                "benchmark_id": gold.get("benchmark_id", ""),
                "harm_id": gold.get("harm_id", ""),
                "gold_verdict": gold["gold_verdict"],
                "predicted_verdict": prediction.get("verdict", ""),
                "gold_strength": gold["gold_strength"],
                "predicted_strength": prediction.get("corrected_strength", ""),
                "gold_basis": gold["gold_basis"],
                "predicted_basis": prediction.get("corrected_basis", ""),
                "gold_reason": gold.get("gold_reason", ""),
                "predicted_reason": prediction.get("reason", ""),
            }
        )
    return metrics, disagreements


def score_files(
    gold_path: Path, prediction_path: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    return score_rows(read_csv(gold_path), read_jsonl(prediction_path))
