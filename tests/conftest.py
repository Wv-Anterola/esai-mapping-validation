from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    path = tmp_path / "mapping.xlsx"
    benchmarks = pd.DataFrame(
        [
            {
                "benchmark_id": "B1.01.01",
                "title": "Behavior Benchmark",
                "description": "Scores a concrete behavior.",
                "task": "Behavior generation",
                "metric": "Rate",
                "evidence_type": "model benchmark",
            },
            {
                "benchmark_id": "B2.01.01",
                "title": "First Colliding Benchmark",
                "description": "First source.",
                "task": "Task A",
                "metric": "Accuracy",
                "evidence_type": "model benchmark",
            },
            {
                "benchmark_id": "B2.01.01",
                "title": "Second Colliding Benchmark",
                "description": "Second source.",
                "task": "Task B",
                "metric": "Score",
                "evidence_type": "model benchmark",
            },
            {
                "benchmark_id": "B3.01.01",
                "title": "Economic Study",
                "description": "Observational economic analysis.",
                "task": "Analysis",
                "metric": "Concentration index",
                "evidence_type": "empirical study",
            },
        ]
    )
    harms = pd.DataFrame(
        [
            {
                "harm_id": "1.01.01",
                "label": "Harmful behavior",
                "description": "The model produces the behavior.",
                "domain": "Discrimination",
            },
            {
                "harm_id": "6.01.01",
                "label": "Market concentration",
                "description": "Economic power becomes concentrated.",
                "domain": "Socioeconomic",
            },
        ]
    )
    edges = pd.DataFrame(
        [
            {
                "edge_id": "e1",
                "benchmark_id": "B1.01.01",
                "harm_id": "1.01.01",
                "Harm: Domain": "1",
                "Harm: Subdomain": "1.1",
                "strength": "direct",
                "basis": "face-validity-only",
                "confidence": "probable",
                "notes": "Current rationale.",
            },
            {
                "edge_id": "e2",
                "benchmark_id": "B2.01.01",
                "harm_id": "1.01.01",
                "Harm: Domain": "1",
                "Harm: Subdomain": "1.1",
                "strength": "indirect",
                "basis": "face-validity-only",
                "confidence": "possible",
                "notes": "Ambiguous source.",
            },
            {
                "edge_id": "e3",
                "benchmark_id": "B3.01.01",
                "harm_id": "6.01.01",
                "Harm: Domain": "6",
                "Harm: Subdomain": "6.1",
                "strength": "weak-proxy",
                "basis": "face-validity-only",
                "confidence": "possible",
                "notes": "Economic proxy.",
            },
        ]
    )
    with pd.ExcelWriter(path) as writer:
        benchmarks.to_excel(writer, sheet_name="benchmarks", index=False)
        harms.to_excel(writer, sheet_name="harms", index=False)
        edges.to_excel(writer, sheet_name="bench_measures_harm", index=False)
    return path
