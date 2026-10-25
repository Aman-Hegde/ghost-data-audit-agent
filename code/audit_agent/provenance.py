"""Evidence-ID, resource-support, and cutoff validation."""

from __future__ import annotations

from .evidence_store import EvidenceStore
from .models import (ActivityEvent, EvidenceCitation, EvidenceManifestEntry, ExtractionIssue,
                     IdentityEvent, ResourceRelationship, ValidationResult)


class ProvenanceValidator:
    def __init__(self, manifest: list[EvidenceManifestEntry], activities: list[ActivityEvent],
                 identity_events: list[IdentityEvent], store: EvidenceStore):
        self.manifest = {item.file_id: item for item in manifest}
        self.activities = {item.activity_id: item for item in activities}
        self.identity_events = {item.audit_id: item for item in identity_events}
        self.store = store
        self.known_ids = set(self.manifest) | set(self.activities) | set(self.identity_events)

    def _supports_scoped_absence(self, evidence_id: str, resource_id: str, audit_at) -> bool:
        entry = self.manifest.get(evidence_id)
        if not entry or entry.captured_at > audit_at or entry.file_path.suffix.casefold() != ".sql":
            return False
        try:
            text = entry.file_path.read_text(encoding="utf-8-sig")
        except OSError:
            return False
        lower = text.casefold()
        prefix = resource_id.casefold().split("_", 1)[0]
        scope_tokens = {
            "account": "customer_profiles", "search": "search", "support": "support",
            "analytics": "analytics", "export": "export", "backup": "backup",
        }
        return ("point-in-time database snapshot" in lower
                and scope_tokens.get(prefix, "\0") in lower
                and resource_id.casefold() not in lower)

    def validate_index(self) -> ValidationResult:
        issues = []
        for observation in self.store.observations:
            evidence_id = observation.provenance.evidence_id
            if evidence_id not in self.known_ids:
                issues.append(ExtractionIssue(evidence_id, "UNKNOWN_EVIDENCE_ID",
                                              "observation provenance is absent from all participant indexes", "ERROR"))
                continue
            manifest_item = self.manifest.get(evidence_id)
            if manifest_item and manifest_item.file_path.resolve() != observation.provenance.source_path.resolve():
                issues.append(ExtractionIssue(evidence_id, "SOURCE_PATH_MISMATCH",
                                              f"manifest path does not match {observation.provenance.source_path}", "ERROR"))
        return ValidationResult(not issues, tuple(issues))

    def validate_relationships(self, relationships: tuple[ResourceRelationship, ...]) -> ValidationResult:
        """Validate graph-edge provenance without promoting the edge into state proof."""
        issues = []
        for edge in relationships:
            for evidence_id in edge.supporting_provenance:
                if evidence_id not in self.known_ids:
                    issues.append(ExtractionIssue(
                        evidence_id, "UNKNOWN_RELATIONSHIP_PROVENANCE",
                        f"relationship {edge.source_id} -> {edge.target_id} has unknown provenance", "ERROR",
                    ))
                    continue
                resource_ids = {
                    node.removeprefix("resource:") for node in (edge.source_id, edge.target_id)
                    if node.startswith("resource:")
                }
                activity = self.activities.get(evidence_id)
                identity = self.identity_events.get(evidence_id)
                observation_resources = {
                    item.resource.resource_id for resource_id in resource_ids
                    for item in self.store.by_resource_id(resource_id)
                    if item.provenance.evidence_id == evidence_id
                }
                supports = bool(observation_resources)
                supports = supports or bool(activity and activity.resource_id in resource_ids)
                supports = supports or bool(identity and f"user:{identity.user_id.casefold()}" in {
                    edge.source_id, edge.target_id})
                if resource_ids and not supports:
                    issues.append(ExtractionIssue(
                        evidence_id, "RELATIONSHIP_RESOURCE_NOT_SUPPORTED",
                        f"provenance does not name either graph resource {sorted(resource_ids)}", "ERROR",
                    ))
        return ValidationResult(not issues, tuple(issues))

    def validate_citation(self, citation: EvidenceCitation) -> ValidationResult:
        issues = []
        if citation.evidence_id not in self.known_ids:
            issues.append(ExtractionIssue(citation.evidence_id, "UNKNOWN_EVIDENCE_ID",
                                          "citation ID is not participant-provided", "ERROR"))
            return ValidationResult(False, tuple(issues))
        observations = [item for item in self.store.by_resource_id(citation.resource_id)
                        if item.provenance.evidence_id == citation.evidence_id]
        activity = self.activities.get(citation.evidence_id)
        identity = self.identity_events.get(citation.evidence_id)
        supports_resource = (bool(observations) or (activity and activity.resource_id == citation.resource_id)
                             or self._supports_scoped_absence(citation.evidence_id, citation.resource_id,
                                                             citation.audit_at))
        # Identity events support their user identity, not arbitrary resources.
        supports_resource = supports_resource or bool(identity and identity.user_id == citation.resource_id)
        if not supports_resource:
            issues.append(ExtractionIssue(citation.evidence_id, "RESOURCE_NOT_SUPPORTED",
                                          f"source does not support {citation.resource_id}", "ERROR"))
        if observations and not any(item.captured_at <= citation.audit_at and item.observed_at <= citation.audit_at
                                    for item in observations):
            issues.append(ExtractionIssue(citation.evidence_id, "TEMPORALLY_INAPPLICABLE",
                                          "no supporting observation existed by audit_at", "ERROR"))
        if activity and activity.event_time > citation.audit_at:
            issues.append(ExtractionIssue(citation.evidence_id, "TEMPORALLY_INAPPLICABLE",
                                          "activity occurred after audit_at", "ERROR"))
        if identity and identity.event_time > citation.audit_at:
            issues.append(ExtractionIssue(citation.evidence_id, "TEMPORALLY_INAPPLICABLE",
                                          "identity event occurred after audit_at", "ERROR"))
        if citation.claimed_state is not None and observations and not any(
                item.state == citation.claimed_state and item.captured_at <= citation.audit_at
                and item.observed_at <= citation.audit_at for item in observations):
            issues.append(ExtractionIssue(citation.evidence_id, "STATE_NOT_SUPPORTED",
                                          f"source does not support state {citation.claimed_state}", "ERROR"))
        return ValidationResult(not issues, tuple(issues))
