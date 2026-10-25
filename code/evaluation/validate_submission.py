"""Independently reopen and validate a generated submission CSV."""

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

from audit_agent.errors import DataValidationError  # noqa: E402
from audit_agent.identity import IdentityGraph  # noqa: E402
from audit_agent.ingestion import ingest_evidence  # noqa: E402
from audit_agent.loaders import (load_activity, load_evidence_manifest, load_identities,  # noqa: E402
                                 load_identity_events, load_requests)
from audit_agent.models import AuditStep, EvidenceCitation  # noqa: E402
from audit_agent.normalization import natural_id_key  # noqa: E402
from audit_agent.ordering import order_steps  # noqa: E402
from audit_agent.provenance import ProvenanceValidator  # noqa: E402
from audit_agent.serialization import OUTPUT_COLUMNS  # noqa: E402

STEP_FIELDS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}


def validate(path: Path, dataset: Path) -> dict[str, object]:
    requests = load_requests(dataset / "deletion_requests.csv")
    expected_ids = [item.case_id for item in requests]
    request_by_id = {item.case_id: item for item in requests}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
            raise DataValidationError(f"invalid header: {reader.fieldnames}")
        rows = list(reader)
    actual_ids = [row["case_id"] for row in rows]
    if len(rows) != 518 or len(set(actual_ids)) != 518:
        raise DataValidationError("submission must contain 518 unique data rows")
    if actual_ids != sorted(expected_ids, key=natural_id_key):
        raise DataValidationError("case IDs are missing, extra, or not naturally sorted")

    identities = load_identities(dataset / "user_identities.csv")
    identity_events = load_identity_events(dataset / "user_audit_log.csv")
    graph = IdentityGraph(identities, identity_events)
    activities = load_activity(dataset / "system_activity.csv")
    manifest = load_evidence_manifest(dataset / "evidence_files.csv", dataset)
    ingestion = ingest_evidence(manifest, identity_graph=graph)
    provenance = ProvenanceValidator(manifest, activities, identity_events, ingestion.store)

    statuses: Counter[str] = Counter()
    step_count = 0
    cited_count = 0
    for line_no, row in enumerate(rows, 2):
        case_id = row["case_id"]
        status = row["deletion_status"]
        statuses[status] += 1
        if status not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}:
            raise DataValidationError(f"line {line_no}: invalid deletion_status {status}")
        try:
            raw_steps = json.loads(row["steps_json"])
        except json.JSONDecodeError as exc:
            raise DataValidationError(f"line {line_no}: invalid steps_json: {exc}") from exc
        if not isinstance(raw_steps, list):
            raise DataValidationError(f"line {line_no}: steps_json is not an array")
        if status == "NOT_APPLICABLE" and raw_steps:
            raise DataValidationError(f"line {line_no}: NOT_APPLICABLE must have []")
        steps = []
        for index, raw in enumerate(raw_steps, 1):
            if not isinstance(raw, dict) or set(raw) != STEP_FIELDS:
                raise DataValidationError(f"line {line_no}, step {index}: invalid fields")
            if raw["step_no"] != index:
                raise DataValidationError(f"line {line_no}, step {index}: non-consecutive step_no")
            step = AuditStep(**raw)
            steps.append(step)
            future = status == "INCOMPLETE" and step.phase in {"REMEDIATION", "VERIFICATION"}
            if future and step.evidence_id:
                raise DataValidationError(f"line {line_no}, step {index}: future step cites evidence")
            if (step.phase == "FINDING" or status == "COMPLETE") and not step.evidence_id:
                raise DataValidationError(f"line {line_no}, step {index}: evidence is required")
            if step.evidence_id:
                cited_count += 1
                result = provenance.validate_citation(EvidenceCitation(
                    step.evidence_id, step.resource_id, request_by_id[case_id].audit_at))
                if not result.valid:
                    codes = ",".join(issue.code for issue in result.issues)
                    raise DataValidationError(
                        f"line {line_no}, step {index}: invalid evidence {step.evidence_id}: {codes}")
        if tuple(steps) != order_steps(steps):
            raise DataValidationError(f"line {line_no}: steps are not canonically ordered")
        step_count += len(steps)
    return {
        "rows": len(rows), "unique_case_ids": len(set(actual_ids)),
        "steps": step_count, "cited_steps": cited_count,
        "status_distribution": dict(sorted(statuses.items())),
        "evidence_files": ingestion.coverage.manifest_files,
        "observations": ingestion.coverage.usable_observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--dataset", type=Path, default=CODE_ROOT.parent / "dataset")
    args = parser.parse_args()
    print(json.dumps(validate(args.output.resolve(), args.dataset.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
