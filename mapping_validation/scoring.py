from __future__ import annotations

from collections import Counter
from datetime import date
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


def validate_prediction_run(prediction_rows: list[dict[str, Any]]) -> None:
    runs = {
        (str(row.get("prompt_sha256", "")), str(row.get("model", "")))
        for row in prediction_rows
    }
    if len(runs) > 1:
        raise ValueError(
            "prediction file contains multiple prompt/model runs; "
            "score each run separately"
        )
    edge_ids = [str(row.get("edge_id", "")).strip() for row in prediction_rows]
    if any(not edge_id for edge_id in edge_ids):
        raise ValueError("every prediction must have an edge_id")
    duplicates = sorted(
        edge_id for edge_id, count in Counter(edge_ids).items() if count > 1
    )
    if duplicates:
        raise ValueError(f"prediction file contains duplicate edge_ids: {duplicates}")
    for row in prediction_rows:
        if row.get("parse_error"):
            continue
        edge_id = str(row.get("edge_id", ""))
        if row.get("verdict") not in VALID_VERDICTS:
            raise ValueError(f"prediction {edge_id} has an invalid verdict")
        if row.get("corrected_strength") not in PREDICTED_STRENGTHS:
            raise ValueError(f"prediction {edge_id} has an invalid strength")
        if row.get("corrected_basis") not in VALID_BASES:
            raise ValueError(f"prediction {edge_id} has an invalid basis")


def _completed_gold(
    gold_rows: list[dict[str, str]], split: str = "all"
) -> dict[str, dict[str, str]]:
    if split not in {"development", "test", "all"}:
        raise ValueError("split must be development, test, or all")
    incomplete_status = [
        row.get("edge_id", "")
        for row in gold_rows
        if row.get("gold_verdict", "")
        and row.get("annotation_status", "").strip().casefold() != "complete"
    ]
    if incomplete_status:
        raise ValueError(
            "gold rows with adjudicated labels must set annotation_status=complete: "
            f"{sorted(incomplete_status)}"
        )
    eligible_rows = [
        row
        for row in gold_rows
        if (
            row.get("annotation_status", "").casefold() == "complete"
            or row.get("gold_verdict", "")
        )
        and (split == "all" or row.get("gold_split", "") == split)
    ]
    edge_ids = [row.get("edge_id", "").strip() for row in eligible_rows]
    if any(not edge_id for edge_id in edge_ids):
        raise ValueError("every completed gold row must have an edge_id")
    duplicates = sorted(
        edge_id for edge_id, count in Counter(edge_ids).items() if count > 1
    )
    if duplicates:
        raise ValueError(f"gold file contains duplicate edge_ids: {duplicates}")
    completed = {row["edge_id"]: row for row in eligible_rows}
    for edge_id, row in completed.items():
        if row.get("gold_verdict") not in VALID_VERDICTS:
            raise ValueError(f"gold edge {edge_id} has an invalid verdict")
        if row.get("gold_strength") not in PREDICTED_STRENGTHS:
            raise ValueError(f"gold edge {edge_id} has an invalid strength")
        if row.get("gold_basis") not in VALID_BASES:
            raise ValueError(f"gold edge {edge_id} has an invalid basis")
        if not row.get("gold_reason", "").strip():
            raise ValueError(f"gold edge {edge_id} is missing a reason")
        if not row.get("gold_adjudicator", "").strip():
            raise ValueError(f"gold edge {edge_id} is missing an adjudicator")
        if not row.get("gold_adjudicated_at", "").strip():
            raise ValueError(f"gold edge {edge_id} is missing an adjudication date")
        try:
            date.fromisoformat(row["gold_adjudicated_at"])
        except ValueError as exc:
            raise ValueError(
                f"gold edge {edge_id} has a non-ISO adjudication date"
            ) from exc
    return completed


def score_rows(
    gold_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, Any]],
    split: str = "all",
) -> tuple[dict[str, object], list[dict[str, object]]]:
    validate_prediction_run(prediction_rows)
    completed_gold = _completed_gold(gold_rows, split)
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
        "gold_split": split,
        "scored_rows": len(edge_ids),
        "missing_predictions": len(set(completed_gold) - set(predictions)),
        "parse_errors": sum(
            bool(row.get("parse_error"))
            for row in prediction_rows
            if str(row.get("edge_id", "")) in completed_gold
        ),
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
    gold_path: Path, prediction_path: Path, split: str = "all"
) -> tuple[dict[str, object], list[dict[str, object]]]:
    return score_rows(read_csv(gold_path), read_jsonl(prediction_path), split)


def human_agreement(gold_rows: list[dict[str, str]]) -> dict[str, object]:
    annotation_fields = [
        f"annotator_{annotator}_{field}"
        for annotator in ("a", "b")
        for field in ("verdict", "strength", "basis", "reason", "name", "reviewed_at")
    ]
    incomplete = [
        row.get("edge_id", "")
        for row in gold_rows
        if any(row.get(field, "").strip() for field in annotation_fields)
        and not all(row.get(field, "").strip() for field in annotation_fields)
    ]
    if incomplete:
        raise ValueError(
            f"partially completed dual annotations for edge_ids: {sorted(incomplete)}"
        )
    rows = [
        row
        for row in gold_rows
        if row.get("annotator_a_verdict") and row.get("annotator_b_verdict")
    ]
    for row in rows:
        for prefix in ("annotator_a", "annotator_b"):
            if row[f"{prefix}_verdict"] not in VALID_VERDICTS:
                raise ValueError(f"{row['edge_id']} has an invalid {prefix} verdict")
            if row[f"{prefix}_strength"] not in PREDICTED_STRENGTHS:
                raise ValueError(f"{row['edge_id']} has an invalid {prefix} strength")
            if row[f"{prefix}_basis"] not in VALID_BASES:
                raise ValueError(f"{row['edge_id']} has an invalid {prefix} basis")
            try:
                date.fromisoformat(row[f"{prefix}_reviewed_at"])
            except ValueError as exc:
                raise ValueError(
                    f"{row['edge_id']} has a non-ISO {prefix} review date"
                ) from exc
    verdict_a = [row["annotator_a_verdict"] for row in rows]
    verdict_b = [row["annotator_b_verdict"] for row in rows]
    strength_a = [row["annotator_a_strength"] for row in rows]
    strength_b = [row["annotator_b_strength"] for row in rows]
    basis_a = [row["annotator_a_basis"] for row in rows]
    basis_b = [row["annotator_b_basis"] for row in rows]
    return {
        "double_annotated_rows": len(rows),
        "verdict_agreement": accuracy(verdict_a, verdict_b),
        "verdict_kappa": cohen_kappa(verdict_a, verdict_b),
        "strength_agreement": accuracy(strength_a, strength_b),
        "strength_kappa": cohen_kappa(strength_a, strength_b),
        "strength_weighted_kappa": quadratic_weighted_kappa(
            strength_a, strength_b, STRENGTH_ORDER
        )
        if rows
        else None,
        "basis_agreement": accuracy(basis_a, basis_b),
        "basis_kappa": cohen_kappa(basis_a, basis_b),
    }


def subgroup_scores(
    gold_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, Any]],
    split: str = "all",
) -> list[dict[str, object]]:
    completed = _completed_gold(gold_rows, split)
    output: list[dict[str, object]] = []
    for field in ("harm_domain", "current_strength"):
        values = sorted({row.get(field, "") for row in completed.values()})
        for value in values:
            subset = [row for row in completed.values() if row.get(field, "") == value]
            metrics, _ = score_rows(subset, prediction_rows, "all")
            output.append({"group_field": field, "group_value": value, **metrics})
    return output
