"""CLI for comparing a prediction CSV with isolated canonical sample output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from audit_agent.evaluation import compare_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate sample predictions without exposing labels to prediction code")
    parser.add_argument("prediction", type=Path)
    parser.add_argument("canonical", type=Path)
    args = parser.parse_args()
    metrics = compare_outputs(args.prediction, args.canonical)
    print(json.dumps({
        "cases": metrics.cases,
        "status_accuracy": metrics.status_accuracy,
        "exact_row_accuracy": metrics.exact_row_accuracy,
        "step_precision": metrics.step_precision,
        "step_recall": metrics.step_recall,
        "step_f1": metrics.step_f1,
        "field_accuracy": metrics.field_accuracy,
        "sequence_accuracy": metrics.sequence_accuracy,
        "per_field": metrics.per_field,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
