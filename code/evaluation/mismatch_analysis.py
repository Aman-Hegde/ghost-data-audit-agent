"""Classify public-sample mismatches without feeding labels into prediction logic."""

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

from audit_agent.evaluation import SIGNATURE_FIELDS  # noqa: E402
from audit_agent.identity import IdentityGraph  # noqa: E402
from audit_agent.ingestion import ingest_evidence  # noqa: E402
from audit_agent.linking import ResourceLinker  # noqa: E402
from audit_agent.loaders import (load_activity, load_evidence_manifest, load_identities,  # noqa: E402
                                 load_identity_events, load_requests)
from audit_agent.models import EvidenceNature, IdentifierKind  # noqa: E402
from audit_agent.policy import canonical_category  # noqa: E402
from audit_agent.provenance import ProvenanceValidator  # noqa: E402
from audit_agent.temporal import observation_usable_at  # noqa: E402

CATEGORIES = (
    "Missing resource associations",
    "Identifier-free retained records",
    "Missing historical identity relationships",
    "Missing active-flow or restore dependencies",
    "Temporal reconstruction errors",
    "Policy interpretation errors",
    "Verification coverage errors",
    "Evidence-selection errors",
    "Other genuinely unresolvable associations",
)


def _load_output(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["case_id"]: (row["deletion_status"], json.loads(row["steps_json"]))
                for row in csv.DictReader(handle)}


def _signature(step, *, evidence: bool = True):
    fields = SIGNATURE_FIELDS if evidence else tuple(
        field for field in SIGNATURE_FIELDS if field != "evidence_id")
    return tuple(step[field] for field in fields)


def build_report(dataset: Path, prediction: Path, canonical: Path) -> str:
    predicted, expected = _load_output(prediction), _load_output(canonical)
    requests = {item.case_id: item for item in load_requests(dataset / "sample_deletion_requests.csv")}
    identity_events = load_identity_events(dataset / "user_audit_log.csv")
    identity_graph = IdentityGraph(load_identities(dataset / "user_identities.csv"), identity_events)
    activities = load_activity(dataset / "system_activity.csv")
    manifest = load_evidence_manifest(dataset / "evidence_files.csv", dataset)
    ingestion = ingest_evidence(manifest, identity_graph=identity_graph)
    linker = ResourceLinker(identity_graph, ingestion.store, activities, manifest)
    relationship_validation = ProvenanceValidator(
        manifest, activities, identity_events, ingestion.store,
    ).validate_relationships(linker.relationship_graph.relationships)
    relationship_types = Counter(edge.relationship_type.value
                                 for edge in linker.relationship_graph.relationships)
    relationship_validity = Counter(edge.validity.value
                                    for edge in linker.relationship_graph.relationships)

    counts = Counter({category: 0 for category in CATEGORIES})
    details: list[tuple[str, dict, str, str]] = []
    evidence_mismatches = ordering_mismatches = extra_count = missing_count = 0

    for case_id in sorted(expected):
        request = requests[case_id]
        user_id = identity_graph.resolve_email(request.email, at=request.audit_at).resolved_user_id or ""
        discovery = linker.discover(request)
        _, p_steps = predicted[case_id]
        _, c_steps = expected[case_id]
        p_exact = Counter(_signature(step) for step in p_steps)
        c_exact = Counter(_signature(step) for step in c_steps)
        missing = list((c_exact - p_exact).elements())
        extra = list((p_exact - c_exact).elements())
        extra_count += len(extra); missing_count += len(missing)
        p_no_evidence = Counter(_signature(step, evidence=False) for step in p_steps)
        c_no_evidence = Counter(_signature(step, evidence=False) for step in c_steps)
        if missing and p_no_evidence == c_no_evidence:
            evidence_mismatches += len(missing)
        if not missing and not extra and [_signature(step) for step in p_steps] != [
                _signature(step) for step in c_steps]:
            ordering_mismatches += 1

        missing_steps = [step for step in c_steps if p_exact[_signature(step)] < c_exact[_signature(step)]]
        seen = Counter()
        for step in missing_steps:
            sig = _signature(step); seen[sig] += 1
            if seen[sig] > c_exact[sig] - p_exact[sig]:
                continue
            resource_id = step["resource_id"]
            observations = ingestion.store.by_resource_id(resource_id)
            eligible = tuple(item for item in observations
                             if item.nature == EvidenceNature.STATE_OBSERVATION
                             and observation_usable_at(item, request.audit_at))
            resource_activities = tuple(item for item in activities
                                        if item.resource_id == resource_id
                                        and item.event_time <= request.audit_at)
            graph_linked = resource_id in linker.relationship_graph.resources_for_user(
                user_id, request.audit_at) if user_id else False
            discovered = resource_id in discovery.by_resource
            predicted_without_evidence = {_signature(item, evidence=False) for item in p_steps}

            if _signature(step, evidence=False) in predicted_without_evidence:
                category = "Evidence-selection errors"
                rationale = "the semantic step exists, but its evidence ID differs"
            elif discovered and step["phase"] == "VERIFICATION":
                category = "Verification coverage errors"
                rationale = "the resource is discovered but its required final-state check is missing"
            elif discovered:
                category = "Policy interpretation errors"
                rationale = "the resource is discovered but policy mapping omitted the expected action"
            elif step["operation"] in {"REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW",
                                      "VERIFY_DATA_FLOW_DISABLED", "REPORT_RESTORE_RISK",
                                      "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"}:
                category = "Missing active-flow or restore dependencies"
                rationale = "a process/restore dependency was not reached through a validated graph edge"
            else:
                historical = False
                for item in eligible:
                    for identifier in item.identifiers:
                        if identifier.kind == IdentifierKind.NAME:
                            continue
                        resolution = identity_graph.resolve(identifier.kind, identifier.raw_value,
                                                            at=request.audit_at, include_historical=True)
                        historical |= any(association.user_id == user_id
                                          and not association.active_at(item.observed_at)
                                          for association in resolution.associations)
                retained_identifier_free = bool(eligible) and all(not item.identifiers for item in eligible) \
                    and any(canonical_category(item) in {"SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"}
                            for item in eligible)
                later_only = bool(observations) and not eligible
                if retained_identifier_free:
                    category = "Identifier-free retained records"
                    rationale = "retained state is visible but contains no safe subject identifier or graph path"
                elif historical:
                    category = "Missing historical identity relationships"
                    rationale = "eligible evidence contains a historical identity that was not propagated"
                elif graph_linked and not discovered:
                    category = "Temporal reconstruction errors"
                    rationale = "a cutoff-valid graph path exists but no usable state reached discovery"
                elif eligible or resource_activities:
                    category = "Missing resource associations"
                    rationale = "the resource is visible before audit_at but lacks a validated subject relationship"
                else:
                    category = "Other genuinely unresolvable associations"
                    rationale = ("the resource appears only in later-captured evidence"
                                 if later_only else "no participant-visible pre-cutoff resource evidence exists")
            counts[category] += 1
            details.append((case_id, step, category, rationale +
                            f"; eligible_state={len(eligible)}, pre_cutoff_activity={len(resource_activities)}"))

    lines = [
        "# Phase 4 public-sample mismatch analysis", "",
        "This report is evaluation-only. Canonical steps are used to diagnose aggregate failure modes and are never imported by production prediction code.", "",
        "## Aggregate", "",
        f"- Missing steps: {missing_count}",
        f"- Extra steps: {extra_count}",
        f"- Evidence-ID-only mismatches: {evidence_mismatches}",
        f"- Ordering-only mismatches: {ordering_mismatches}", "",
    ]
    lines.extend(f"- {category}: {counts[category]}" for category in CATEGORIES)
    lines += ["", "## Relationship graph coverage", "",
              f"- Relationships: {len(linker.relationship_graph.relationships)}",
              f"- Provenance validation: {'passed' if relationship_validation.valid else 'failed'} ({len(relationship_validation.issues)} issues)",
              f"- Validity classes: `{dict(sorted(relationship_validity.items()))}`",
              f"- Relationship types: `{dict(sorted(relationship_types.items()))}`", "",
              "`REJECTED` operation edges and `AMBIGUOUS` correlation/collision edges are retained for audit diagnostics but are not prediction-traversable.", "",
              "## Per-step classification", ""]
    for case_id, step, category, rationale in details:
        lines += [
            f"### {case_id} / step {step['step_no']}", "",
            f"- Root cause: {category}",
            f"- Step: `{_signature(step)}`",
            f"- Rationale: {rationale}.", "",
        ]
    lines += [
        "## Safety conclusion", "",
        "No missing step is recoverable from a case number, list position, neighboring activity timestamp, or canonical resource label. Such correlations remain diagnostic-only. Identifier-free records become prediction-eligible only through an explicit participant-visible foreign key, parent/child edge, stable identity reference, source/target reference, or similarly validated relationship.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=CODE_ROOT.parent / "dataset")
    parser.add_argument("--prediction", type=Path, default=CODE_ROOT / "evaluation" / "sample_predictions.csv")
    parser.add_argument("--canonical", type=Path, default=CODE_ROOT.parent / "dataset" / "sample_output.csv")
    parser.add_argument("--output", type=Path, default=CODE_ROOT / "evaluation" / "mismatch_analysis.md")
    args = parser.parse_args()
    args.output.write_text(build_report(args.dataset.resolve(), args.prediction.resolve(),
                                        args.canonical.resolve()), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
