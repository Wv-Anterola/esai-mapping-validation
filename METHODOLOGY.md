# Validation methodology

## Design goals

The workflow is designed to answer a narrow question reproducibly: does a benchmark-to-harm edge
follow the project's coding rubric, and can a versioned prompt reproduce independent reviewer
labels well enough to assist with the remaining edges?

It does not measure construct validity of the benchmark itself, aggregate benchmark results, or
make legal-compliance determinations.

## Separation of checks

Deterministic integrity checks run before semantic validation. Edges with colliding benchmark IDs
are not suitable for semantic validation because an ID resolves to multiple sources. Invalid enum
values and direct/face-validity combinations enter a review queue but are not silently rewritten.

Semantic validation uses source metadata, benchmark task and metric, harm description, and current
edge labels. It returns a proposed label and reason. The model never writes the tracker.

## Gold set

The sampling algorithm is deterministic for a given workbook, size, and seed. It cycles across
strata defined by current strength and benchmark evidence type, preventing the largest class from
dominating the pilot. Ambiguous benchmark IDs are excluded by default.

Gold labels must be assigned independently by a person following `ANNOTATION_GUIDE.md`. Current
labels remain visible because reviewers need to assess whether they are defensible, but they are
not copied into the gold columns. Model predictions should not be shown to annotators before the
first-pass labels are complete.

If multiple human annotators are available, report their agreement before adjudication. Keep both
raw annotation files and document adjudication decisions outside the model prompt.

## Prompt comparison

Two prompt variants are versioned in `prompts/`. The first applies the coding rubric in a fixed
sequence. The second applies an evidence-first counterexample test. Each run records the prompt
file hash and exact model identifier, so editing a prompt creates a distinguishable experiment.

Prompt selection should consider:

- verdict accuracy, Cohen's kappa, and macro F1;
- exact and quadratic-weighted agreement on strength;
- basis agreement;
- class-specific disagreements;
- parse failures and missing results;
- stability across benchmark evidence types and harm domains.

The team should agree on acceptance criteria before inspecting final prompt results. A single
aggregate score should not hide systematic errors on rare or high-impact classes.

## Full-data run

Only the selected prompt/model combination is run on all unambiguous edges. Runs are append-only
JSONL and resumable by edge ID, prompt hash, and model. Invalid responses are retained with a parse
error rather than dropped.

Predictions are joined back to the current workbook by `edge_id`. Any proposed change, parse
failure, or explicit human-review flag enters `tracker_mapping_review.csv`.

## Tracker integration

Reviewers approve or reject each proposed change. The exporter validates enum values and writes an
update-oriented patch keyed by `edge_id`. It does not edit `.xlsx` files and does not translate a
`none` judgment into deletion. This preserves ownership and makes every applied change auditable.

The patch schema is:

`sheet, operation, edge_id, benchmark_id, harm_id, strength, basis, confidence, notes, reviewer`.

## Re-running

A new workbook export, prompt edit, or model change is a new validation run. Keep the workbook
hash, gold-set seed, prompt hash, model identifier, metrics, disagreements, and reviewed patch
together in the handoff. Never compare metrics across runs if the gold labels changed without
recording that change.

