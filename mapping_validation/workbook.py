from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import CONTEXT_FIELDS, ISSUE_FIELDS, VALID_BASES, VALID_STRENGTHS


def _joined_unique(values: pd.Series) -> str:
    unique = sorted({str(value).strip() for value in values if str(value).strip()})
    return " || ".join(unique)


def _benchmark_lookup(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"benchmark_id", "title"}
    if not required.issubset(frame.columns):
        missing = sorted(required - set(frame.columns))
        raise ValueError(f"benchmarks sheet is missing columns: {missing}")
    source = frame.copy().fillna("")
    for field in ("description", "task", "metric", "evidence_type"):
        if field not in source.columns:
            source[field] = ""
    grouped = source.groupby("benchmark_id", dropna=False)
    result = grouped.agg(
        benchmark_title=("title", _joined_unique),
        benchmark_description=("description", _joined_unique),
        benchmark_task=("task", _joined_unique),
        benchmark_metric=("metric", _joined_unique),
        benchmark_evidence_type=("evidence_type", _joined_unique),
        benchmark_row_count=("benchmark_id", "size"),
    ).reset_index()
    result["benchmark_id_collision"] = (result["benchmark_row_count"] > 1).astype(str)
    return result.drop(columns=["benchmark_row_count"])


def load_context(workbook: Path) -> pd.DataFrame:
    excel = pd.ExcelFile(workbook)
    required_sheets = {"benchmarks", "harms", "bench_measures_harm"}
    missing_sheets = required_sheets - set(excel.sheet_names)
    if missing_sheets:
        raise ValueError(f"workbook is missing sheets: {sorted(missing_sheets)}")

    benchmarks = excel.parse("benchmarks", dtype=str).fillna("")
    harms = excel.parse("harms", dtype=str).fillna("")
    edges = excel.parse("bench_measures_harm", dtype=str).fillna("")

    required_edges = {
        "edge_id",
        "benchmark_id",
        "harm_id",
        "strength",
        "basis",
        "confidence",
    }
    missing_edges = required_edges - set(edges.columns)
    if missing_edges:
        raise ValueError(
            f"bench_measures_harm is missing columns: {sorted(missing_edges)}"
        )
    if not {"harm_id", "label"}.issubset(harms.columns):
        raise ValueError("harms sheet must contain harm_id and label")

    for field in ("description", "domain"):
        if field not in harms.columns:
            harms[field] = ""
    if "notes" not in edges.columns:
        edges["notes"] = ""
    for field in ("Harm: Domain", "Harm: Subdomain"):
        if field not in edges.columns:
            edges[field] = ""

    harm_lookup = harms[["harm_id", "label", "description", "domain"]].rename(
        columns={
            "label": "harm_label",
            "description": "harm_description",
            "domain": "harm_domain_from_node",
        }
    )
    edges = edges.rename(
        columns={
            "Harm: Domain": "harm_domain_from_edge",
            "Harm: Subdomain": "harm_subdomain",
        }
    )
    context = (
        edges.merge(_benchmark_lookup(benchmarks), on="benchmark_id", how="left")
        .merge(harm_lookup, on="harm_id", how="left")
        .rename(
            columns={
                "strength": "current_strength",
                "basis": "current_basis",
                "confidence": "current_confidence",
                "notes": "current_notes",
            }
        )
    )
    context["harm_domain"] = context.get("harm_domain_from_edge", "").where(
        context.get("harm_domain_from_edge", "") != "",
        context.get("harm_domain_from_node", ""),
    )
    for field in CONTEXT_FIELDS:
        if field not in context.columns:
            context[field] = ""
    return context[CONTEXT_FIELDS].fillna("")


def deterministic_issues(workbook: Path) -> list[dict[str, str]]:
    context = load_context(workbook)
    issues: list[dict[str, str]] = []
    for _, row in context.iterrows():
        base = {
            "edge_id": row["edge_id"],
            "benchmark_id": row["benchmark_id"],
            "harm_id": row["harm_id"],
        }
        if not row["benchmark_title"]:
            issues.append(
                {
                    **base,
                    "issue_type": "dangling_benchmark_id",
                    "severity": "high",
                    "current_value": row["benchmark_id"],
                    "detail": "edge benchmark_id is absent from the benchmarks sheet",
                }
            )
        if not row["harm_label"]:
            issues.append(
                {
                    **base,
                    "issue_type": "dangling_harm_id",
                    "severity": "high",
                    "current_value": row["harm_id"],
                    "detail": "edge harm_id is absent from the harms sheet",
                }
            )
        if row["benchmark_id_collision"] == "True":
            issues.append(
                {
                    **base,
                    "issue_type": "ambiguous_benchmark_id",
                    "severity": "high",
                    "current_value": row["benchmark_id"],
                    "detail": "benchmark_id resolves to more than one benchmark row",
                }
            )
        if row["current_strength"] not in VALID_STRENGTHS:
            issues.append(
                {
                    **base,
                    "issue_type": "invalid_strength",
                    "severity": "medium",
                    "current_value": row["current_strength"],
                    "detail": f"strength must be one of: {', '.join(VALID_STRENGTHS)}",
                }
            )
        if row["current_basis"] not in VALID_BASES:
            issues.append(
                {
                    **base,
                    "issue_type": "invalid_basis",
                    "severity": "medium",
                    "current_value": row["current_basis"],
                    "detail": f"basis must be one of: {', '.join(VALID_BASES)}",
                }
            )
        if (
            row["current_strength"] == "direct"
            and row["current_basis"] == "face-validity-only"
        ):
            issues.append(
                {
                    **base,
                    "issue_type": "direct_face_validity_review",
                    "severity": "review",
                    "current_value": "direct / face-validity-only",
                    "detail": (
                        "direct strength requires a literal harm instance or "
                        "downstream validation"
                    ),
                }
            )
    return [{field: row.get(field, "") for field in ISSUE_FIELDS} for row in issues]
