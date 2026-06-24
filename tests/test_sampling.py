from pathlib import Path

import pytest

from mapping_validation.sampling import prepare_gold


def test_gold_sampling_is_reproducible_and_excludes_collisions(workbook: Path) -> None:
    first = prepare_gold(workbook, size=1, seed=7, require_source_grounded=False)
    second = prepare_gold(workbook, size=1, seed=7, require_source_grounded=False)
    assert [row["edge_id"] for row in first] == [row["edge_id"] for row in second]
    assert {row["edge_id"] for row in first} == {"e1"}
    assert all(row["annotation_status"] == "pending" for row in first)
    assert all(not row["gold_verdict"] for row in first)

    with_non_model = prepare_gold(
        workbook,
        size=2,
        seed=7,
        include_non_model=True,
        require_source_grounded=False,
    )
    assert {row["edge_id"] for row in with_non_model} == {"e1", "e3"}
    assert {row["gold_split"] for row in with_non_model} == {"development"}


def test_gold_sampling_rejects_repeated_benchmarks(workbook: Path) -> None:
    with pytest.raises(ValueError, match="unique benchmarks"):
        prepare_gold(workbook, size=2, require_source_grounded=False)


def test_gold_sampling_requires_verified_sources(workbook: Path) -> None:
    with pytest.raises(ValueError, match="without verified source context"):
        prepare_gold(workbook, size=1)
