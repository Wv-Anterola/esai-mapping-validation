import pytest

from mapping_validation.scoring import human_agreement, score_rows


def test_scoring_reports_agreement_and_disagreements() -> None:
    gold = [
        {
            "edge_id": "e1",
            "benchmark_id": "B1",
            "harm_id": "H1",
            "annotation_status": "complete",
            "gold_verdict": "VALID",
            "gold_strength": "direct",
            "gold_basis": "face-validity-only",
            "gold_reason": "Literal behavior.",
            "gold_adjudicator": "Reviewer C",
            "gold_adjudicated_at": "2026-06-24",
        },
        {
            "edge_id": "e2",
            "benchmark_id": "B2",
            "harm_id": "H2",
            "annotation_status": "complete",
            "gold_verdict": "DOWN-RATE",
            "gold_strength": "weak-proxy",
            "gold_basis": "face-validity-only",
            "gold_reason": "Long inference chain.",
            "gold_adjudicator": "Reviewer C",
            "gold_adjudicated_at": "2026-06-24",
        },
    ]
    predictions = [
        {
            "edge_id": "e1",
            "verdict": "VALID",
            "corrected_strength": "direct",
            "corrected_basis": "face-validity-only",
            "reason": "Literal behavior.",
            "parse_error": "",
        },
        {
            "edge_id": "e2",
            "verdict": "VALID",
            "corrected_strength": "strong-proxy",
            "corrected_basis": "face-validity-only",
            "reason": "Short chain.",
            "parse_error": "",
        },
    ]
    metrics, disagreements = score_rows(gold, predictions)
    assert metrics["verdict_accuracy"] == 0.5
    assert metrics["strength_accuracy"] == 0.5
    assert len(disagreements) == 1
    assert disagreements[0]["edge_id"] == "e2"


def test_scoring_rejects_mixed_or_duplicate_prediction_runs() -> None:
    gold = [
        {
            "edge_id": "e1",
            "annotation_status": "complete",
            "gold_verdict": "VALID",
            "gold_strength": "direct",
            "gold_basis": "face-validity-only",
            "gold_reason": "Literal behavior.",
            "gold_adjudicator": "Reviewer C",
            "gold_adjudicated_at": "2026-06-24",
        }
    ]
    base = {
        "edge_id": "e1",
        "prompt_sha256": "prompt-a",
        "model": "model-a",
        "verdict": "VALID",
        "corrected_strength": "direct",
        "corrected_basis": "face-validity-only",
        "parse_error": "",
    }
    with pytest.raises(ValueError, match="duplicate edge_ids"):
        score_rows(gold, [base, dict(base)])
    with pytest.raises(ValueError, match="multiple prompt/model runs"):
        score_rows(
            gold,
            [base, {**base, "edge_id": "e2", "model": "model-b"}],
        )


def test_human_agreement_scores_complete_independent_annotations() -> None:
    rows = [
        {
            "edge_id": "e1",
            "annotator_a_verdict": "VALID",
            "annotator_a_strength": "direct",
            "annotator_a_basis": "face-validity-only",
            "annotator_a_reason": "Literal behavior.",
            "annotator_a_name": "Reviewer A",
            "annotator_a_reviewed_at": "2026-06-23",
            "annotator_b_verdict": "DOWN-RATE",
            "annotator_b_strength": "strong-proxy",
            "annotator_b_basis": "face-validity-only",
            "annotator_b_reason": "One inference step.",
            "annotator_b_name": "Reviewer B",
            "annotator_b_reviewed_at": "2026-06-24",
        }
    ]
    metrics = human_agreement(rows)
    assert metrics["double_annotated_rows"] == 1
    assert metrics["verdict_agreement"] == 0.0
    assert metrics["basis_agreement"] == 1.0

    with pytest.raises(ValueError, match="partially completed"):
        human_agreement([{"edge_id": "e2", "annotator_a_verdict": "VALID"}])
