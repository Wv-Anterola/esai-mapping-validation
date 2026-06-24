# Gold-set annotation guide

## Purpose

The gold set measures whether a prompt reproduces independent human judgments. It must not be
created by copying current labels or accepting model suggestions. Two people annotate
independently. Keep first-pass labels separate and adjudicate disagreements only after calculating
inter-rater agreement.

## Unit of annotation

One row is one `benchmark_id` to `harm_id` edge. Judge only whether that benchmark's scored task
and metric measure that harm, and at what strength. Do not judge whether the harm is important or
whether the benchmark is well designed in every other respect.

## Annotation steps

1. Confirm the benchmark identity and verified source. Stop if the ID is ambiguous or the source
   cannot be resolved.
2. Identify the evaluation task and metric from the source, not from the proposed mapping.
3. State the construct that a high or low score operationalizes.
4. Compare that construct with the harm label and description.
5. Test the inference distance using the strength definitions below.
6. Check whether the stated basis is supported.
7. Record a short reason that another reviewer can audit.

## Strength

- `direct`: the score is an instance of the harm or its defining capability. Describing a high
  score as the model doing the harmful thing requires no additional causal step.
- `strong-proxy`: the score captures a near-necessary component or precursor through a short,
  established chain with few important confounders.
- `weak-proxy`: the connection requires multiple assumptions or has substantial confounders.
- `contested`: the relationship is plausible but reasonably disputed.
- `none`: the benchmark does not measure this harm.

For societal outcomes, distinguish model capability from downstream realization. For example,
task automation capability may be evidence relevant to job displacement, but deployment,
adoption, substitution, and labor-market response remain additional causal steps.

## Basis

- `validated-against-downstream`: the source reports validation against an appropriate downstream
  outcome.
- `face-validity-only`: the relation is justified by construct similarity or mechanism without
  downstream validation.
- `known-non-correlation`: evidence shows the measure does not track the proposed outcome.

Do not infer validation from a benchmark title, venue, or popularity.

## Verdict

- `VALID`: source and mapping are defensible as coded.
- `DOWN-RATE`: the edge is relevant, but current strength is too strong.
- `UP-RATE`: the edge is relevant, but current strength is too weak.
- `REVISE-BASIS`: strength is defensible, but basis should change.
- `NOT-A-BENCHMARK`: the source does not contain an evaluation task and metric.
- `WRONG-HARM`: the evaluation measures a different construct.
- `INSUFFICIENT-EVIDENCE`: the available source information cannot support a reliable judgment.

## Completion requirements

Each reviewer fills their complete `annotator_a_*` or `annotator_b_*` field set, including name and
ISO review date. Partially completed reviewer records are rejected by the agreement command.

After agreement is recorded and disagreements are discussed, fill:

- `annotation_status=complete`;
- `gold_verdict`;
- `gold_strength`, including `none` where appropriate;
- `gold_basis`;
- `gold_reason`;
- `gold_adjudicator`;
- `gold_adjudicated_at` in ISO date format.
