# Gold annotations

Gold CSV files in this directory are version-controlled evaluation data.

Create the initial file with `esai-validate prepare-gold`, complete it using
`ANNOTATION_GUIDE.md`, and commit the completed annotations before running prompt comparisons.
Do not replace human labels with current tracker values or model predictions.

When a label changes, use a focused commit whose message identifies the annotation correction.
Keep raw model predictions under `outputs/`; they are not gold data.

