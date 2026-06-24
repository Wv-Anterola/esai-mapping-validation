from mapping_validation.scoring import score_rows


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
