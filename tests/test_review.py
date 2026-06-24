import pytest

from mapping_validation.review import approved_patches


def test_approved_review_exports_tracker_patch() -> None:
    rows = [
        {
            "review_status": "approved",
            "edge_id": "e1",
            "benchmark_id": "B1",
            "harm_id": "H1",
            "proposed_strength": "weak-proxy",
            "proposed_basis": "face-validity-only",
            "model_confidence": "possible",
            "current_notes": "Original.",
            "reason": "The relationship is indirect.",
            "reviewer": "Reviewer",
        }
    ]
    patches = approved_patches(rows)
    assert patches[0]["sheet"] == "bench_measures_harm"
    assert patches[0]["operation"] == "update"
    assert patches[0]["strength"] == "weak-proxy"
    assert "Original." in patches[0]["notes"]


def test_approved_none_exports_reviewed_deletion() -> None:
    patches = approved_patches(
        [
            {
                "review_status": "approved",
                "edge_id": "e1",
                "benchmark_id": "B1",
                "harm_id": "H1",
                "proposed_strength": "none",
                "proposed_basis": "face-validity-only",
                "model_confidence": "possible",
                "reason": "The mapping is unsupported.",
                "reviewer": "Reviewer",
            }
        ]
    )
    assert patches[0]["operation"] == "delete"
    assert patches[0]["strength"] == ""


def test_approved_review_requires_reviewer_and_rationale() -> None:
    row = {
        "review_status": "approved",
        "edge_id": "e1",
        "benchmark_id": "B1",
        "harm_id": "H1",
        "proposed_strength": "weak-proxy",
        "proposed_basis": "face-validity-only",
        "model_confidence": "possible",
        "reason": "A short causal chain remains.",
    }
    with pytest.raises(ValueError, match="reviewer"):
        approved_patches([row])
