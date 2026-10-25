"""Typed immutable models shared by ingestion, indexing, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class IdentifierKind(str, Enum):
    USER_ID = "user_id"
    EMAIL = "email"
    EMAIL_HASH = "email_hash"
    PHONE = "phone"
    NAME = "name"
    OTHER = "other"


class IntentKind(str, Enum):
    DELETION = "DELETION"
    NON_DELETION = "NON_DELETION"
    AMBIGUOUS = "AMBIGUOUS"


class TemporalSemantics(str, Enum):
    """How an observation can be used relative to its capture time."""

    POINT_IN_TIME = "POINT_IN_TIME"
    EVENT_OCCURRED = "EVENT_OCCURRED"
    HISTORICAL_RECORD = "HISTORICAL_RECORD"


class EvidenceNature(str, Enum):
    STATE_OBSERVATION = "STATE_OBSERVATION"
    OPERATION_EVENT = "OPERATION_EVENT"
    HISTORICAL_FACT = "HISTORICAL_FACT"
    NARRATIVE = "NARRATIVE"


class OperationStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ATTEMPTED = "ATTEMPTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"


class TimelineStatus(str, Enum):
    RESOLVED = "RESOLVED"
    CONTRADICTORY = "CONTRADICTORY"
    UNRESOLVED = "UNRESOLVED"


class PolicyAction(str, Enum):
    DELETE = "DELETE"
    REDACT = "REDACT"
    ANONYMIZE = "ANONYMIZE"
    RETAIN = "RETAIN"


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    UNRESOLVED = "UNRESOLVED"


class RelationshipType(str, Enum):
    """Evidence-grounded ways in which graph nodes can be related."""

    STABLE_USER_ID = "STABLE_USER_ID"
    HISTORICAL_IDENTITY = "HISTORICAL_IDENTITY"
    EXPLICIT_IDENTITY_REFERENCE = "EXPLICIT_IDENTITY_REFERENCE"
    FOREIGN_KEY = "FOREIGN_KEY"
    PARENT_CHILD = "PARENT_CHILD"
    SOURCE_TARGET_FLOW = "SOURCE_TARGET_FLOW"
    BACKUP_REFERENCE = "BACKUP_REFERENCE"
    OPERATION_READBACK = "OPERATION_READBACK"
    PHYSICAL_REPLICA = "PHYSICAL_REPLICA"


class RelationshipValidity(str, Enum):
    """Whether a relationship is safe to use for prediction-time traversal."""

    VALIDATED = "VALIDATED"
    CORROBORATED = "CORROBORATED"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class Provenance:
    evidence_id: str
    source_path: Path
    origin: str
    locator: str
    parser: str


@dataclass(frozen=True, slots=True)
class DeletionRequest:
    case_id: str
    email: str
    requested_at: datetime
    reported_status: str
    reported_at: datetime
    audit_at: datetime
    request_text: str


@dataclass(frozen=True, slots=True)
class IdentitySnapshot:
    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityEvent:
    audit_id: str
    user_id: str
    event_time: datetime
    field_name: str
    old_value: str
    new_value: str


@dataclass(frozen=True, slots=True)
class IdentityAssociation:
    user_id: str
    kind: IdentifierKind
    raw_value: str
    normalized_value: str
    valid_from: datetime | None
    valid_to: datetime | None
    provenance_id: str

    def active_at(self, instant: datetime) -> bool:
        return ((self.valid_from is None or self.valid_from <= instant)
                and (self.valid_to is None or instant < self.valid_to))


@dataclass(frozen=True, slots=True)
class EvidenceManifestEntry:
    file_id: str
    file_path: Path
    origin: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    activity_id: str
    event_time: datetime
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str
    details: str


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    data_category: str
    condition: str
    required_action: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    rule_id: str
    data_category: str
    action: PolicyAction
    terminal_state: str
    condition: str
    prohibited_identifier_kinds: tuple[IdentifierKind, ...] = ()


@dataclass(frozen=True, slots=True)
class Identifier:
    kind: IdentifierKind
    raw_value: str
    normalized_value: str
    field_path: str


@dataclass(frozen=True, slots=True)
class Resource:
    resource_id: str
    logical_system: str
    physical_system: str
    category: str


@dataclass(frozen=True, slots=True)
class ResourceRelationship:
    """A temporal graph edge with participant-visible supporting provenance."""

    source_id: str
    target_id: str
    relationship_type: RelationshipType
    supporting_provenance: tuple[str, ...]
    valid_from: datetime | None
    valid_to: datetime | None
    captured_at: datetime
    confidence: float
    validity: RelationshipValidity
    rationale: str = ""

    def applicable_at(self, instant: datetime) -> bool:
        return (
            self.captured_at <= instant
            and (self.valid_from is None or self.valid_from <= instant)
            and (self.valid_to is None or instant < self.valid_to)
        )


@dataclass(frozen=True, slots=True)
class Observation:
    resource: Resource
    state: str
    observed_at: datetime
    captured_at: datetime
    identifiers: tuple[Identifier, ...]
    attributes: Mapping[str, Any]
    provenance: Provenance
    temporal_semantics: TemporalSemantics = TemporalSemantics.POINT_IN_TIME
    nature: EvidenceNature = EvidenceNature.STATE_OBSERVATION
    correlation_id: str = ""
    operation_status: OperationStatus = OperationStatus.NOT_APPLICABLE


@dataclass(frozen=True, slots=True)
class IntentDecision:
    kind: IntentKind
    confidence: str
    rationale: str
    mechanism: str


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    normalized_identifier: str
    user_ids: tuple[str, ...]
    associations: tuple[IdentityAssociation, ...]

    @property
    def resolved_user_id(self) -> str | None:
        return self.user_ids[0] if len(self.user_ids) == 1 else None

    @property
    def ambiguous(self) -> bool:
        return len(self.user_ids) > 1


@dataclass(frozen=True, slots=True)
class ResourceHistory:
    resource_id: str
    latest_by_physical_system: Mapping[str, Observation]
    observations: tuple[Observation, ...]
    contradictory: bool


@dataclass(frozen=True, slots=True)
class TimelineAssessment:
    resource_id: str
    audit_at: datetime
    status: TimelineStatus
    best_state: str | None
    latest_by_physical_system: Mapping[str, Observation]
    state_observations: tuple[Observation, ...]
    operation_events: tuple[Observation, ...]
    conflicts: tuple[tuple[Observation, Observation], ...]
    recreation_detected: bool


@dataclass(frozen=True, slots=True)
class ResourceAssessment:
    resource: Resource
    policy: PolicyDecision
    compliance: ComplianceStatus
    effective_state: str | None
    evidence: Observation | None
    observations: tuple[Observation, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class AuditStep:
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_no": self.step_no, "phase": self.phase, "system_id": self.system_id,
            "resource_id": self.resource_id, "operation": self.operation,
            "state": self.state, "evidence_id": self.evidence_id,
        }


@dataclass(frozen=True, slots=True)
class CasePrediction:
    case_id: str
    deletion_status: str
    steps: tuple[AuditStep, ...]
    unresolved_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionIssue:
    evidence_id: str
    code: str
    message: str
    severity: str = "WARNING"


@dataclass(frozen=True, slots=True)
class ArtifactExtraction:
    evidence_id: str
    status: str
    observations: tuple[Observation, ...]
    issues: tuple[ExtractionIssue, ...] = ()
    content_sha256: str = ""
    method: str = ""


@dataclass(frozen=True, slots=True)
class ModelUsage:
    provider: str
    model: str
    purpose: str
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    evidence_id: str
    resource_id: str
    audit_at: datetime
    claimed_state: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    issues: tuple[ExtractionIssue, ...]


@dataclass(frozen=True, slots=True)
class EvidenceCoverage:
    manifest_files: int
    parsed_files: int
    unresolved_files: int
    parser_errors: int
    observations_before_deduplication: int
    usable_observations: int
    duplicate_observations: int
    unresolved_evidence_ids: tuple[str, ...]
    issues: tuple[ExtractionIssue, ...]
    model_usage: tuple[ModelUsage, ...]


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    cases: int
    status_correct: int
    exact_rows: int
    exact_sequences: int
    step_true_positive: int
    predicted_steps: int
    canonical_steps: int
    field_correct: int
    field_total: int
    per_field: Mapping[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def status_accuracy(self) -> float:
        return self.status_correct / self.cases if self.cases else 0.0

    @property
    def exact_row_accuracy(self) -> float:
        return self.exact_rows / self.cases if self.cases else 0.0

    @property
    def sequence_accuracy(self) -> float:
        return self.exact_sequences / self.cases if self.cases else 0.0

    @property
    def step_precision(self) -> float:
        return self.step_true_positive / self.predicted_steps if self.predicted_steps else 0.0

    @property
    def step_recall(self) -> float:
        return self.step_true_positive / self.canonical_steps if self.canonical_steps else 0.0

    @property
    def step_f1(self) -> float:
        p, r = self.step_precision, self.step_recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def field_accuracy(self) -> float:
        return self.field_correct / self.field_total if self.field_total else 0.0
