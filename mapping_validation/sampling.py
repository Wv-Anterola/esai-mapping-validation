from __future__ import annotations

import random
from collections import defaultdict, deque
from pathlib import Path

from .schema import GOLD_FIELDS
from .workbook import load_context

ANNOTATION_FIELDS = [
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


def _balanced_split(rows: list[dict[str, str]], seed: int) -> None:
    by_stratum: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_stratum[row["sample_stratum"]].append(row)
    rng = random.Random(seed + 1)
    for stratum in sorted(by_stratum):
        group = by_stratum[stratum]
        rng.shuffle(group)
        for index, row in enumerate(group):
            row["gold_split"] = "test" if index % 3 == 2 else "development"
    target_test_rows = len(rows) // 3
    current_test_rows = sum(row["gold_split"] == "test" for row in rows)
    candidates: list[dict[str, str]] = []
    for stratum in sorted(by_stratum):
        development = [
            row for row in by_stratum[stratum] if row["gold_split"] == "development"
        ]
        rng.shuffle(development)
        candidates.extend(development[:-1])
    rng.shuffle(candidates)
    for row in candidates[: target_test_rows - current_test_rows]:
        row["gold_split"] = "test"


def prepare_gold(
    workbook: Path,
    *,
    size: int = 90,
    seed: int = 20260624,
    include_collisions: bool = False,
    include_non_model: bool = False,
    require_source_grounded: bool = True,
    source_registry: Path | None = None,
    candidate_catalog: Path | None = None,
) -> list[dict[str, str]]:
    """Create a diverse edge sample with a benchmark-independent first pass."""
    if size < 1:
        raise ValueError("gold-set size must be positive")
    context = load_context(workbook, source_registry, candidate_catalog)
    rows = context.to_dict(orient="records")
    if not include_collisions:
        rows = [
            row
            for row in rows
            if row["benchmark_id_collision"] != "True"
            and row["edge_id_collision"] != "True"
        ]
    if not include_non_model:
        rows = [
            row
            for row in rows
            if row["benchmark_evidence_type"].strip().casefold() == "model benchmark"
        ]
    if not rows:
        raise ValueError("no eligible edges are available for the gold set")
    unique_benchmarks = {row["benchmark_id"] for row in rows}
    if size > len(unique_benchmarks):
        raise ValueError(
            f"requested {size} rows but only {len(unique_benchmarks)} unique "
            "benchmarks are eligible"
        )

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["current_strength"], row["harm_domain"])
        row["sample_stratum"] = " | ".join(key)
        groups[key].append(row)

    rng = random.Random(seed)
    queues: list[deque[dict[str, str]]] = []
    for key in sorted(groups, key=lambda value: (len(groups[value]), value)):
        group = groups[key]
        rng.shuffle(group)
        queues.append(deque(group))

    target = size
    selected: list[dict[str, str]] = []
    seen_benchmarks: set[str] = set()
    while len(selected) < target:
        made_progress = False
        for queue in queues:
            while queue and queue[0]["benchmark_id"] in seen_benchmarks:
                queue.popleft()
            if queue and len(selected) < target:
                row = queue.popleft()
                selected.append(row)
                seen_benchmarks.add(row["benchmark_id"])
                made_progress = True
        if not made_progress:
            break

    if len(selected) != target:
        raise RuntimeError(
            "gold sampling did not reach the requested unique-benchmark size"
        )
    if require_source_grounded:
        ungrounded = [
            row["benchmark_id"]
            for row in selected
            if row["context_status"] != "source-grounded"
        ]
        if ungrounded:
            raise ValueError(
                f"gold sample contains {len(ungrounded)} benchmarks without verified "
                "source context; resolve the source registry or use "
                "--allow-metadata-only for diagnostic output"
            )

    output: list[dict[str, str]] = []
    for row in selected:
        item = {field: str(row.get(field, "")) for field in GOLD_FIELDS}
        item["annotation_status"] = "pending"
        for field in ANNOTATION_FIELDS:
            item[field] = ""
        output.append(item)
    _balanced_split(output, seed)
    return output
