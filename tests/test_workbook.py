from pathlib import Path

import pandas as pd

from mapping_validation.workbook import (
    deterministic_issues,
    duplicate_edge_id_repairs,
    load_context,
    source_registry_template,
)


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
    assert ("e1", "benchmark_source_missing") in types
    assert ("e2", "ambiguous_benchmark_id") in types
    assert ("e2", "invalid_strength") in types


def test_missing_catalog_matches_are_not_source_grounded(
    workbook: Path, tmp_path: Path
) -> None:
    catalog = tmp_path / "candidates.csv"
    pd.DataFrame(
        [
            {
                "title": "Behavior Benchmark",
                "paper_url": "https://example.test/behavior",
                "abstract": "A source abstract.",
            }
        ]
    ).to_csv(catalog, index=False)

    context = load_context(workbook, candidate_catalog=catalog).set_index("edge_id")
    assert context.loc["e1", "context_status"] == "source-grounded"
    assert context.loc["e3", "context_status"] == "metadata-complete"
    assert context.loc["e3", "benchmark_source_url"] == ""


def test_source_registry_requires_verified_status(
    workbook: Path, tmp_path: Path
) -> None:
    registry = tmp_path / "sources.csv"
    row = {
        "benchmark_id": "B1.01.01",
        "source_url": "https://example.test/source",
        "source_abstract": "A verified source abstract.",
        "source_status": "pending",
        "verified_at": "",
    }
    pd.DataFrame([row]).to_csv(registry, index=False)
    pending = load_context(workbook, source_registry=registry).set_index("edge_id")
    assert pending.loc["e1", "benchmark_source_url"] == ""

    pd.DataFrame(
        [{**row, "source_status": "verified", "verified_at": "2026-06-24"}]
    ).to_csv(registry, index=False)
    verified = load_context(workbook, source_registry=registry).set_index("edge_id")
    assert verified.loc["e1", "context_status"] == "source-grounded"
    assert verified.loc["e1", "source_match_method"] == "benchmark-id-registry"


def test_source_registry_prefills_exact_catalog_matches(
    workbook: Path, tmp_path: Path
) -> None:
    catalog = tmp_path / "candidates.csv"
    pd.DataFrame(
        [
            {
                "title": "Behavior Benchmark",
                "paper_url": "https://example.test/behavior",
                "abstract": "A source abstract.",
            }
        ]
    ).to_csv(catalog, index=False)

    rows = source_registry_template(workbook, catalog)
    match = next(row for row in rows if row["benchmark_id"] == "B1.01.01")
    assert match["source_url"] == "https://example.test/behavior"
    assert match["source_status"] == "pending"
    assert "verify benchmark identity" in match["notes"]


def test_collection_alias_match_carries_source_context(
    workbook: Path, tmp_path: Path
) -> None:
    catalog = tmp_path / "candidates.csv"
    pd.DataFrame(
        [
            {
                "title": "Behavior Benchmark: Extended Title",
                "paper_url": "https://example.test/behavior",
                "abstract": "A source abstract.",
                "already_in_tracker": "True",
                "tracker_match": "Behavior Benchmark",
                "tracker_match_method": "conservative-title-alias",
            }
        ]
    ).to_csv(catalog, index=False)

    context = load_context(workbook, candidate_catalog=catalog).set_index("edge_id")
    assert context.loc["e1", "context_status"] == "source-grounded"
    assert context.loc["e1", "source_match_method"] == (
        "catalog-conservative-title-alias"
    )


def test_duplicate_edge_ids_are_audited_without_expanding_rows(
    workbook: Path, tmp_path: Path
) -> None:
    duplicate_workbook = tmp_path / "duplicate-edges.xlsx"
    benchmarks = pd.read_excel(workbook, sheet_name="benchmarks", dtype=str)
    harms = pd.read_excel(workbook, sheet_name="harms", dtype=str)
    edges = pd.read_excel(workbook, sheet_name="bench_measures_harm", dtype=str)
    edges = pd.concat([edges, edges.iloc[[0]]], ignore_index=True)
    with pd.ExcelWriter(duplicate_workbook) as writer:
        benchmarks.to_excel(writer, sheet_name="benchmarks", index=False)
        harms.to_excel(writer, sheet_name="harms", index=False)
        edges.to_excel(writer, sheet_name="bench_measures_harm", index=False)

    context = load_context(duplicate_workbook)
    assert len(context) == 4
    assert set(context.loc[context["edge_id"] == "e1", "edge_id_collision"]) == {"True"}
    issues = deterministic_issues(duplicate_workbook)
    assert sum(issue["issue_type"] == "duplicate_edge_id" for issue in issues) == 2
    repairs = duplicate_edge_id_repairs(duplicate_workbook)
    assert len(repairs) == 1
    assert repairs[0]["old_edge_id"] == "e1"
    assert repairs[0]["new_edge_id"] == "e4"
    assert repairs[0]["row_number"] == "5"
