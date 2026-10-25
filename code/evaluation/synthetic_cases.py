"""Independent Phase 4 evaluation cases with ground truth kept in fixtures/."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from audit_agent.evidence_store import EvidenceStore  # noqa: E402
from audit_agent.identity import IdentityGraph  # noqa: E402
from audit_agent.intent import IntentClassifier, MultilingualRuleAdjudicator  # noqa: E402
from audit_agent.linking import ResourceLinker  # noqa: E402
from audit_agent.models import (DeletionRequest, Identifier, IdentifierKind, IdentitySnapshot,  # noqa: E402
                                Observation, PolicyRule, Provenance, Resource)
from audit_agent.normalization import normalize_identifier  # noqa: E402
from audit_agent.policy import PolicyEngine  # noqa: E402
from audit_agent.reasoning import DeletionAuditor  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _rules() -> tuple[PolicyRule, ...]:
    values = (
        ("USER_PROFILE", "DELETE"), ("SECONDARY_IDENTIFIER", "DELETE"),
        ("SEARCH_INDEX_ENTRY", "DELETE"), ("CACHE_ENTRY", "DELETE"),
        ("SUPPORT_MESSAGE", "REDACT"), ("SUPPORT_ATTACHMENT", "DELETE"),
        ("ANALYTICS_PROFILE", "ANONYMIZE"), ("PRODUCT_TELEMETRY", "ANONYMIZE"),
        ("USER_EXPORT", "DELETE"), ("MARKETING_PROFILE", "DELETE"),
        ("EMAIL_DELIVERY_LOG", "REDACT"), ("SECURITY_AUDIT_LOG", "RETAIN"),
        ("LEGAL_HOLD_RECORD", "RETAIN"), ("BACKUP_ARCHIVE", "RETAIN"),
        ("ACCOUNT_TOMBSTONE", "REDACT"),
    )
    return tuple(PolicyRule(f"synthetic_rule_{index}", category, "synthetic condition", action)
                 for index, (category, action) in enumerate(values, 1))


def _identifier(user_id: str) -> Identifier:
    return Identifier(IdentifierKind.USER_ID, user_id,
                      normalize_identifier(IdentifierKind.USER_ID, user_id), "$.user_id")


def _observation(case: str, user_id: str, resource_id: str, system: str,
                 category: str, state: str, attributes=None) -> Observation:
    evidence_id = f"synthetic_evidence_{case}_{resource_id}"
    return Observation(
        Resource(resource_id, system, system, category), state, NOW, NOW,
        (_identifier(user_id),), attributes or {},
        Provenance(evidence_id, Path(f"{evidence_id}.json"), "synthetic",
                   "$.records[0]", "synthetic-v1"),
    )


def predictions():
    snapshots = (
        IdentitySnapshot("user_complete", "Complete Person", "complete@example.test",
                         "+10000000101", "1" * 64, NOW - timedelta(days=10)),
        IdentitySnapshot("user_incomplete", "Incomplete Person", "incomplete@example.test",
                         "+10000000102", "2" * 64, NOW - timedelta(days=10)),
        IdentitySnapshot("user_nondelete", "Access Person", "access@example.test",
                         "+10000000103", "3" * 64, NOW - timedelta(days=10)),
    )
    graph = IdentityGraph(snapshots, ())
    observations = (
        _observation("complete", "user_complete", "account_7001", "account_service",
                     "USER_PROFILE", "ABSENT"),
        _observation("complete", "user_complete", "audit_record_7001", "security_service",
                     "SECURITY_AUDIT_LOG", "PRESENT", {"integrity": "sealed"}),
        _observation("incomplete", "user_incomplete", "account_7002", "account_service",
                     "USER_PROFILE", "ABSENT"),
        _observation("incomplete", "user_incomplete", "search_7002", "search_service",
                     "SEARCH_INDEX_ENTRY", "PRESENT"),
        _observation("incomplete", "user_incomplete", "data_flow_7002", "integration_service",
                     "DATA_FLOW", "ACTIVE", {"enabled": True}),
        _observation("incomplete", "user_incomplete", "audit_record_7002", "security_service",
                     "SECURITY_AUDIT_LOG", "PRESENT", {"integrity": "sealed"}),
    )
    auditor = DeletionAuditor(
        IntentClassifier(MultilingualRuleAdjudicator()),
        ResourceLinker(graph, EvidenceStore(observations), (), ()),
        PolicyEngine(_rules()),
    )
    requests = (
        DeletionRequest("synthetic_complete", "complete@example.test", NOW - timedelta(days=3),
                        "COMPLETE", NOW - timedelta(days=2), NOW,
                        "Delete my account and all personal data."),
        DeletionRequest("synthetic_incomplete", "incomplete@example.test", NOW - timedelta(days=3),
                        "COMPLETE", NOW - timedelta(days=2), NOW,
                        "Permanently delete my account and personal information."),
        DeletionRequest("synthetic_non_deletion", "access@example.test", NOW - timedelta(days=3),
                        "NOT_STARTED", NOW - timedelta(days=2), NOW,
                        "Please send my data export; do not delete my account."),
    )
    return tuple(auditor.predict(request) for request in requests)


def evaluate(expected_path: Path | None = None) -> tuple[bool, list[str]]:
    expected_path = expected_path or Path(__file__).parent / "fixtures" / "synthetic_expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = {item.case_id: {"deletion_status": item.deletion_status,
                             "steps": [step.as_dict() for step in item.steps]}
              for item in predictions()}
    failures = [case_id for case_id in sorted(expected) if actual.get(case_id) != expected[case_id]]
    failures.extend(sorted(set(actual) - set(expected)))
    return not failures, failures


if __name__ == "__main__":
    passed, failures = evaluate()
    print(json.dumps({"passed": passed, "failures": failures}, indent=2))
    raise SystemExit(0 if passed else 1)
