"""Central deterministic output serializer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import CasePrediction
from .normalization import natural_id_key
from .validation import validate_predictions_structure

OUTPUT_COLUMNS = ("case_id", "deletion_status", "steps_json")


def output_rows(predictions: list[CasePrediction], expected_case_ids: list[str]) -> list[dict[str, str]]:
    validate_predictions_structure(predictions, expected_case_ids)
    rows = []
    for item in sorted(predictions, key=lambda value: natural_id_key(value.case_id)):
        rows.append({
            "case_id": item.case_id,
            "deletion_status": item.deletion_status,
            "steps_json": json.dumps([step.as_dict() for step in item.steps],
                                     ensure_ascii=False, separators=(",", ":")),
        })
    return rows


def write_output(path: Path, predictions: list[CasePrediction], expected_case_ids: list[str]) -> None:
    rows = output_rows(predictions, expected_case_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
