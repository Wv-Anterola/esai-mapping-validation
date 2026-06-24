from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .io import read_csv, read_jsonl, write_csv
from .review import approved_patches, prepare_review
from .runner import AnthropicClient, run_predictions
from .sampling import prepare_gold
from .schema import (
    CONTEXT_FIELDS,
    GOLD_FIELDS,
    ISSUE_FIELDS,
    PATCH_FIELDS,
    REVIEW_FIELDS,
)
from .scoring import score_files
from .workbook import deterministic_issues, load_context

DISAGREEMENT_FIELDS = [
    "edge_id",
    "benchmark_id",
    "harm_id",
    "gold_verdict",
    "predicted_verdict",
    "gold_strength",
    "predicted_strength",
    "gold_basis",
    "predicted_basis",
    "gold_reason",
    "predicted_reason",
]

COMPARISON_FIELDS = [
    "prediction_file",
    "prompt_name",
    "model",
    "gold_rows",
    "scored_rows",
    "missing_predictions",
    "parse_errors",
    "verdict_accuracy",
    "verdict_kappa",
    "verdict_macro_f1",
    "strength_accuracy",
    "strength_kappa",
    "strength_weighted_kappa",
    "basis_accuracy",
    "basis_kappa",
]


def audit_command(args: argparse.Namespace) -> int:
    issues = deterministic_issues(args.workbook)
    write_csv(args.out, issues, ISSUE_FIELDS)
    print(f"Deterministic issues: {len(issues)}")
    print(f"Output: {args.out}")
    return 0


def prepare_gold_command(args: argparse.Namespace) -> int:
    rows = prepare_gold(
        args.workbook,
        size=args.size,
        seed=args.seed,
        include_collisions=args.include_collisions,
    )
    write_csv(args.out, rows, GOLD_FIELDS)
    print(f"Gold-set rows: {len(rows)}")
    print(f"Annotation template: {args.out}")
    return 0


def prepare_all_command(args: argparse.Namespace) -> int:
    rows = load_context(args.workbook).to_dict(orient="records")
    if not args.include_collisions:
        rows = [row for row in rows if row["benchmark_id_collision"] != "True"]
    write_csv(args.out, rows, CONTEXT_FIELDS)
    print(f"Mapping rows: {len(rows)}")
    print(f"LLM input: {args.out}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    client = AnthropicClient()
    written, skipped = run_predictions(
        input_path=args.input,
        prompt_path=args.prompt,
        model=args.model,
        output_path=args.out,
        client=client,
        limit=args.limit,
    )
    print(f"Predictions written: {written}")
    print(f"Predictions resumed/skipped: {skipped}")
    print(f"Output: {args.out}")
    return 0


def score_command(args: argparse.Namespace) -> int:
    metrics, disagreements = score_files(args.gold, args.predictions)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(args.disagreements, disagreements, DISAGREEMENT_FIELDS)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    print(f"Disagreements: {args.disagreements}")
    return 0


def compare_command(args: argparse.Namespace) -> int:
    rows: list[dict[str, object]] = []
    for path in args.predictions:
        metrics, _ = score_files(args.gold, path)
        predictions = read_jsonl(path)
        first = predictions[0] if predictions else {}
        rows.append(
            {
                "prediction_file": str(path),
                "prompt_name": first.get("prompt_name", ""),
                "model": first.get("model", ""),
                **metrics,
            }
        )
    write_csv(args.out, rows, COMPARISON_FIELDS)
    print(f"Prompt runs compared: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def review_command(args: argparse.Namespace) -> int:
    rows = prepare_review(args.workbook, args.predictions)
    write_csv(args.out, rows, REVIEW_FIELDS)
    print(f"Review rows: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def export_command(args: argparse.Namespace) -> int:
    rows = approved_patches(read_csv(args.review))
    write_csv(args.out, rows, PATCH_FIELDS)
    print(f"Approved patches: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="esai-validate",
        description=(
            "Validate ESAI benchmark-to-harm mappings and prepare reviewed "
            "tracker patches."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="run deterministic workbook checks")
    audit.add_argument("--workbook", type=Path, required=True)
    audit.add_argument(
        "--out", type=Path, default=Path("outputs/deterministic_issues.csv")
    )
    audit.set_defaults(handler=audit_command)

    gold = subparsers.add_parser(
        "prepare-gold", help="create a stratified manual annotation set"
    )
    gold.add_argument("--workbook", type=Path, required=True)
    gold.add_argument("--size", type=int, default=60)
    gold.add_argument("--seed", type=int, default=20260624)
    gold.add_argument("--include-collisions", action="store_true")
    gold.add_argument("--out", type=Path, default=Path("gold/gold_edges.csv"))
    gold.set_defaults(handler=prepare_gold_command)

    all_rows = subparsers.add_parser(
        "prepare-all", help="prepare all unambiguous mapping edges"
    )
    all_rows.add_argument("--workbook", type=Path, required=True)
    all_rows.add_argument("--include-collisions", action="store_true")
    all_rows.add_argument("--out", type=Path, default=Path("outputs/all_edges.csv"))
    all_rows.set_defaults(handler=prepare_all_command)

    run = subparsers.add_parser(
        "run", help="run one prompt and model over an edge file"
    )
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--prompt", type=Path, required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--limit", type=int)
    run.set_defaults(handler=run_command)

    score = subparsers.add_parser(
        "score", help="score one prediction run against gold labels"
    )
    score.add_argument("--gold", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--metrics", type=Path, default=Path("outputs/metrics.json"))
    score.add_argument(
        "--disagreements", type=Path, default=Path("outputs/disagreements.csv")
    )
    score.set_defaults(handler=score_command)

    compare = subparsers.add_parser(
        "compare", help="compare multiple prompt or model runs"
    )
    compare.add_argument("--gold", type=Path, required=True)
    compare.add_argument("predictions", type=Path, nargs="+")
    compare.add_argument(
        "--out", type=Path, default=Path("outputs/prompt_comparison.csv")
    )
    compare.set_defaults(handler=compare_command)

    review = subparsers.add_parser(
        "prepare-review", help="combine predictions with current mappings"
    )
    review.add_argument("--workbook", type=Path, required=True)
    review.add_argument("--predictions", type=Path, required=True)
    review.add_argument(
        "--out", type=Path, default=Path("outputs/tracker_mapping_review.csv")
    )
    review.set_defaults(handler=review_command)

    export = subparsers.add_parser(
        "export", help="export human-approved tracker updates"
    )
    export.add_argument("--review", type=Path, required=True)
    export.add_argument("--out", type=Path, default=Path("outputs/tracker_patch.csv"))
    export.set_defaults(handler=export_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
