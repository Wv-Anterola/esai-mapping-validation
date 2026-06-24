# Work package: Mapping validation

Owner: Wilber ("can complete my work"). Window: 17.06.2026 - 24.06.2026.
Status: not started (scaffold only).

## Goal (from the project doc)

Validate and correct the assignment of benchmarks to risks: the
`benchmark_measures_harm` relation in the workbook. This is distinct from the paper QC
in `../systematic-benchmark-collection/` (which checks that a collected paper is a real,
unique benchmark). Here we check whether a benchmark actually measures the harm it is
mapped to, and at the strength claimed.

## Todos (from the doc)

1. Manually label a small set of benchmark-to-risk edges, following the workbook coding
   instructions (strength: direct / strong-proxy / weak-proxy / contested; basis;
   confidence). This is the gold set.
2. Write good LLM prompts that reproduce the coding instructions.
3. Run the prompts on the small set; record kappa / agreement against the gold labels;
   compare prompt variants.
4. Once agreement is acceptable, run on all benchmark-to-harm edges.
5. Combine the LLM output with what is already mapped, flagging disagreements for review.

## Pointers / reuse

- Coding instructions and strength definitions: the "Ontology" section of the project doc
  (`references/...mapping policies to benchmarks.docx`), and `esai-work/4-team-tools/`
  (`mapping-validation-prompt.md`, `how-to-add-rows.md`).
- Inputs: the `bench_measures_harm` and `benchmarks` / `harms` sheets of the workbook.
- The candidate set from collection (`../systematic-benchmark-collection/outputs/`) feeds
  the benchmarks side once those papers are coded into the workbook.
- Use Claude (Opus 4.8) for the LLM labelling; keep prompts and gold labels under version
  control so kappa is reproducible.

## Suggested layout (when building)

    prompts/            # versioned LLM prompts
    gold/               # hand-labelled gold set (small)
    validate_mapping.py # run prompts, score kappa, output disagreements
    outputs/            # scores + disagreement reports (gitignored)
