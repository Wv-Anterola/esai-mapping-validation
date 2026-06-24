from __future__ import annotations

VALID_STRENGTHS = ("direct", "strong-proxy", "weak-proxy", "contested")
PREDICTED_STRENGTHS = VALID_STRENGTHS + ("none",)
VALID_BASES = (
    "validated-against-downstream",
    "face-validity-only",
    "known-non-correlation",
)
VALID_VERDICTS = (
    "VALID",
    "DOWN-RATE",
    "UP-RATE",
    "REVISE-BASIS",
    "NOT-A-BENCHMARK",
    "WRONG-HARM",
    "INSUFFICIENT-EVIDENCE",
)
VALID_CONFIDENCE = ("probable", "possible", "uncertain", "tentative")

CONTEXT_FIELDS = [
    "edge_id",
    "benchmark_id",
    "harm_id",
    "benchmark_title",
    "benchmark_description",
    "benchmark_task",
    "benchmark_metric",
    "benchmark_evidence_type",
    "benchmark_id_collision",
    "harm_label",
    "harm_description",
    "harm_domain",
    "harm_subdomain",
    "current_strength",
    "current_basis",
    "current_confidence",
    "current_notes",
]

GOLD_FIELDS = CONTEXT_FIELDS + [
    "annotation_status",
    "gold_verdict",
    "gold_strength",
    "gold_basis",
    "gold_reason",
    "gold_annotator",
    "gold_reviewed_at",
]

PREDICTION_FIELDS = [
    "edge_id",
    "prompt_name",
    "prompt_sha256",
    "model",
    "created_at",
    "verdict",
    "corrected_strength",
    "corrected_basis",
    "reason",
    "confidence",
    "needs_human_review",
    "raw_response",
    "parse_error",
]

ISSUE_FIELDS = [
    "issue_type",
    "severity",
    "edge_id",
    "benchmark_id",
    "harm_id",
    "current_value",
    "detail",
]

REVIEW_FIELDS = CONTEXT_FIELDS + [
    "verdict",
    "proposed_strength",
    "proposed_basis",
    "model_confidence",
    "reason",
    "needs_human_review",
    "prompt_name",
    "prompt_sha256",
    "model",
    "review_status",
    "reviewer",
    "review_notes",
]

PATCH_FIELDS = [
    "sheet",
    "operation",
    "edge_id",
    "benchmark_id",
    "harm_id",
    "strength",
    "basis",
    "confidence",
    "notes",
    "reviewer",
]
