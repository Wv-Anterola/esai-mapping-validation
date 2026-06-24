import json

from mapping_validation.provenance import sha256_file, write_manifest


def test_manifest_hashes_workbook_input_and_output(tmp_path) -> None:
    workbook = tmp_path / "workbook.xlsx"
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    workbook.write_bytes(b"workbook")
    source.write_text("input\n", encoding="utf-8")
    output.write_text("output\n", encoding="utf-8")
    secondary = tmp_path / "secondary.csv"
    secondary.write_text("secondary\n", encoding="utf-8")

    manifest = write_manifest(
        output,
        command="test",
        workbook=workbook,
        inputs=[source],
        additional_outputs=[secondary],
        counts={"rows": 1},
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["workbook"]["sha256"] == sha256_file(workbook)
    assert payload["inputs"][0]["sha256"] == sha256_file(source)
    assert payload["output_sha256"] == sha256_file(output)
    assert payload["additional_outputs"][0]["sha256"] == sha256_file(secondary)
