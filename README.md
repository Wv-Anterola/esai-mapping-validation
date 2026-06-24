# ESAI mapping validation

This repository validates and prepares corrections for the workbook's `bench_measures_harm`
relation. It combines deterministic data checks, an independently labelled gold set, versioned
LLM prompts, agreement metrics, and mandatory human review.

The workflow never edits a workbook. Its final artifact is a reviewed patch CSV that can be
applied by the tracker owner.

## Installation

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
```

Install the optional Anthropic client only on the machine used for model runs:

```bash
python -m pip install -e ".[anthropic,dev]"
```

## 1. Audit the current mapping

```bash
esai-validate audit \
  --workbook "path/to/ESAI Harm-Bench-Legal Map.xlsx" \
  --out outputs/deterministic_issues.csv
```

This reports dangling IDs, ambiguous benchmark IDs, invalid strength or basis values, and
`direct` plus `face-validity-only` combinations that require review.

## 2. Create and label the gold set

```bash
esai-validate prepare-gold \
  --workbook "path/to/workbook.xlsx" \
  --size 60 \
  --seed 20260624 \
  --out gold/gold_edges.csv
```

The sample is stratified by current strength and evidence type. Colliding benchmark IDs are
excluded by default because the benchmark identity is ambiguous. Complete the `gold_*` fields
manually and set `annotation_status=complete`. Current labels are context, not gold labels.

See [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md) before annotating.

## 3. Run and compare prompt variants

No model name is hard-coded. Record the exact provider model identifier used for every run.

```bash
set ANTHROPIC_API_KEY=...

esai-validate run \
  --input gold/gold_edges.csv \
  --prompt prompts/rubric_v1.txt \
  --model "provider-model-id" \
  --out outputs/gold_rubric_v1.jsonl

esai-validate run \
  --input gold/gold_edges.csv \
  --prompt prompts/rubric_v2.txt \
  --model "provider-model-id" \
  --out outputs/gold_rubric_v2.jsonl
```

Runs are resumable. Each prediction records the model, prompt name, prompt SHA-256, timestamp,
parsed decision, raw response, and parsing error.

Score and compare the runs:

```bash
esai-validate score \
  --gold gold/gold_edges.csv \
  --predictions outputs/gold_rubric_v1.jsonl \
  --metrics outputs/rubric_v1_metrics.json \
  --disagreements outputs/rubric_v1_disagreements.csv

esai-validate compare \
  --gold gold/gold_edges.csv \
  outputs/gold_rubric_v1.jsonl outputs/gold_rubric_v2.jsonl \
  --out outputs/prompt_comparison.csv
```

Reported measures include verdict and strength accuracy, Cohen's kappa, macro F1, quadratic
weighted kappa for strength, basis agreement, missing predictions, and parse failures.

## 4. Validate all unambiguous edges

After selecting a prompt and model from the gold-set results:

```bash
esai-validate prepare-all \
  --workbook "path/to/workbook.xlsx" \
  --out outputs/all_edges.csv

esai-validate run \
  --input outputs/all_edges.csv \
  --prompt prompts/rubric_v1.txt \
  --model "provider-model-id" \
  --out outputs/all_predictions.jsonl
```

`prepare-all` excludes edges attached to colliding benchmark IDs by default. Resolve those IDs
before validation or opt in explicitly with `--include-collisions`.

## 5. Combine results with the tracker

```bash
esai-validate prepare-review \
  --workbook "path/to/workbook.xlsx" \
  --predictions outputs/all_predictions.jsonl \
  --out outputs/tracker_mapping_review.csv
```

Reviewers inspect the current and proposed labels, set `review_status=approved` where appropriate,
and add their name and notes. Export approved updates with:

```bash
esai-validate export \
  --review outputs/tracker_mapping_review.csv \
  --out outputs/tracker_patch.csv
```

The patch identifies `sheet=bench_measures_harm`, `operation=update`, `edge_id`, IDs, corrected
strength, basis, confidence, notes, and reviewer. A prediction of `strength=none` is not converted
into a deletion; removals require explicit tracker-owner handling.

## Development

```bash
ruff format --check mapping_validation tests
ruff check mapping_validation tests
pytest
```

Workbooks, gold annotations, model outputs, and tracker patches are ignored by Git.

