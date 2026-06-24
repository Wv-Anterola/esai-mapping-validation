from __future__ import annotations

from pathlib import Path

from .io import read_jsonl
from .schema import (
    PATCH_FIELDS,
    REVIEW_FIELDS,
    VALID_BASES,
    VALID_CONFIDENCE,
    VALID_STRENGTHS,
)
from .scoring import validate_prediction_run
from .workbook import load_context


def prepare_review(
    workbook: Path,
    prediction_path: Path,
    source_registry: Path | None = None,
    candidate_catalog: Path | None = None,
) -> list[dict[str, object]]:
    context = {
        row["edge_id"]: row
        for row in load_context(workbook, source_registry, candidate_catalog).to_dict(
            orient="records"
        )
    }
    predictions = read_jsonl(prediction_path)
    validate_prediction_run(predictions)
    colliding_prediction_edges = sorted(
        str(prediction.get("edge_id", ""))
        for prediction in predictions
        if str(prediction.get("edge_id", "")) in context
        and context[str(prediction.get("edge_id", ""))]["edge_id_collision"] == "True"
    )
    if colliding_prediction_edges:
        raise ValueError(
            "predictions contain duplicate workbook edge_ids: "
            f"{colliding_prediction_edges}"
        )
    unknown_edges = sorted(
        str(prediction.get("edge_id", ""))
        for prediction in predictions
        if str(prediction.get("edge_id", "")) not in context
    )
    if unknown_edges:
        raise ValueError(
            f"predictions contain edge_ids absent from the workbook: {unknown_edges}"
        )
    output: list[dict[str, object]] = []
    for prediction in predictions:
        edge_id = str(prediction.get("edge_id", ""))
        if edge_id not in context:
            continue
        current = context[edge_id]
        proposed_strength = str(prediction.get("corrected_strength", ""))
        proposed_basis = str(prediction.get("corrected_basis", ""))
        changed = (
            prediction.get("verdict") != "VALID"
            or proposed_strength != current["current_strength"]
            or proposed_basis != current["current_basis"]
            or bool(prediction.get("parse_error"))
            or bool(prediction.get("needs_human_review"))
        )
        if not changed:
            continue
        item = {field: current.get(field, "") for field in REVIEW_FIELDS}
        item.update(
            {
                "verdict": prediction.get("verdict", ""),
                "proposed_strength": proposed_strength,
                "proposed_basis": proposed_basis,
                "scored_construct": prediction.get("scored_construct", ""),
                "evidence_used": prediction.get("evidence_used", ""),
                "inference_steps": prediction.get("inference_steps", ""),
                "model_confidence": prediction.get("confidence", ""),
                "reason": prediction.get("reason", "")
                or prediction.get("parse_error", ""),
                "needs_human_review": prediction.get("needs_human_review", True),
                "prompt_name": prediction.get("prompt_name", ""),
                "prompt_sha256": prediction.get("prompt_sha256", ""),
                "model": prediction.get("model", ""),
                "review_status": "pending",
                "reviewer": "",
                "review_notes": "",
            }
        )
        output.append(item)
    return output


def approved_patches(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    patches: list[dict[str, str]] = []
    approved_edge_ids = [
        row.get("edge_id", "").strip()
        for row in rows
        if row.get("review_status", "").strip().casefold() == "approved"
    ]
    duplicate_edges = sorted(
        edge_id
        for edge_id in set(approved_edge_ids)
        if approved_edge_ids.count(edge_id) > 1
    )
    if duplicate_edges:
        raise ValueError(f"approved review has duplicate edge_ids: {duplicate_edges}")
    for row in rows:
        if row.get("review_status", "").strip().casefold() != "approved":
            continue
        strength = row.get("proposed_strength", "")
        basis = row.get("proposed_basis", "")
        confidence = row.get("model_confidence", "")
        missing_keys = [
            field
            for field in ("edge_id", "benchmark_id", "harm_id")
            if not row.get(field, "").strip()
        ]
        if missing_keys:
            raise ValueError(
                f"approved edge is missing tracker keys: {', '.join(missing_keys)}"
            )
        reviewer = row.get("reviewer", "").strip()
        if not reviewer:
            raise ValueError(
                f"approved edge {row.get('edge_id')} is missing a reviewer"
            )
        if strength != "none" and strength not in VALID_STRENGTHS:
            raise ValueError(f"approved edge {row.get('edge_id')} has invalid strength")
        if basis not in VALID_BASES:
            raise ValueError(f"approved edge {row.get('edge_id')} has invalid basis")
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(
                f"approved edge {row.get('edge_id')} has invalid confidence"
            )
        reason = row.get("review_notes", "").strip() or row.get("reason", "").strip()
        if not reason:
            raise ValueError(
                f"approved edge {row.get('edge_id')} is missing a review rationale"
            )
        existing_notes = row.get("current_notes", "").strip()
        notes = f"{existing_notes} Mapping validation: {reason}".strip()
        operation = "delete" if strength == "none" else "update"
        patches.append(
            {
                "sheet": "bench_measures_harm",
                "operation": operation,
                "edge_id": row.get("edge_id", ""),
                "benchmark_id": row.get("benchmark_id", ""),
                "harm_id": row.get("harm_id", ""),
                "strength": "" if operation == "delete" else strength,
                "basis": "" if operation == "delete" else basis,
                "confidence": "" if operation == "delete" else confidence,
                "notes": notes,
                "reviewer": reviewer,
            }
        )
    return [
        {field: patch.get(field, "") for field in PATCH_FIELDS} for patch in patches
    ]
