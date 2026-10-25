"""Compilation and evaluation of participant-provided deletion rules."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Any

from .errors import DataValidationError
from .models import (ComplianceStatus, IdentifierKind, Observation, PolicyAction,
                     PolicyDecision, PolicyRule, ResourceAssessment)

TERMINAL_STATES = {
    PolicyAction.DELETE: "ABSENT",
    PolicyAction.REDACT: "REDACTED",
    PolicyAction.ANONYMIZE: "ANONYMIZED",
    PolicyAction.RETAIN: "PRESENT",
}
PII_KINDS = (IdentifierKind.NAME, IdentifierKind.EMAIL, IdentifierKind.PHONE, IdentifierKind.EMAIL_HASH)


def canonical_category(observation: Observation) -> str:
    """Normalize parser-family labels using stable resource/system semantics."""
    category = observation.resource.category.upper()
    rid = observation.resource.resource_id.casefold()
    event = str(observation.attributes.get("event", "")).casefold()
    if category in {"TICKETS", "SUPPORT_TICKET_READ_STARTED", "SUPPORT_TICKET_READ_COMPLETED",
                    "MESSAGE_PII_SCAN", "MESSAGE_READ", "MESSAGE_SCAN_STARTED"}:
        return "SUPPORT_MESSAGE"
    if category in {"DELETION_MARKER_CHECK", "CONTACT_QUERY_STARTED", "CONTACT_QUERY_COMPLETED"}:
        return "SUPPORT_ATTACHMENT"
    if category == "SUPPORT_ATTACHMENT" or "attachment" in category.casefold():
        return "SUPPORT_ATTACHMENT"
    if rid.startswith("support_"):
        return "SUPPORT_MESSAGE"
    if rid.startswith("account_"):
        return "USER_PROFILE"
    if rid.startswith("search_"):
        return "SEARCH_INDEX_ENTRY"
    if rid.startswith("analytics_"):
        return "MARKETING_PROFILE" if "contact" in event or "email_opt_in" in observation.attributes else "ANALYTICS_PROFILE"
    if rid.startswith("data_flow_"):
        return "DATA_FLOW"
    if rid.startswith("backup_"):
        return "BACKUP_ARCHIVE"
    if rid.startswith("audit_record_"):
        return "SECURITY_AUDIT_LOG"
    if rid.startswith("export_"):
        return "USER_EXPORT"
    if rid.startswith("tombstone_") or category == "ACCOUNT_TOMBSTONE":
        return "ACCOUNT_TOMBSTONE"
    if rid.startswith("cache_"):
        return "CACHE_ENTRY"
    if rid.startswith("email_delivery_"):
        return "EMAIL_DELIVERY_LOG"
    if rid.startswith(("ord-", "fin-")):
        return "LEGAL_HOLD_RECORD"
    return category


def canonical_system(category: str, fallback: str) -> str:
    return {
        "USER_PROFILE": "account_service", "SECONDARY_IDENTIFIER": "identity_service",
        "SEARCH_INDEX_ENTRY": "search_service", "CACHE_ENTRY": "cache_service",
        "SUPPORT_MESSAGE": "support_platform", "SUPPORT_ATTACHMENT": "support_platform",
        "ANALYTICS_PROFILE": "analytics_platform", "PRODUCT_TELEMETRY": "analytics_platform",
        "USER_EXPORT": "export_service",
        "EMAIL_DELIVERY_LOG": "email_delivery_service", "SECURITY_AUDIT_LOG": "security_service",
        "LEGAL_HOLD_RECORD": "legal_service", "BACKUP_ARCHIVE": "backup_service",
        "ACCOUNT_TOMBSTONE": "identity_service", "DATA_FLOW": "integration_service",
    }.get(category, fallback)


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().casefold() in {"", "null", "none", "[redacted]"})


def effective_state(observation: Observation, category: str) -> str:
    state = observation.state.upper()
    if state in {"HIT", "FOUND", "IDENTIFIABLE"}:
        state = "PRESENT"
    elif state in {"MISS", "NOT_FOUND", "MISSING"}:
        state = "ABSENT"
    attrs = observation.attributes
    if category == "DATA_FLOW":
        enabled = attrs.get("enabled")
        if isinstance(enabled, bool):
            return "ACTIVE" if enabled else "DISABLED"
    if category == "BACKUP_ARCHIVE":
        allowed = attrs.get("restore_allowed")
        if isinstance(allowed, bool):
            return "ACTIVE" if allowed else "BLOCKED"
    if category == "SUPPORT_MESSAGE" and state not in {"ABSENT", "REDACTED"}:
        keys = ("requester_name", "requester_email", "requester_phone", "name", "email", "phone", "full_name")
        fields = [attrs[key] for key in keys if key in attrs]
        if fields and all(_empty(value) for value in fields):
            return "REDACTED"
    if category in {"ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"} and state not in {"ABSENT", "ANONYMIZED"}:
        keys = ("customer_reference", "user_id", "email", "phone", "email_hash")
        fields = [attrs[key] for key in keys if key in attrs]
        if fields and all(_empty(value) for value in fields):
            return "ANONYMIZED"
    if category == "ACCOUNT_TOMBSTONE" and state != "ABSENT":
        stable = attrs.get("subject_reference") or attrs.get("user_id") or attrs.get("customer_reference")
        pii = [attrs.get(key) for key in ("name", "full_name", "email", "phone", "email_hash")]
        if stable and all(_empty(value) for value in pii):
            return "REDACTED"
        return "PRESENT"
    return state


class PolicyEngine:
    def __init__(self, rules: Iterable[PolicyRule]):
        self.rules = {rule.data_category: rule for rule in rules}
        if len(self.rules) != 15:
            raise DataValidationError(f"expected 15 unique policy categories, found {len(self.rules)}")
        for rule in self.rules.values():
            try:
                PolicyAction(rule.required_action)
            except ValueError as exc:
                raise DataValidationError(f"{rule.rule_id}: invalid action {rule.required_action}") from exc

    def decision_for_category(self, category: str) -> PolicyDecision:
        if category == "DATA_FLOW":
            return PolicyDecision("process_data_flow", category, PolicyAction.REDACT, "DISABLED",
                                  "Active synchronization/import paths must be disabled")
        rule = self.rules.get(category)
        if rule is None:
            raise DataValidationError(f"no deletion rule for category {category!r}")
        action = PolicyAction(rule.required_action)
        terminal = "BLOCKED" if category == "BACKUP_ARCHIVE" else TERMINAL_STATES[action]
        prohibited = PII_KINDS if action in {PolicyAction.REDACT, PolicyAction.ANONYMIZE} else ()
        return PolicyDecision(rule.rule_id, category, action, terminal, rule.condition, prohibited)

    def assess(self, observations: Iterable[Observation], audit_at: datetime) -> ResourceAssessment:
        values = tuple(sorted(observations, key=lambda item: (
            item.observed_at, item.captured_at, item.provenance.evidence_id, item.provenance.locator)))
        if not values:
            raise DataValidationError("cannot assess an empty resource observation set")
        category = canonical_category(values[-1])
        decision = self.decision_for_category(category)
        states = [(effective_state(item, category), item) for item in values]
        compliant = [(state, item) for state, item in states if state == decision.terminal_state]
        violations = [(state, item) for state, item in states if state != decision.terminal_state]
        # Each physical store contributes its latest state; an older state must not override a newer one.
        latest: dict[str, tuple[str, Observation]] = {}
        for state, item in states:
            latest[item.resource.physical_system] = (state, item)
        current = tuple(latest.values())
        bad = [(state, item) for state, item in current if state != decision.terminal_state]
        good = [(state, item) for state, item in current if state == decision.terminal_state]
        if bad:
            state, evidence = sorted(bad, key=lambda pair: (
                pair[1].observed_at, pair[1].captured_at, pair[1].provenance.evidence_id))[-1]
            compliance = ComplianceStatus.VIOLATION
            rationale = f"{category} requires {decision.terminal_state}, observed {state}"
        elif good:
            state, evidence = sorted(good, key=lambda pair: (
                pair[1].observed_at, pair[1].captured_at, pair[1].provenance.evidence_id))[-1]
            compliance = ComplianceStatus.COMPLIANT
            rationale = f"all observed physical copies satisfy {decision.terminal_state}"
        else:
            state, evidence = None, None
            compliance = ComplianceStatus.UNRESOLVED
            rationale = "no eligible state observation"
        original = values[-1].resource
        from .models import Resource
        resource = Resource(original.resource_id, canonical_system(category, original.logical_system),
                            original.physical_system, category)
        return ResourceAssessment(resource, decision, compliance, state, evidence, values, rationale)
