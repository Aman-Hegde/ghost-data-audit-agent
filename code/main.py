"""Phase 2 validation entry point. It deliberately does not create output.csv."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from audit_agent.identity import IdentityGraph
from audit_agent.ingestion import ingest_evidence
from audit_agent.intent import IntentClassifier, MultilingualRuleAdjudicator
from audit_agent.loaders import (
    load_activity, load_evidence_manifest, load_identities, load_identity_events,
    load_policy_rules, load_requests,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and index Ghost Data participant inputs (Phase 2)")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "dataset")
    parser.add_argument("--requests", default="deletion_requests.csv")
    args = parser.parse_args()
    dataset = args.dataset.resolve()

    requests = load_requests(dataset / args.requests)
    identities = load_identities(dataset / "user_identities.csv")
    events = load_identity_events(dataset / "user_audit_log.csv")
    graph = IdentityGraph(identities, events)
    activity = load_activity(dataset / "system_activity.csv")
    rules = load_policy_rules(dataset / "deletion_rules.csv")
    manifest = load_evidence_manifest(dataset / "evidence_files.csv", dataset)
    ingestion = ingest_evidence(manifest, identity_graph=graph)
    classifier = IntentClassifier(MultilingualRuleAdjudicator())
    intent_counts = Counter(classifier.classify(item.request_text).kind.value for item in requests)
    resolution_counts = Counter(
        "unique" if graph.resolve_email(item.email, at=item.audit_at).resolved_user_id else
        "ambiguous" if graph.resolve_email(item.email, at=item.audit_at).ambiguous else "unresolved"
        for item in requests
    )
    print(json.dumps({
        "requests": len(requests), "identities": len(identities), "identity_events": len(events),
        "activity_events": len(activity), "policy_rules": len(rules), "manifest_files": len(manifest),
        "evidence_files_parsed": ingestion.coverage.parsed_files,
        "unresolved_evidence_files": ingestion.coverage.unresolved_files,
        "parser_errors": ingestion.coverage.parser_errors,
        "observations": ingestion.coverage.usable_observations,
        "duplicate_observations": ingestion.coverage.duplicate_observations,
        "model_calls": sum(item.calls for item in ingestion.coverage.model_usage),
        "intent_counts": dict(sorted(intent_counts.items())),
        "identity_resolution": dict(sorted(resolution_counts.items())),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
