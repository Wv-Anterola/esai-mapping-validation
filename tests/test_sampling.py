from pathlib import Path

from mapping_validation.sampling import prepare_gold


def test_gold_sampling_is_reproducible_and_excludes_collisions(workbook: Path) -> None:
    first = prepare_gold(workbook, size=2, seed=7)
    second = prepare_gold(workbook, size=2, seed=7)
    assert [row["edge_id"] for row in first] == [row["edge_id"] for row in second]
    assert {row["edge_id"] for row in first} == {"e1", "e3"}
    assert all(row["annotation_status"] == "pending" for row in first)
    assert all(not row["gold_verdict"] for row in first)
