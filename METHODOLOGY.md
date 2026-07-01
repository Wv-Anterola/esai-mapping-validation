# Validation methodology

## Scope

The unit of analysis is one `benchmark_id` to `harm_id` edge. The question is whether the
benchmark's scored task and metric measure the named harm, and whether strength and evidentiary
basis follow the coding rubric. This workflow does not establish a benchmark's general construct
validity, aggregate benchmark scores, or make legal-compliance determinations.

The primary run is restricted to rows whose `evidence_type` is `model benchmark`. Empirical
studies, legal instruments, incident data, and other evidence types require different inference
rules and must be evaluated in separately reported runs. They are never silently mixed into the
model-benchmark agreement estimates.

Existing-edge validation and missing-edge discovery are separate tasks. Existing-edge validation
scores a proposed `benchmark_id` to `harm_id` relation. Missing-edge discovery may propose new
candidate relations, but those candidates must be reviewed and then validated through the same
edge-level workflow before tracker import.

## Preconditions

Deterministic integrity checks precede semantic validation. The following conditions block an
edge from annotation or model evaluation:

- a benchmark ID resolves to multiple benchmark rows or an edge ID is duplicated;
- the benchmark source URL or source abstract is unverified;
- the benchmark description, task, or metric is missing;
- a benchmark or harm ID is dangling;
- strength or basis falls outside the controlled vocabulary.

The current tracker label is context, not evidence. Source metadata must come from the verified
source registry, an exact normalized-title catalog match, or a unique conservative alias already
recorded by the systematic collection pipeline. The model and human reviewers may not fill
missing evidence from memory.

## Gold-set design

Sampling is deterministic for a workbook hash, sample size, and seed. Rows are stratified by
current strength and harm domain. Each benchmark appears at most once, preventing benchmark-level
information from leaking across development and test rows. A request larger than the number of
eligible unique benchmarks fails instead of silently returning a smaller or dependent sample.
Colliding benchmark IDs and non-model evidence are excluded by default.

Within each stratum, approximately two thirds of rows are assigned to `development` and one third
to `test`. Prompt iteration and model selection use development rows only. Test labels remain
hidden until the prompt and exact model identifier are locked.

Two reviewers independently complete their annotation columns using the same source record and
annotation guide. Cohen's kappa is reported for verdict, strength, and basis, with quadratic
weighted kappa for ordinal strength. Disagreements are adjudicated into the final `gold_*` fields
only after raw agreement is recorded. Gold corrections remain in version control with a reasoned
commit.

## Prompt evaluation

Each prediction states the scored construct, source evidence used, number of inference steps,
verdict, corrected strength and basis, confidence, rationale, and whether human review is needed.
The output also records the exact prompt hash and model identifier. Mixed prompt/model runs and
duplicate edge IDs are rejected rather than collapsed during scoring.

The following acceptance criteria are fixed before inspecting the test split:

- 100% prediction coverage and no unparsed responses;
- verdict Cohen's kappa of at least 0.70;
- verdict macro F1 of at least 0.75;
- quadratic weighted kappa of at least 0.70 for strength;
- no recurring error pattern that systematically converts downstream societal outcomes into
  direct model measurements;
- manual inspection of every development disagreement and all reported subgroup metrics.

These thresholds determine whether the system may be used to populate a review queue. They do
not authorize automatic tracker changes. If the locked run fails the test criteria, revise on the
development split and evaluate a newly reserved test set; do not tune against the failed test
labels.

## Full-data run and tracker integration

Only the locked prompt/model combination is run on all unambiguous model-benchmark edges. A
handoff is incomplete if the audit still reports blocking source or metadata issues. Predictions
are append-only and resumable for the same prompt hash and model.

Every proposed change, parse failure, or explicit review flag enters the review CSV. Reviewers
approve or reject each row. The exporter requires a named reviewer and rationale and emits:

`sheet, operation, edge_id, benchmark_id, harm_id, strength, basis, confidence, notes, reviewer`.

`operation=update` changes the coded relation. `operation=delete` removes an edge adjudicated as
`strength=none`. The exporter never edits the workbook and never invents a new edge ID.

For missing-edge discovery, the exporter is not used directly. Accepted candidate edges first need
tracker-owner IDs and source verification, then enter a normal validation run.

## Reproducibility

Every command writes a sidecar manifest containing the command, timestamp, package version, Git
commit and dirty state, input hashes, output hash, workbook hash where applicable, parameters,
and record counts. Keep the gold file, source registry, prompt, predictions, metrics,
disagreements, subgroup metrics, review CSV, patch, and their manifests together for handoff.
