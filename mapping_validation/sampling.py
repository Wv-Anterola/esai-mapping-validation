from __future__ import annotations

import random
from collections import defaultdict, deque
from pathlib import Path

from .schema import GOLD_FIELDS
from .workbook import load_context


def prepare_gold(
    workbook: Path,
    *,
    size: int = 60,
    seed: int = 20260624,
    include_collisions: bool = False,
) -> list[dict[str, str]]:
    if size < 1:
        raise ValueError("gold-set size must be positive")
    context = load_context(workbook)
    rows = context.to_dict(orient="records")
    if not include_collisions:
        rows = [row for row in rows if row["benchmark_id_collision"] != "True"]
    if not rows:
        raise ValueError("no eligible edges are available for the gold set")

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["current_strength"], row["benchmark_evidence_type"])
        groups[key].append(row)

    rng = random.Random(seed)
    queues: list[deque[dict[str, str]]] = []
    for key in sorted(groups):
        group = groups[key]
        rng.shuffle(group)
        queues.append(deque(group))

    selected: list[dict[str, str]] = []
    target = min(size, len(rows))
    while len(selected) < target:
        made_progress = False
        for queue in queues:
            if queue and len(selected) < target:
                selected.append(queue.popleft())
                made_progress = True
        if not made_progress:
            break

    output: list[dict[str, str]] = []
    for row in selected:
        item = {field: str(row.get(field, "")) for field in GOLD_FIELDS}
        item.update(
            {
                "annotation_status": "pending",
                "gold_verdict": "",
                "gold_strength": "",
                "gold_basis": "",
                "gold_reason": "",
                "gold_annotator": "",
                "gold_reviewed_at": "",
            }
        )
        output.append(item)
    return output
