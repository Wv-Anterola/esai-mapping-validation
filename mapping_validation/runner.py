from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .io import append_jsonl, read_csv, read_jsonl
from .schema import (
    CONTEXT_FIELDS,
    PREDICTED_STRENGTHS,
    VALID_BASES,
    VALID_CONFIDENCE,
    VALID_VERDICTS,
)

SYSTEM_PROMPT = (
    "You are a precise data-quality reviewer. Follow the supplied rubric, "
    "use only the record "
    "provided, and return valid JSON without markdown."
)


class CompletionClient(Protocol):
    def complete(self, *, model: str, system: str, prompt: str) -> str: ...


class AnthropicClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for LLM execution")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - installation-path check
            raise RuntimeError(
                "install the Anthropic extra with: pip install -e '.[anthropic]'"
            ) from exc
        self.client = anthropic.Anthropic(api_key=key)

    def complete(self, *, model: str, system: str, prompt: str) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=1000,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        )


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_prompt(template: str, row: dict[str, str]) -> str:
    record = {field: row.get(field, "") for field in CONTEXT_FIELDS}
    return f"{template.rstrip()}\n\nMAPPING RECORD\n{json.dumps(record, indent=2)}\n"


def parse_response(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    parsed: Any = None
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(parsed, dict):
        raise ValueError("response does not contain a JSON object")

    verdict = str(parsed.get("verdict", "")).upper()
    strength = str(parsed.get("corrected_strength", "")).casefold()
    basis = str(parsed.get("corrected_basis", "")).casefold()
    confidence = str(parsed.get("confidence", "")).casefold()
    scored_construct = str(parsed.get("scored_construct", "")).strip()
    evidence_used = str(parsed.get("evidence_used", "")).strip()
    inference_steps = parsed.get("inference_steps")
    reason = str(parsed.get("reason", "")).strip()
    review = parsed.get("needs_human_review")
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"invalid verdict: {verdict}")
    if strength not in PREDICTED_STRENGTHS:
        raise ValueError(f"invalid corrected_strength: {strength}")
    if basis not in VALID_BASES:
        raise ValueError(f"invalid corrected_basis: {basis}")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"invalid confidence: {confidence}")
    if not scored_construct:
        raise ValueError("scored_construct is required")
    if not evidence_used:
        raise ValueError("evidence_used is required")
    if not isinstance(inference_steps, int) or inference_steps < 0:
        raise ValueError("inference_steps must be a non-negative integer")
    if not reason:
        raise ValueError("reason is required")
    if not isinstance(review, bool):
        raise ValueError("needs_human_review must be a boolean")
    return {
        "verdict": verdict,
        "corrected_strength": strength,
        "corrected_basis": basis,
        "scored_construct": scored_construct,
        "evidence_used": evidence_used,
        "inference_steps": inference_steps,
        "reason": reason,
        "confidence": confidence,
        "needs_human_review": review,
    }


def _call_with_retry(call: Callable[[], str], attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:  # provider SDK exceptions are version-specific
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"LLM request failed after {attempts} attempts: {last_error}")


def validate_prediction_input(
    rows: list[dict[str, str]], *, allow_metadata_only: bool = False
) -> None:
    if not rows:
        raise ValueError("prediction input is empty")
    edge_ids = [row.get("edge_id", "").strip() for row in rows]
    if any(not edge_id for edge_id in edge_ids):
        raise ValueError("every prediction input row must have an edge_id")
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("prediction input contains duplicate edge_ids")
    ungrounded = [
        row["edge_id"]
        for row in rows
        if row.get("context_status", "") != "source-grounded"
    ]
    if ungrounded and not allow_metadata_only:
        raise ValueError(
            f"prediction input contains {len(ungrounded)} rows without verified "
            "source context"
        )


def run_predictions(
    *,
    input_path: Path,
    prompt_path: Path,
    model: str,
    output_path: Path,
    client: CompletionClient,
    limit: int | None = None,
    allow_metadata_only: bool = False,
) -> tuple[int, int]:
    rows = read_csv(input_path)
    validate_prediction_input(rows, allow_metadata_only=allow_metadata_only)
    template = prompt_path.read_text(encoding="utf-8")
    digest = prompt_hash(template)
    prompt_name = prompt_path.stem
    existing = read_jsonl(output_path) if output_path.exists() else []
    existing_runs = {
        (str(row.get("prompt_sha256", "")), str(row.get("model", "")))
        for row in existing
    }
    if existing_runs and existing_runs != {(digest, model)}:
        raise ValueError(
            "output file belongs to a different prompt/model run; use a new path"
        )
    existing_keys = [
        (str(row.get("edge_id")), str(row.get("prompt_sha256")), str(row.get("model")))
        for row in existing
    ]
    if len(existing_keys) != len(set(existing_keys)):
        raise ValueError("output file contains duplicate prediction keys")
    completed = {
        (str(row.get("edge_id")), str(row.get("prompt_sha256")), str(row.get("model")))
        for row in existing
    }
    written = 0
    skipped = 0
    for row in rows:
        if limit is not None and written >= limit:
            break
        key = (row.get("edge_id", ""), digest, model)
        if key in completed:
            skipped += 1
            continue
        prompt = build_prompt(template, row)
        raw = _call_with_retry(
            lambda prompt=prompt: client.complete(
                model=model, system=SYSTEM_PROMPT, prompt=prompt
            )
        )
        prediction: dict[str, object] = {
            "edge_id": row.get("edge_id", ""),
            "prompt_name": prompt_name,
            "prompt_sha256": digest,
            "model": model,
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "raw_response": raw,
            "parse_error": "",
        }
        try:
            prediction.update(parse_response(raw))
        except ValueError as exc:
            prediction["parse_error"] = str(exc)
        append_jsonl(output_path, prediction)
        completed.add(key)
        written += 1
    return written, skipped
