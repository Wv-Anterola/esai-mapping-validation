# Better mapping plan

## Current validated workflow

The package already supports validating existing `bench_measures_harm` edges:

1. deterministic workbook audit;
2. verified benchmark-source registry;
3. stratified gold set with two independent human labels;
4. prompt/model scoring against the gold set;
5. human-reviewed tracker patch export.

This is the right workflow for correcting existing edges because it preserves provenance and does
not let a model directly edit the tracker.

## Missing-edge discovery

Validation of existing edges does not find harms that were never mapped. Add a second pass:

1. For each benchmark, build a compact packet with title, source abstract, task, metric,
   communicated metric, current mapped harms, and a taxonomy excerpt.
2. Run `prompts/harm_candidate_selection_v1.txt` to propose at most five candidate harms.
3. Drop candidates already present in `bench_measures_harm`.
4. Human-review only the remaining candidate edges.
5. Promote accepted rows into the normal validation workflow before tracker import.

This keeps generation and validation separate. Candidate generation optimizes recall; the
validation prompt optimizes precision.

## Mapping quality upgrades

- Use `prompts/rubric_v3_mapping_validator.txt` for future model runs. It adds explicit
  counterexamples and a stronger distinction between model behavior and downstream societal
  outcomes.
- Treat downstream harms such as labor-market effects, polarization, or concentration of power as
  proxy mappings unless the benchmark source validates against a downstream outcome.
- Require a named `source_match_method` for every model-run input: `benchmark-id-registry`,
  `exact-normalized-title`, or `catalog-conservative-title-alias`.
- Keep `strength=none` as a valid adjudicated result, then export it as a delete operation only
  after human approval.
- Report subgroup metrics by harm domain and current strength to catch systematic overrating of
  weak proxies.

## Presentation-ready status

Current hardened outputs show that the validation framework is operational:

- `outputs/hardened/all_edges.csv`: 1,387 unambiguous model-benchmark edges prepared for model
  input.
- `outputs/hardened/gold_edges.csv`: 90-row gold template, split into 60 development and 30 test
  rows.
- `outputs/hardened/deterministic_issues.csv`: workbook audit for duplicate IDs, missing sources,
  ambiguous benchmark IDs, non-model evidence, and basis/strength issues.
- `outputs/hardened/duplicate_edge_id_repairs.csv`: row-addressed proposal for duplicate edge IDs.

The main blocker before a full model run is source verification. Existing outputs contain many
source-missing flags, so agreement scores should not be presented as complete until benchmark
sources are verified or deliberately marked metadata-only for diagnostics.
