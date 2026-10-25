"""Single source of truth for the challenge step contract and ordering."""

from __future__ import annotations

from .errors import DataValidationError
from .models import AuditStep

PHASE_ORDER = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
OPERATION_ORDER = {
    "FINDING": ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"],
    "REMEDIATION": ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"],
    "VERIFICATION": ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED",
                     "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"],
}
OPERATION_STATES = {
    "REPORT_REMAINING_RECORD": "PRESENT", "REPORT_EXPOSED_PII": "PRESENT",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE", "REPORT_RESTORE_RISK": "ACTIVE",
    "DISABLE_DATA_FLOW": "DISABLED", "BLOCK_RESTORE": "BLOCKED", "DELETE_RECORD": "ABSENT",
    "REDACT_RECORD": "REDACTED", "ANONYMIZE_RECORD": "ANONYMIZED",
    "VERIFY_RECORD_ABSENT": "ABSENT", "VERIFY_RECORD_PRESENT": "PRESENT",
    "VERIFY_RECORD_REDACTED": "REDACTED", "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED": "DISABLED", "VERIFY_RESTORE_BLOCKED": "BLOCKED",
}


def order_steps(steps: list[AuditStep]) -> tuple[AuditStep, ...]:
    def key(step: AuditStep) -> tuple:
        if step.phase not in PHASE_ORDER or step.operation not in OPERATION_STATES:
            raise DataValidationError(f"illegal step {step.phase}/{step.operation}")
        if step.operation not in OPERATION_ORDER[step.phase]:
            raise DataValidationError(f"operation {step.operation} is illegal in phase {step.phase}")
        if OPERATION_STATES[step.operation] != step.state:
            raise DataValidationError(f"{step.operation} requires state {OPERATION_STATES[step.operation]}")
        return (PHASE_ORDER[step.phase], OPERATION_ORDER[step.phase].index(step.operation),
                step.system_id, step.resource_id, step.evidence_id)
    ordered = sorted(steps, key=key)
    return tuple(AuditStep(index, item.phase, item.system_id, item.resource_id,
                           item.operation, item.state, item.evidence_id)
                 for index, item in enumerate(ordered, 1))
