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
from .workbook import load_context


def prepare_review(workbook: Path, prediction_path: Path) -> list[dict[str, object]]:
    context = {
        row["edge_id"]: row for row in load_context(workbook).to_dict(orient="records")
    }
    output: list[dict[str, object]] = []
    for prediction in read_jsonl(prediction_path):
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
    for row in rows:
        if row.get("review_status", "").strip().casefold() != "approved":
            continue
        strength = row.get("proposed_strength", "")
        basis = row.get("proposed_basis", "")
        confidence = row.get("model_confidence", "")
        if strength == "none":
            edge_id = row.get("edge_id")
            raise ValueError(
                f"approved edge {edge_id} has strength=none; remove operations "
                "require tracker-owner handling"
            )
        if strength not in VALID_STRENGTHS:
            raise ValueError(f"approved edge {row.get('edge_id')} has invalid strength")
        if basis not in VALID_BASES:
            raise ValueError(f"approved edge {row.get('edge_id')} has invalid basis")
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(
                f"approved edge {row.get('edge_id')} has invalid confidence"
            )
        reason = row.get("review_notes", "").strip() or row.get("reason", "").strip()
        existing_notes = row.get("current_notes", "").strip()
        notes = f"{existing_notes} Mapping validation: {reason}".strip()
        patches.append(
            {
                "sheet": "bench_measures_harm",
                "operation": "update",
                "edge_id": row.get("edge_id", ""),
                "benchmark_id": row.get("benchmark_id", ""),
                "harm_id": row.get("harm_id", ""),
                "strength": strength,
                "basis": basis,
                "confidence": confidence,
                "notes": notes,
                "reviewer": row.get("reviewer", ""),
            }
        )
    return [
        {field: patch.get(field, "") for field in PATCH_FIELDS} for patch in patches
    ]
