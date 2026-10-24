"""Sample evaluation metrics isolated from prediction code."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .errors import DataValidationError
from .models import EvaluationMetrics

STEP_FIELDS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")
SIGNATURE_FIELDS = ("phase", "system_id", "resource_id", "operation", "state", "evidence_id")
OUTPUT_COLUMNS = ("case_id", "deletion_status", "steps_json")


def _load(path: Path) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
            raise DataValidationError(f"{path}: expected columns {OUTPUT_COLUMNS}")
        result = {}
        for line_no, row in enumerate(reader, start=2):
            if row["case_id"] in result:
                raise DataValidationError(f"{path}:{line_no}: duplicate case_id {row['case_id']}")
            try:
                steps = json.loads(row["steps_json"])
            except json.JSONDecodeError as exc:
                raise DataValidationError(f"{path}:{line_no}: invalid steps_json: {exc}") from exc
            if not isinstance(steps, list) or any(not isinstance(item, dict) for item in steps):
                raise DataValidationError(f"{path}:{line_no}: steps_json must be an array of objects")
            for index, step in enumerate(steps, start=1):
                if set(step) != set(STEP_FIELDS):
                    raise DataValidationError(f"{path}:{line_no}: step {index} has invalid fields")
            result[row["case_id"]] = (row["deletion_status"], steps)
    return result


def _signature(step: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(step[field] for field in SIGNATURE_FIELDS)


def compare_outputs(prediction_path: Path, canonical_path: Path) -> EvaluationMetrics:
    predicted, canonical = _load(prediction_path), _load(canonical_path)
    if set(predicted) != set(canonical):
        missing = sorted(set(canonical) - set(predicted))
        extra = sorted(set(predicted) - set(canonical))
        raise DataValidationError(f"case mismatch: missing={missing}, extra={extra}")
    status_correct = exact_rows = exact_sequences = true_positive = 0
    predicted_steps = canonical_steps = field_correct = field_total = 0
    per_field: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case_id in sorted(canonical):
        p_status, p_steps = predicted[case_id]
        c_status, c_steps = canonical[case_id]
        status_correct += p_status == c_status
        p_sequence = [_signature(step) for step in p_steps]
        c_sequence = [_signature(step) for step in c_steps]
        exact_sequences += p_sequence == c_sequence
        exact_rows += p_status == c_status and p_steps == c_steps
        p_counter, c_counter = Counter(p_sequence), Counter(c_sequence)
        true_positive += sum((p_counter & c_counter).values())
        predicted_steps += len(p_steps)
        canonical_steps += len(c_steps)
        slots = max(len(p_steps), len(c_steps))
        for index in range(slots):
            p_step = p_steps[index] if index < len(p_steps) else None
            c_step = c_steps[index] if index < len(c_steps) else None
            for field in STEP_FIELDS:
                correct = p_step is not None and c_step is not None and p_step[field] == c_step[field]
                field_correct += correct
                field_total += 1
                per_field[field][0] += correct
                per_field[field][1] += 1
    return EvaluationMetrics(len(canonical), status_correct, exact_rows, exact_sequences, true_positive,
                             predicted_steps, canonical_steps, field_correct, field_total,
                             {key: tuple(value) for key, value in sorted(per_field.items())})
