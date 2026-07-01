# ESAI mapping validation

This repository validates the workbook's `bench_measures_harm` relation and prepares reviewed,
tracker-ready corrections. It separates deterministic data checks, source verification, independent
human annotation, model evaluation, and final human approval.

The workflow never edits a workbook. Every generated artifact has a SHA-256 manifest, and the
final outputs are explicit `update` or `delete` operations keyed by `edge_id`.

## Installation

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
```

No API key is needed for auditing, source preparation, annotation, scoring, review, or export. The
optional Anthropic dependency and `ANTHROPIC_API_KEY` are used only if the later model-run command
is selected:

```bash
python -m pip install -e ".[anthropic,dev]"
```

## 1. Audit the current mapping

Use a fresh workbook export, not a previously downloaded copy:

```bash
esai-validate audit \
  --workbook "path/to/workbook.xlsx" \
  --candidate-catalog "path/to/benchmark_candidates.csv" \
  --source-registry sources/benchmark_sources.csv \
  --out outputs/deterministic_issues.csv
```

The audit reports ID collisions, dangling IDs, invalid enum values, missing source or benchmark
metadata, missing harm descriptions, out-of-scope evidence types, and label combinations that
require review. A sidecar manifest records hashes for the workbook, inputs, and output.

Repeated edge IDs can be converted into a row-addressed tracker repair proposal. The first
workbook occurrence retains its key; later occurrences receive unused IDs following the existing
prefix and numeric convention:

```bash
esai-validate prepare-id-repairs \
  --workbook "path/to/workbook.xlsx" \
  --out outputs/duplicate_edge_id_repairs.csv
```

Review and apply these key repairs before creating the gold set. Benchmark-ID collisions cannot be
split mechanically because their mapping rows do not identify which colliding benchmark title was
intended; the tracker owner must resolve those separately.

## 2. Resolve benchmark sources

Create a source registry from the workbook:

```bash
esai-validate prepare-source-registry \
  --workbook "path/to/workbook.xlsx" \
  --candidate-catalog "path/to/benchmark_candidates.csv" \
  --out sources/benchmark_sources.csv
```

Fill `source_url` and `source_abstract`, then change `source_status` from `pending` to `verified`
only after checking the benchmark identity. A collection catalog can also supply source metadata
when its normalized paper title exactly matches the tracker title or the collection pipeline has
recorded one unique conservative title alias. The recorded match method is preserved. Registry
entries take precedence. Unverified registry entries are never treated as source-grounded.

Do not begin semantic annotation or a model run while relevant rows remain
`benchmark_source_missing` or `benchmark_metadata_incomplete` in the audit.
`prepare-gold`, `prepare-all`, and `run` enforce source-grounded inputs by default.
`--allow-metadata-only` exists only to generate diagnostic work queues; do not use such output for
agreement estimates or tracker decisions.

## 3. Create and label the gold set

```bash
esai-validate prepare-gold \
  --workbook "path/to/workbook.xlsx" \
  --candidate-catalog "path/to/benchmark_candidates.csv" \
  --source-registry sources/benchmark_sources.csv \
  --size 90 \
  --seed 20260624 \
  --out gold/gold_edges.csv
```

The default sample contains model benchmarks only, excludes colliding IDs, balances current
strength and harm domain, and includes at most one edge per benchmark. It assigns a fixed
development/test split. Use `--include-non-model` only with a separate evidence-type-specific
rubric; use `--include-collisions` only after the ambiguous identity has been resolved.

Two reviewers independently complete the `annotator_a_*` and `annotator_b_*` fields without
seeing model output. Record agreement before adjudication:

```bash
esai-validate human-agreement \
  --gold gold/gold_edges.csv \
  --out outputs/human_agreement.json
```

After adjudication, complete the `gold_*` fields and set `annotation_status=complete`. See
[ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md).

## 4. Evaluate prompt variants

Model execution is a later, optional stage. Each prompt/model pair must use a separate output
file. Runs are resumable and record the exact model, prompt hash, timestamp, parsed fields, raw
response, and parse error.

```bash
set ANTHROPIC_API_KEY=...

esai-validate run \
  --input gold/gold_edges.csv \
  --prompt prompts/rubric_v3_mapping_validator.txt \
  --model "provider-model-id" \
  --out outputs/gold_rubric_v3.jsonl
```

Compare variants on the development split only:

```bash
esai-validate score \
  --gold gold/gold_edges.csv \
  --predictions outputs/gold_rubric_v3.jsonl \
  --split development \
  --metrics outputs/rubric_v3_metrics.json

esai-validate compare \
  --gold gold/gold_edges.csv \
  --split development \
  outputs/gold_rubric_v2.jsonl outputs/gold_rubric_v3.jsonl \
  --out outputs/prompt_comparison.csv
```

Lock the selected prompt and model before scoring the test split. The predeclared acceptance
criteria are in [METHODOLOGY.md](METHODOLOGY.md).

`prompts/harm_candidate_selection_v1.txt` is a separate, recall-oriented prompt for discovering
missing candidate edges. It should not be scored as a validator and should not directly produce
tracker patches. See [MAPPING_IMPROVEMENTS.md](MAPPING_IMPROVEMENTS.md).

## 5. Validate all eligible edges and prepare tracker changes

```bash
esai-validate prepare-all \
  --workbook "path/to/workbook.xlsx" \
  --candidate-catalog "path/to/benchmark_candidates.csv" \
  --source-registry sources/benchmark_sources.csv \
  --out outputs/all_edges.csv

esai-validate run \
  --input outputs/all_edges.csv \
  --prompt prompts/rubric_v3_mapping_validator.txt \
  --model "provider-model-id" \
  --out outputs/all_predictions.jsonl

esai-validate prepare-review \
  --workbook "path/to/workbook.xlsx" \
  --predictions outputs/all_predictions.jsonl \
  --candidate-catalog "path/to/benchmark_candidates.csv" \
  --source-registry sources/benchmark_sources.csv \
  --out outputs/tracker_mapping_review.csv
```

Every proposed change requires human review. Approved rows must have a named reviewer and a
rationale. Export produces tracker-compatible updates; a reviewed `strength=none` decision
becomes an explicit delete operation.

```bash
esai-validate export \
  --review outputs/tracker_mapping_review.csv \
  --out outputs/tracker_patch.csv
```

## Development

```bash
ruff format --check mapping_validation tests
ruff check mapping_validation tests
pytest
```

Source workbooks, model outputs, and patches are ignored by Git. Completed gold annotations and
verified source registries are version-controlled because they define the evaluation evidence.
