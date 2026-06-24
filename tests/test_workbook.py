from pathlib import Path

from mapping_validation.workbook import deterministic_issues, load_context


def test_context_does_not_expand_colliding_ids(workbook: Path) -> None:
    context = load_context(workbook)
    assert len(context) == 3
    collision = context.loc[context["edge_id"] == "e2"].iloc[0]
    assert collision["benchmark_id_collision"] == "True"
    assert "First Colliding Benchmark" in collision["benchmark_title"]
    assert "Second Colliding Benchmark" in collision["benchmark_title"]


def test_deterministic_checks_identify_review_conditions(workbook: Path) -> None:
    issues = deterministic_issues(workbook)
    types = {(row["edge_id"], row["issue_type"]) for row in issues}
    assert ("e1", "direct_face_validity_review") in types
    assert ("e2", "ambiguous_benchmark_id") in types
    assert ("e2", "invalid_strength") in types
