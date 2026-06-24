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
    "edge_id_collision",
    "benchmark_id",
    "harm_id",
    "benchmark_quick_ref",
    "benchmark_title",
    "benchmark_description",
    "benchmark_task",
    "benchmark_metric",
    "benchmark_evidence_type",
    "benchmark_id_collision",
    "benchmark_source_url",
    "benchmark_source_abstract",
    "source_match_method",
    "context_status",
    "harm_label",
    "harm_description",
    "harm_context",
    "harm_description_missing",
    "harm_domain",
    "harm_subdomain",
    "current_strength",
    "current_basis",
    "current_confidence",
    "current_notes",
]

GOLD_FIELDS = CONTEXT_FIELDS + [
    "sample_stratum",
    "gold_split",
    "annotation_status",
    "annotator_a_verdict",
    "annotator_a_strength",
    "annotator_a_basis",
    "annotator_a_reason",
    "annotator_a_name",
    "annotator_a_reviewed_at",
    "annotator_b_verdict",
    "annotator_b_strength",
    "annotator_b_basis",
    "annotator_b_reason",
    "annotator_b_name",
    "annotator_b_reviewed_at",
    "gold_verdict",
    "gold_strength",
    "gold_basis",
    "gold_reason",
    "gold_adjudicator",
    "gold_adjudicated_at",
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
    "scored_construct",
    "evidence_used",
    "inference_steps",
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
    "scored_construct",
    "evidence_used",
    "inference_steps",
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

SOURCE_REGISTRY_FIELDS = [
    "benchmark_id",
    "title",
    "quick_ref",
    "source_url",
    "source_abstract",
    "source_status",
    "verified_at",
    "notes",
]

ID_REPAIR_FIELDS = [
    "sheet",
    "row_number",
    "operation",
    "old_edge_id",
    "benchmark_id",
    "harm_id",
    "new_edge_id",
    "reason",
]
