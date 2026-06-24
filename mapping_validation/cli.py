from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .io import read_csv, read_jsonl, write_csv
from .provenance import write_manifest
from .review import approved_patches, prepare_review
from .runner import AnthropicClient, run_predictions, validate_prediction_input
from .sampling import prepare_gold
from .schema import (
    CONTEXT_FIELDS,
    GOLD_FIELDS,
    ID_REPAIR_FIELDS,
    ISSUE_FIELDS,
    PATCH_FIELDS,
    REVIEW_FIELDS,
    SOURCE_REGISTRY_FIELDS,
)
from .scoring import human_agreement, score_files, subgroup_scores
from .workbook import (
    deterministic_issues,
    duplicate_edge_id_repairs,
    load_context,
    source_registry_template,
)

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

SUBGROUP_FIELDS = ["group_field", "group_value"] + [
    field
    for field in COMPARISON_FIELDS
    if field not in {"prediction_file", "prompt_name", "model"}
]


def _context_paths(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    return getattr(args, "source_registry", None), getattr(
        args, "candidate_catalog", None
    )


def _add_context_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-registry", type=Path)
    parser.add_argument("--candidate-catalog", type=Path)


def audit_command(args: argparse.Namespace) -> int:
    source_registry, candidate_catalog = _context_paths(args)
    issues = deterministic_issues(args.workbook, source_registry, candidate_catalog)
    write_csv(args.out, issues, ISSUE_FIELDS)
    write_manifest(
        args.out,
        command="audit",
        workbook=args.workbook,
        inputs=[path for path in (source_registry, candidate_catalog) if path],
        counts={"issues": len(issues)},
    )
    print(f"Deterministic issues: {len(issues)}")
    print(f"Output: {args.out}")
    return 0


def prepare_gold_command(args: argparse.Namespace) -> int:
    source_registry, candidate_catalog = _context_paths(args)
    rows = prepare_gold(
        args.workbook,
        size=args.size,
        seed=args.seed,
        include_collisions=args.include_collisions,
        include_non_model=args.include_non_model,
        require_source_grounded=not args.allow_metadata_only,
        source_registry=source_registry,
        candidate_catalog=candidate_catalog,
    )
    write_csv(args.out, rows, GOLD_FIELDS)
    write_manifest(
        args.out,
        command="prepare-gold",
        workbook=args.workbook,
        inputs=[path for path in (source_registry, candidate_catalog) if path],
        parameters={
            "size": args.size,
            "seed": args.seed,
            "include_collisions": args.include_collisions,
            "include_non_model": args.include_non_model,
            "allow_metadata_only": args.allow_metadata_only,
        },
        counts={
            "rows": len(rows),
            "unique_benchmarks": len({row["benchmark_id"] for row in rows}),
            "development_rows": sum(row["gold_split"] == "development" for row in rows),
            "test_rows": sum(row["gold_split"] == "test" for row in rows),
        },
    )
    print(f"Gold-set rows: {len(rows)}")
    print(f"Annotation template: {args.out}")
    return 0


def prepare_all_command(args: argparse.Namespace) -> int:
    source_registry, candidate_catalog = _context_paths(args)
    rows = load_context(args.workbook, source_registry, candidate_catalog).to_dict(
        orient="records"
    )
    if not args.include_collisions:
        rows = [
            row
            for row in rows
            if row["benchmark_id_collision"] != "True"
            and row["edge_id_collision"] != "True"
        ]
    if not args.include_non_model:
        rows = [
            row
            for row in rows
            if row["benchmark_evidence_type"].strip().casefold() == "model benchmark"
        ]
    ungrounded = [row for row in rows if row["context_status"] != "source-grounded"]
    if ungrounded and not args.allow_metadata_only:
        raise ValueError(
            f"{len(ungrounded)} eligible rows lack verified source context; "
            "resolve the source registry before preparing a full model input"
        )
    write_csv(args.out, rows, CONTEXT_FIELDS)
    write_manifest(
        args.out,
        command="prepare-all",
        workbook=args.workbook,
        inputs=[path for path in (source_registry, candidate_catalog) if path],
        parameters={
            "include_collisions": args.include_collisions,
            "include_non_model": args.include_non_model,
            "allow_metadata_only": args.allow_metadata_only,
        },
        counts={
            "rows": len(rows),
            "source_grounded": sum(
                row["context_status"] == "source-grounded" for row in rows
            ),
            "metadata_incomplete": sum(
                row["context_status"] == "metadata-incomplete" for row in rows
            ),
        },
    )
    print(f"Mapping rows: {len(rows)}")
    print(f"LLM input: {args.out}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    validate_prediction_input(
        read_csv(args.input), allow_metadata_only=args.allow_metadata_only
    )
    client = AnthropicClient()
    written, skipped = run_predictions(
        input_path=args.input,
        prompt_path=args.prompt,
        model=args.model,
        output_path=args.out,
        client=client,
        limit=args.limit,
        allow_metadata_only=args.allow_metadata_only,
    )
    write_manifest(
        args.out,
        command="run",
        inputs=[args.input, args.prompt],
        parameters={
            "model": args.model,
            "provider": "anthropic",
            "limit": args.limit,
            "allow_metadata_only": args.allow_metadata_only,
        },
        counts={"written": written, "resumed_or_skipped": skipped},
    )
    print(f"Predictions written: {written}")
    print(f"Predictions resumed/skipped: {skipped}")
    print(f"Output: {args.out}")
    return 0


def score_command(args: argparse.Namespace) -> int:
    metrics, disagreements = score_files(args.gold, args.predictions, args.split)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(args.disagreements, disagreements, DISAGREEMENT_FIELDS)
    subgroups = subgroup_scores(
        read_csv(args.gold), read_jsonl(args.predictions), args.split
    )
    write_csv(args.subgroups, subgroups, SUBGROUP_FIELDS)
    write_manifest(
        args.metrics,
        command="score",
        inputs=[args.gold, args.predictions],
        additional_outputs=[args.disagreements, args.subgroups],
        parameters={"split": args.split},
        counts={"scored_rows": int(metrics["scored_rows"])},
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    print(f"Disagreements: {args.disagreements}")
    return 0


def compare_command(args: argparse.Namespace) -> int:
    rows: list[dict[str, object]] = []
    for path in args.predictions:
        metrics, _ = score_files(args.gold, path, args.split)
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
    write_manifest(
        args.out,
        command="compare",
        inputs=[args.gold, *args.predictions],
        parameters={"split": args.split},
        counts={"runs": len(rows)},
    )
    print(f"Prompt runs compared: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def review_command(args: argparse.Namespace) -> int:
    source_registry, candidate_catalog = _context_paths(args)
    rows = prepare_review(
        args.workbook,
        args.predictions,
        source_registry,
        candidate_catalog,
    )
    write_csv(args.out, rows, REVIEW_FIELDS)
    write_manifest(
        args.out,
        command="prepare-review",
        workbook=args.workbook,
        inputs=[
            path
            for path in (args.predictions, source_registry, candidate_catalog)
            if path
        ],
        counts={"review_rows": len(rows)},
    )
    print(f"Review rows: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def export_command(args: argparse.Namespace) -> int:
    rows = approved_patches(read_csv(args.review))
    write_csv(args.out, rows, PATCH_FIELDS)
    write_manifest(
        args.out,
        command="export",
        inputs=[args.review],
        counts={
            "patches": len(rows),
            "updates": sum(row["operation"] == "update" for row in rows),
            "deletions": sum(row["operation"] == "delete" for row in rows),
        },
    )
    print(f"Approved patches: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def source_registry_command(args: argparse.Namespace) -> int:
    rows = source_registry_template(args.workbook, args.candidate_catalog)
    write_csv(args.out, rows, SOURCE_REGISTRY_FIELDS)
    write_manifest(
        args.out,
        command="prepare-source-registry",
        workbook=args.workbook,
        inputs=[args.candidate_catalog] if args.candidate_catalog else [],
        counts={"benchmarks": len(rows)},
    )
    print(f"Source registry rows: {len(rows)}")
    print(f"Output: {args.out}")
    return 0


def human_agreement_command(args: argparse.Namespace) -> int:
    metrics = human_agreement(read_csv(args.gold))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_manifest(
        args.out,
        command="human-agreement",
        inputs=[args.gold],
        counts={"double_annotated_rows": int(metrics["double_annotated_rows"])},
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


def id_repairs_command(args: argparse.Namespace) -> int:
    rows = duplicate_edge_id_repairs(args.workbook)
    write_csv(args.out, rows, ID_REPAIR_FIELDS)
    write_manifest(
        args.out,
        command="prepare-id-repairs",
        workbook=args.workbook,
        counts={"repairs": len(rows)},
    )
    print(f"Duplicate edge ID repairs: {len(rows)}")
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
    _add_context_arguments(audit)
    audit.set_defaults(handler=audit_command)

    gold = subparsers.add_parser(
        "prepare-gold", help="create a stratified manual annotation set"
    )
    gold.add_argument("--workbook", type=Path, required=True)
    gold.add_argument("--size", type=int, default=90)
    gold.add_argument("--seed", type=int, default=20260624)
    gold.add_argument("--include-collisions", action="store_true")
    gold.add_argument("--include-non-model", action="store_true")
    gold.add_argument("--allow-metadata-only", action="store_true")
    _add_context_arguments(gold)
    gold.add_argument("--out", type=Path, default=Path("gold/gold_edges.csv"))
    gold.set_defaults(handler=prepare_gold_command)

    all_rows = subparsers.add_parser(
        "prepare-all", help="prepare all unambiguous mapping edges"
    )
    all_rows.add_argument("--workbook", type=Path, required=True)
    all_rows.add_argument("--include-collisions", action="store_true")
    all_rows.add_argument("--include-non-model", action="store_true")
    all_rows.add_argument("--allow-metadata-only", action="store_true")
    _add_context_arguments(all_rows)
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
    run.add_argument("--allow-metadata-only", action="store_true")
    run.set_defaults(handler=run_command)

    score = subparsers.add_parser(
        "score", help="score one prediction run against gold labels"
    )
    score.add_argument("--gold", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--metrics", type=Path, default=Path("outputs/metrics.json"))
    score.add_argument("--split", choices=("development", "test", "all"), default="all")
    score.add_argument(
        "--disagreements", type=Path, default=Path("outputs/disagreements.csv")
    )
    score.add_argument(
        "--subgroups", type=Path, default=Path("outputs/subgroup_metrics.csv")
    )
    score.set_defaults(handler=score_command)

    compare = subparsers.add_parser(
        "compare", help="compare multiple prompt or model runs"
    )
    compare.add_argument("--gold", type=Path, required=True)
    compare.add_argument("predictions", type=Path, nargs="+")
    compare.add_argument(
        "--split", choices=("development", "test", "all"), default="development"
    )
    compare.add_argument(
        "--out", type=Path, default=Path("outputs/prompt_comparison.csv")
    )
    compare.set_defaults(handler=compare_command)

    review = subparsers.add_parser(
        "prepare-review", help="combine predictions with current mappings"
    )
    review.add_argument("--workbook", type=Path, required=True)
    review.add_argument("--predictions", type=Path, required=True)
    _add_context_arguments(review)
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

    registry = subparsers.add_parser(
        "prepare-source-registry",
        help="create a benchmark source-verification template",
    )
    registry.add_argument("--workbook", type=Path, required=True)
    registry.add_argument("--candidate-catalog", type=Path)
    registry.add_argument(
        "--out", type=Path, default=Path("sources/benchmark_sources.csv")
    )
    registry.set_defaults(handler=source_registry_command)

    agreement = subparsers.add_parser(
        "human-agreement", help="score independent annotator agreement"
    )
    agreement.add_argument("--gold", type=Path, required=True)
    agreement.add_argument(
        "--out", type=Path, default=Path("outputs/human_agreement.json")
    )
    agreement.set_defaults(handler=human_agreement_command)

    repairs = subparsers.add_parser(
        "prepare-id-repairs",
        help="propose unique keys for repeated mapping edge IDs",
    )
    repairs.add_argument("--workbook", type=Path, required=True)
    repairs.add_argument(
        "--out", type=Path, default=Path("outputs/duplicate_edge_id_repairs.csv")
    )
    repairs.set_defaults(handler=id_repairs_command)
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
