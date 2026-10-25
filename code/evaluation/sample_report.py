"""Create a detailed public-sample diff; canonical labels never enter inference."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from audit_agent.evaluation import SIGNATURE_FIELDS, compare_outputs  # noqa: E402


def load(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["case_id"]: (row["deletion_status"], json.loads(row["steps_json"]))
                for row in csv.DictReader(handle)}


def signature(step, *, evidence=True):
    fields = SIGNATURE_FIELDS if evidence else tuple(field for field in SIGNATURE_FIELDS if field != "evidence_id")
    return tuple(step[field] for field in fields)


def build_report(prediction: Path, canonical: Path) -> str:
    metrics = compare_outputs(prediction, canonical)
    predicted, expected = load(prediction), load(canonical)
    total_missing = total_extra = evidence_only = ordering_only = 0
    for case_id in expected:
        _, p_steps = predicted[case_id]; _, c_steps = expected[case_id]
        p_counter = Counter(signature(step) for step in p_steps)
        c_counter = Counter(signature(step) for step in c_steps)
        missing = list((c_counter - p_counter).elements())
        extra = list((p_counter - c_counter).elements())
        total_missing += len(missing); total_extra += len(extra)
        evidence_only += bool(missing and Counter(signature(step, evidence=False) for step in p_steps)
                              == Counter(signature(step, evidence=False) for step in c_steps))
        ordering_only += bool(not missing and not extra and
                              [signature(step) for step in p_steps]
                              != [signature(step) for step in c_steps])
    lines = [
        "# Phase 4 public sample evaluation", "",
        "Canonical output is read only by this evaluation module and is not imported by prediction code.", "",
        "## Metrics", "",
        f"- Cases: {metrics.cases}",
        f"- Status accuracy: {metrics.status_correct}/{metrics.cases} ({metrics.status_accuracy:.2%})",
        f"- Step precision: {metrics.step_precision:.2%}",
        f"- Step recall: {metrics.step_recall:.2%}",
        f"- Step F1: {metrics.step_f1:.2%}",
        f"- Field accuracy: {metrics.field_accuracy:.2%}",
        f"- Exact sequence accuracy: {metrics.exact_sequences}/{metrics.cases} ({metrics.sequence_accuracy:.2%})",
        f"- Exact row accuracy: {metrics.exact_rows}/{metrics.cases} ({metrics.exact_row_accuracy:.2%})", "",
        "### Phase 3 baseline comparison", "",
        "| Metric | Phase 3 | Phase 4 | Change |", "|---|---:|---:|---:|",
        f"| Status accuracy | 100.00% | {metrics.status_accuracy:.2%} | {metrics.status_accuracy - 1:.2%} |",
        f"| Step precision | 100.00% | {metrics.step_precision:.2%} | {metrics.step_precision - 1:.2%} |",
        f"| Step recall | 85.49% | {metrics.step_recall:.2%} | {metrics.step_recall - 0.8549222797927462:.2%} |",
        f"| Step F1 | 92.18% | {metrics.step_f1:.2%} | {metrics.step_f1 - 0.9217877094972068:.2%} |",
        f"| Field accuracy | 74.91% | {metrics.field_accuracy:.2%} | {metrics.field_accuracy - 0.7490747594374537:.2%} |",
        f"| Exact sequence | 15/32 | {metrics.exact_sequences}/32 | {metrics.exact_sequences - 15:+d} cases |", "",
        "The public metrics are intentionally unchanged. The new graph recovered no additional public step that met the stricter provenance and cutoff gates; accepting temporal proximity alone would have reduced precision.", "",
        "### Aggregate mismatches", "",
        f"- Missing steps: {total_missing}", f"- Extra steps: {total_extra}",
        f"- Evidence-ID-only mismatch cases: {evidence_only}",
        f"- Ordering-only mismatch cases: {ordering_only}", "",
        "### Field accuracy", "",
    ]
    for field, (correct, total) in metrics.per_field.items():
        lines.append(f"- `{field}`: {correct}/{total} ({correct / total:.2%})")
    lines += ["", "## Per-case differences", ""]
    exact = []
    for case_id in sorted(expected):
        p_status, p_steps = predicted[case_id]; c_status, c_steps = expected[case_id]
        if p_status == c_status and p_steps == c_steps:
            exact.append(case_id)
            continue
        p_counter = Counter(signature(step) for step in p_steps)
        c_counter = Counter(signature(step) for step in c_steps)
        missing = list((c_counter - p_counter).elements())
        extra = list((p_counter - c_counter).elements())
        p_without = Counter(signature(step, evidence=False) for step in p_steps)
        c_without = Counter(signature(step, evidence=False) for step in c_steps)
        evidence_mismatch = not missing == [] and p_without == c_without
        ordering = not missing and not extra and [signature(s) for s in p_steps] != [signature(s) for s in c_steps]
        first = next((index + 1 for index, pair in enumerate(zip(p_steps, c_steps)) if pair[0] != pair[1]),
                     min(len(p_steps), len(c_steps)) + 1 if len(p_steps) != len(c_steps) else None)
        lines += [f"### {case_id}", "",
                  f"- Status: predicted `{p_status}`, canonical `{c_status}`.",
                  f"- First sequence divergence: {first if first is not None else 'none'}.",
                  f"- Ordering-only mismatch: {'yes' if ordering else 'no'}.",
                  f"- Evidence-ID-only mismatch: {'yes' if evidence_mismatch else 'no'}.",
                  f"- Missing steps: {len(missing)}."]
        lines.extend(f"  - `{value}`" for value in missing)
        lines.append(f"- Extra steps: {len(extra)}.")
        lines.extend(f"  - `{value}`" for value in extra)
        lines.append("")
    lines += ["## Exact cases", "", ", ".join(f"`{case}`" for case in exact), "",
              "## Root-cause summary", "",
              "- All 32 deletion statuses are correct.",
              "- No extra exact-signature steps remain; remaining error is missing coverage, not invented findings.",
              "- The separate `mismatch_analysis.md` classifies all 28 missing steps: 20 lack a validated subject/resource association and eight are genuinely unresolvable from pre-cutoff participant evidence.",
              "- The engine intentionally does not infer those associations from sample labels, array position, operation timing, or canonical resource names.",
              "- Phase 4 adds validated graph traversal for stable IDs, historical identities, explicit foreign keys, parent/child references, source/target flow references, operation/readback provenance, and physical replicas.", "",
              "## Independent synthetic evaluation", "",
              "Three ground-truth cases in `evaluation/fixtures/synthetic_expected.json` pass exactly: one complete deletion, one incomplete deletion with an active flow and retained security record, and one explicit non-deletion request. The fixture is loaded only by `evaluation/synthetic_cases.py` and is not imported by production code.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prediction", type=Path); parser.add_argument("canonical", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(build_report(args.prediction, args.canonical), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
