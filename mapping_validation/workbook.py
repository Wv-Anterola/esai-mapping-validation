from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .schema import (
    CONTEXT_FIELDS,
    ID_REPAIR_FIELDS,
    ISSUE_FIELDS,
    VALID_BASES,
    VALID_STRENGTHS,
)


def _joined_unique(values: pd.Series) -> str:
    unique = sorted({str(value).strip() for value in values if str(value).strip()})
    return " || ".join(unique)


def _benchmark_lookup(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"benchmark_id", "title"}
    if not required.issubset(frame.columns):
        missing = sorted(required - set(frame.columns))
        raise ValueError(f"benchmarks sheet is missing columns: {missing}")
    source = frame.copy().fillna("")
    for field in ("quick ref", "description", "task", "metric", "evidence_type"):
        if field not in source.columns:
            source[field] = ""
    grouped = source.groupby("benchmark_id", dropna=False)
    result = grouped.agg(
        benchmark_quick_ref=("quick ref", _joined_unique),
        benchmark_title=("title", _joined_unique),
        benchmark_description=("description", _joined_unique),
        benchmark_task=("task", _joined_unique),
        benchmark_metric=("metric", _joined_unique),
        benchmark_evidence_type=("evidence_type", _joined_unique),
        benchmark_row_count=("benchmark_id", "size"),
    ).reset_index()
    result["benchmark_id_collision"] = (result["benchmark_row_count"] > 1).astype(str)
    return result.drop(columns=["benchmark_row_count"])


def _normalise_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _source_registry(path: Path | None) -> pd.DataFrame:
    columns = [
        "benchmark_id",
        "registry_source_url",
        "registry_source_abstract",
        "registry_source_status",
    ]
    if path is None:
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "benchmark_id",
        "source_url",
        "source_abstract",
        "source_status",
        "verified_at",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"source registry is missing columns: {sorted(missing)}")
    statuses = set(frame["source_status"].str.strip().str.casefold()) - {
        "",
        "pending",
        "verified",
        "rejected",
    }
    if statuses:
        raise ValueError(f"source registry has invalid statuses: {sorted(statuses)}")
    duplicates = sorted(
        frame.loc[frame["benchmark_id"].duplicated(keep=False), "benchmark_id"].unique()
    )
    if duplicates:
        raise ValueError(f"source registry has duplicate benchmark_ids: {duplicates}")
    verified = frame["source_status"].str.strip().str.casefold() == "verified"
    incomplete_verified = verified & (
        (frame["source_url"].str.strip() == "")
        | (frame["source_abstract"].str.strip() == "")
        | (frame["verified_at"].str.strip() == "")
    )
    if incomplete_verified.any():
        ids = sorted(frame.loc[incomplete_verified, "benchmark_id"].unique())
        raise ValueError(
            f"verified source rows require URL, abstract, and verified_at: {ids}"
        )
    frame = frame.rename(
        columns={
            "source_url": "registry_source_url",
            "source_abstract": "registry_source_abstract",
            "source_status": "registry_source_status",
        }
    )
    return frame[columns]


def _candidate_catalog(path: Path | None) -> pd.DataFrame:
    columns = ["title_key", "catalog_source_url", "catalog_source_abstract"]
    if path is None:
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {"title", "paper_url", "abstract"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"candidate catalog is missing columns: {sorted(missing)}")
    frame["title_key"] = frame["title"].map(_normalise_title)
    frame = frame.rename(
        columns={
            "paper_url": "catalog_source_url",
            "abstract": "catalog_source_abstract",
        }
    )
    ambiguous = frame["title_key"].duplicated(keep=False)
    return frame.loc[~ambiguous, columns]


def source_registry_template(
    workbook: Path, candidate_catalog: Path | None = None
) -> list[dict[str, str]]:
    benchmarks = pd.read_excel(workbook, sheet_name="benchmarks", dtype=str).fillna("")
    lookup = _benchmark_lookup(benchmarks)
    lookup["title_key"] = lookup["benchmark_title"].map(_normalise_title)
    lookup = lookup.merge(
        _candidate_catalog(candidate_catalog), on="title_key", how="left"
    ).fillna("")
    rows: list[dict[str, str]] = []
    for _, row in lookup.iterrows():
        prefilled = bool(row.get("catalog_source_url"))
        rows.append(
            {
                "benchmark_id": row["benchmark_id"],
                "title": row["benchmark_title"],
                "quick_ref": row["benchmark_quick_ref"],
                "source_url": row.get("catalog_source_url", ""),
                "source_abstract": row.get("catalog_source_abstract", ""),
                "source_status": "pending",
                "verified_at": "",
                "notes": (
                    "Prefilled from an exact normalized-title catalog match; "
                    "verify benchmark identity."
                    if prefilled
                    else ""
                ),
            }
        )
    return rows


def duplicate_edge_id_repairs(workbook: Path) -> list[dict[str, str]]:
    edges = pd.read_excel(workbook, sheet_name="bench_measures_harm", dtype=str).fillna(
        ""
    )
    required = {"edge_id", "benchmark_id", "harm_id"}
    missing = required - set(edges.columns)
    if missing:
        raise ValueError(f"bench_measures_harm is missing columns: {sorted(missing)}")

    reserved = set(edges["edge_id"])
    counters: dict[str, int] = {}
    for edge_id in reserved:
        match = re.fullmatch(r"(.*?)(\d+)", edge_id)
        if match:
            prefix, number = match.groups()
            counters[prefix] = max(counters.get(prefix, 0), int(number))

    seen: set[str] = set()
    repairs: list[dict[str, str]] = []
    for index, row in edges.iterrows():
        edge_id = row["edge_id"]
        if edge_id not in seen:
            seen.add(edge_id)
            continue
        match = re.fullmatch(r"(.*?)(\d+)", edge_id)
        if not match:
            raise ValueError(
                f"cannot propose a convention-preserving replacement for {edge_id}"
            )
        prefix = match.group(1)
        candidate = ""
        while not candidate or candidate in reserved:
            counters[prefix] = counters.get(prefix, 0) + 1
            candidate = f"{prefix}{counters[prefix]}"
        reserved.add(candidate)
        repairs.append(
            {
                "sheet": "bench_measures_harm",
                "row_number": str(index + 2),
                "operation": "update-key",
                "old_edge_id": edge_id,
                "benchmark_id": row["benchmark_id"],
                "harm_id": row["harm_id"],
                "new_edge_id": candidate,
                "reason": (
                    "duplicate edge_id; first workbook occurrence retains the key"
                ),
            }
        )
    return [
        {field: repair.get(field, "") for field in ID_REPAIR_FIELDS}
        for repair in repairs
    ]


def load_context(
    workbook: Path,
    source_registry: Path | None = None,
    candidate_catalog: Path | None = None,
) -> pd.DataFrame:
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
    if (edges["edge_id"].str.strip() == "").any():
        raise ValueError("bench_measures_harm contains a blank edge_id")
    edges["edge_id_collision"] = edges["edge_id"].duplicated(keep=False).astype(str)
    duplicate_harms = sorted(
        harms.loc[harms["harm_id"].duplicated(keep=False), "harm_id"].unique()
    )
    if duplicate_harms:
        raise ValueError(f"harms sheet has duplicate harm_ids: {duplicate_harms}")

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
        .merge(_source_registry(source_registry), on="benchmark_id", how="left")
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
    context["title_key"] = context["benchmark_title"].map(_normalise_title)
    context = context.merge(
        _candidate_catalog(candidate_catalog), on="title_key", how="left"
    )
    context = context.fillna("")
    registry_verified = (
        context.get("registry_source_status", "").str.strip().str.casefold()
        == "verified"
    )
    context["benchmark_source_url"] = context.get("registry_source_url", "").where(
        registry_verified & (context.get("registry_source_url", "") != ""),
        context.get("catalog_source_url", ""),
    )
    context["benchmark_source_abstract"] = context.get(
        "registry_source_abstract", ""
    ).where(
        registry_verified & (context.get("registry_source_abstract", "") != ""),
        context.get("catalog_source_abstract", ""),
    )
    context["source_match_method"] = ""
    context.loc[context.get("catalog_source_url", "") != "", "source_match_method"] = (
        "exact-normalized-title"
    )
    context.loc[
        registry_verified & (context.get("registry_source_url", "") != ""),
        "source_match_method",
    ] = "benchmark-id-registry"
    context["harm_description_missing"] = (context["harm_description"] == "").astype(
        str
    )
    context["harm_context"] = context["harm_description"].where(
        context["harm_description"] != "", context["harm_label"]
    )
    complete_metadata = (
        (context["benchmark_description"] != "")
        & (context["benchmark_task"] != "")
        & (context["benchmark_metric"] != "")
    )
    source_grounded = (context["benchmark_source_url"] != "") & (
        context["benchmark_source_abstract"] != ""
    )
    context["context_status"] = "metadata-incomplete"
    context.loc[complete_metadata, "context_status"] = "metadata-complete"
    context.loc[complete_metadata & source_grounded, "context_status"] = (
        "source-grounded"
    )
    for field in CONTEXT_FIELDS:
        if field not in context.columns:
            context[field] = ""
    return context[CONTEXT_FIELDS].fillna("")


def deterministic_issues(
    workbook: Path,
    source_registry: Path | None = None,
    candidate_catalog: Path | None = None,
) -> list[dict[str, str]]:
    context = load_context(workbook, source_registry, candidate_catalog)
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
        if row["edge_id_collision"] == "True":
            issues.append(
                {
                    **base,
                    "issue_type": "duplicate_edge_id",
                    "severity": "high",
                    "current_value": row["edge_id"],
                    "detail": (
                        "edge_id identifies more than one mapping row; assign a "
                        "unique edge_id before semantic validation"
                    ),
                }
            )
        if row["benchmark_evidence_type"].strip().casefold() == "model benchmark":
            if not row["benchmark_source_url"] or not row["benchmark_source_abstract"]:
                issues.append(
                    {
                        **base,
                        "issue_type": "benchmark_source_missing",
                        "severity": "blocking",
                        "current_value": row["context_status"],
                        "detail": (
                            "verify a benchmark source URL and abstract before "
                            "manual or model-based semantic validation"
                        ),
                    }
                )
            if (
                not row["benchmark_description"]
                or not row["benchmark_task"]
                or not row["benchmark_metric"]
            ):
                issues.append(
                    {
                        **base,
                        "issue_type": "benchmark_metadata_incomplete",
                        "severity": "blocking",
                        "current_value": row["context_status"],
                        "detail": (
                            "benchmark description, task, and metric are required "
                            "for semantic validation"
                        ),
                    }
                )
        if row["harm_description_missing"] == "True":
            issues.append(
                {
                    **base,
                    "issue_type": "harm_description_missing",
                    "severity": "review",
                    "current_value": row["harm_label"],
                    "detail": (
                        "validation will fall back to the harm label; add a harm "
                        "description where the label is not self-defining"
                    ),
                }
            )
        if row["benchmark_evidence_type"].strip().casefold() != "model benchmark":
            issues.append(
                {
                    **base,
                    "issue_type": "non_model_evidence_scope",
                    "severity": "scope",
                    "current_value": row["benchmark_evidence_type"],
                    "detail": (
                        "use an evidence-type-specific rubric; exclude from the "
                        "model-benchmark validation run"
                    ),
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
