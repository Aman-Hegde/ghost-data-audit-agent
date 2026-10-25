"""Policy-derived finding, remediation, and verification planning."""

from __future__ import annotations

from .models import (AuditStep, ComplianceStatus, PolicyAction, ResourceAssessment)
from .ordering import order_steps


def _finding(item: ResourceAssessment) -> tuple[str, str]:
    category = item.policy.data_category
    if category == "DATA_FLOW":
        return "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"
    if category == "BACKUP_ARCHIVE":
        return "REPORT_RESTORE_RISK", "ACTIVE"
    if item.policy.action == PolicyAction.DELETE:
        return "REPORT_REMAINING_RECORD", "PRESENT"
    return "REPORT_EXPOSED_PII", "PRESENT"


def _remediation(item: ResourceAssessment) -> tuple[str, str] | None:
    category = item.policy.data_category
    if category == "DATA_FLOW":
        return "DISABLE_DATA_FLOW", "DISABLED"
    if category == "BACKUP_ARCHIVE":
        return "BLOCK_RESTORE", "BLOCKED"
    return {
        PolicyAction.DELETE: ("DELETE_RECORD", "ABSENT"),
        PolicyAction.REDACT: ("REDACT_RECORD", "REDACTED"),
        PolicyAction.ANONYMIZE: ("ANONYMIZE_RECORD", "ANONYMIZED"),
        PolicyAction.RETAIN: None,
    }[item.policy.action]


def _verification(item: ResourceAssessment) -> tuple[str, str]:
    category = item.policy.data_category
    if category == "DATA_FLOW":
        return "VERIFY_DATA_FLOW_DISABLED", "DISABLED"
    if category == "BACKUP_ARCHIVE":
        return "VERIFY_RESTORE_BLOCKED", "BLOCKED"
    return {
        PolicyAction.DELETE: ("VERIFY_RECORD_ABSENT", "ABSENT"),
        PolicyAction.REDACT: ("VERIFY_RECORD_REDACTED", "REDACTED"),
        PolicyAction.ANONYMIZE: ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
        PolicyAction.RETAIN: ("VERIFY_RECORD_PRESENT", "PRESENT"),
    }[item.policy.action]


def required_verification_scope(
        assessments: tuple[ResourceAssessment, ...]) -> tuple[ResourceAssessment, ...]:
    """Return every evidence-grounded resource whose policy state must be checked.

    This deliberately includes compliant retained records and already-absent source
    records in incomplete cases. It never manufactures a resource merely because a
    category would normally exist; discovery must first establish its identity link.
    """
    return assessments


def plan_steps(assessments: tuple[ResourceAssessment, ...], *, complete: bool) -> tuple[AuditStep, ...]:
    steps: list[AuditStep] = []
    if not complete:
        for item in assessments:
            if item.compliance != ComplianceStatus.VIOLATION or item.evidence is None:
                continue
            operation, state = _finding(item)
            steps.append(AuditStep(0, "FINDING", item.resource.logical_system,
                                   item.resource.resource_id, operation, state,
                                   item.evidence.provenance.evidence_id))
        for item in assessments:
            if item.compliance != ComplianceStatus.VIOLATION:
                continue
            action = _remediation(item)
            if action is not None:
                steps.append(AuditStep(0, "REMEDIATION", item.resource.logical_system,
                                       item.resource.resource_id, action[0], action[1], ""))
    for item in required_verification_scope(assessments):
        operation, state = _verification(item)
        evidence_id = (item.evidence.provenance.evidence_id
                       if complete and item.compliance == ComplianceStatus.COMPLIANT and item.evidence else "")
        steps.append(AuditStep(0, "VERIFICATION", item.resource.logical_system,
                               item.resource.resource_id, operation, state, evidence_id))
    return order_steps(steps)
