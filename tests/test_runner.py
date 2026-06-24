from pathlib import Path

from mapping_validation.io import read_jsonl, write_csv
from mapping_validation.runner import parse_response, run_predictions
from mapping_validation.schema import CONTEXT_FIELDS
from mapping_validation.workbook import load_context

RESPONSE = """{
  "verdict": "DOWN-RATE",
  "corrected_strength": "weak-proxy",
  "corrected_basis": "face-validity-only",
  "reason": "The score is separated from the harm by an additional causal step.",
  "confidence": "possible",
  "needs_human_review": true
}"""


class FakeClient:
    def complete(self, *, model: str, system: str, prompt: str) -> str:
        assert model == "test-model"
        assert "MAPPING RECORD" in prompt
        return RESPONSE


def test_parse_response_validates_schema() -> None:
    parsed = parse_response(f"```json\n{RESPONSE}\n```")
    assert parsed["verdict"] == "DOWN-RATE"
    assert parsed["needs_human_review"] is True


def test_prediction_run_is_resumable(workbook: Path, tmp_path: Path) -> None:
    input_path = tmp_path / "edges.csv"
    prompt_path = tmp_path / "prompt.txt"
    output_path = tmp_path / "predictions.jsonl"
    rows = load_context(workbook).head(1).to_dict(orient="records")
    write_csv(input_path, rows, CONTEXT_FIELDS)
    prompt_path.write_text("Review this mapping and return JSON.", encoding="utf-8")

    first = run_predictions(
        input_path=input_path,
        prompt_path=prompt_path,
        model="test-model",
        output_path=output_path,
        client=FakeClient(),
    )
    second = run_predictions(
        input_path=input_path,
        prompt_path=prompt_path,
        model="test-model",
        output_path=output_path,
        client=FakeClient(),
    )

    assert first == (1, 0)
    assert second == (0, 1)
    assert len(read_jsonl(output_path)) == 1
