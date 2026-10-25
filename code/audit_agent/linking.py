"""Identity-grounded resource discovery with conservative workflow correlation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterable
import re

from .evidence_store import EvidenceStore
from .identity import IdentityGraph
from .models import (ActivityEvent, DeletionRequest, EvidenceManifestEntry, EvidenceNature,
                     IdentifierKind, Observation, Provenance, Resource, TemporalSemantics)
from .policy import canonical_category
from .relationships import ResourceRelationshipGraph
from .temporal import observation_usable_at

WORKFLOW_EVENTS = {
    "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD", "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE", "CHECK_DATA_FLOW", "CHECK_RESTORE_ACCESS",
}
RESOURCE_ID_RE = re.compile(
    r"^(?:account|search|support|analytics|backup|data_flow|export|tombstone|audit_record|cache|email_delivery)_[A-Za-z0-9-]+$|^(?:ORD|FIN)-[A-Za-z0-9-]+$",
    re.I,
)


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    user_id: str
    by_resource: dict[str, tuple[Observation, ...]]
    activities: tuple[ActivityEvent, ...]
    unresolved_reasons: tuple[str, ...] = ()


def _prefix_metadata(resource_id: str) -> tuple[str, str]:
    prefix = resource_id.casefold().split("_", 1)[0]
    return {
        "account": ("account_service", "USER_PROFILE"),
        "search": ("search_service", "SEARCH_INDEX_ENTRY"),
        "support": ("support_platform", "SUPPORT_MESSAGE"),
        "analytics": ("analytics_platform", "ANALYTICS_PROFILE"),
        "backup": ("backup_service", "BACKUP_ARCHIVE"),
        "data": ("integration_service", "DATA_FLOW"),
        "export": ("export_service", "USER_EXPORT"),
        "tombstone": ("identity_service", "ACCOUNT_TOMBSTONE"),
        "audit": ("security_service", "SECURITY_AUDIT_LOG"),
    }.get(prefix, ("unknown", "UNKNOWN"))


class ResourceLinker:
    def __init__(self, graph: IdentityGraph, store: EvidenceStore,
                 activities: Iterable[ActivityEvent], manifest: Iterable[EvidenceManifestEntry],
                 relationship_graph: ResourceRelationshipGraph | None = None):
        self.graph = graph
        self.store = store
        self.activities = tuple(sorted(activities, key=lambda item: (item.event_time, item.activity_id)))
        self.activity_by_resource: dict[str, list[ActivityEvent]] = defaultdict(list)
        for activity in self.activities:
            self.activity_by_resource[activity.resource_id].append(activity)
        self.manifest = tuple(manifest)
        self.relationship_graph = relationship_graph or ResourceRelationshipGraph.build(
            graph, store.observations, self.activities)

    def _eligible(self, resource_id: str, request: DeletionRequest) -> tuple[Observation, ...]:
        return tuple(item for item in self.store.by_resource_id(resource_id)
                     if item.nature == EvidenceNature.STATE_OBSERVATION
                     and observation_usable_at(item, request.audit_at))

    def _direct_resources(self, user_id: str, request: DeletionRequest) -> set[str]:
        resources = set()
        for association in self.graph.identifiers_for_user(user_id, known_by=request.audit_at):
            if association.kind == IdentifierKind.NAME:
                continue  # Names alone are not collision-safe links.
            for item in self.store.by_identifier(association.kind, association.raw_value):
                if item.nature == EvidenceNature.STATE_OBSERVATION and observation_usable_at(item, request.audit_at):
                    if not RESOURCE_ID_RE.match(item.resource.resource_id) or not any(
                            char.isdigit() for char in item.resource.resource_id):
                        continue
                    if not (item.resource.category == "ACCOUNT_TOMBSTONE"
                            and item.resource.resource_id.casefold() == user_id.casefold()):
                        resources.add(item.resource.resource_id)
        return resources

    def _details_resources(self, user_id: str, request: DeletionRequest) -> set[str]:
        identifiers = {item.normalized_value for item in self.graph.identifiers_for_user(
            user_id, known_by=request.audit_at) if item.kind != IdentifierKind.NAME and item.normalized_value}
        return {activity.resource_id for activity in self.activities if activity.event_time <= request.audit_at
                and any(value in activity.details.casefold() for value in identifiers)}

    def _workflow_candidates(self, resources: set[str], request: DeletionRequest) -> set[str]:
        anchor_times = [activity.event_time for resource_id in resources
                        for activity in self.activity_by_resource.get(resource_id, ())
                        if activity.event_type in WORKFLOW_EVENTS and activity.event_time <= request.audit_at]
        if not anchor_times:
            anchor_times = [request.reported_at]
            max_distance = timedelta(minutes=15)
        else:
            max_distance = timedelta(minutes=75)
        candidates = set()
        floor = request.requested_at - timedelta(minutes=5)
        ceiling = min(request.audit_at, request.reported_at + timedelta(hours=2))
        for activity in self.activities:
            if activity.event_type not in WORKFLOW_EVENTS or not floor <= activity.event_time <= ceiling:
                continue
            if min(abs(activity.event_time - anchor) for anchor in anchor_times) > max_distance:
                continue
            if self._eligible(activity.resource_id, request):
                candidates.add(activity.resource_id)
        return candidates

    def _sql_absence(self, resource_id: str, request: DeletionRequest) -> tuple[Observation, ...]:
        system, category = _prefix_metadata(resource_id)
        if category == "UNKNOWN" or self._eligible(resource_id, request):
            return ()
        matches = []
        for entry in self.manifest:
            if entry.file_path.suffix.casefold() != ".sql" or entry.captured_at > request.audit_at:
                continue
            scoped = [item for item in self.store.observations
                      if item.provenance.evidence_id == entry.file_id
                      and canonical_category(item) == category]
            if not scoped:
                continue
            try:
                header = entry.file_path.read_text(encoding="utf-8-sig")[:500].casefold()
            except OSError:
                continue
            if "point-in-time database snapshot" not in header:
                continue
            for physical in sorted({item.resource.physical_system for item in scoped}):
                matches.append(Observation(
                    Resource(resource_id, system, physical, category), "ABSENT", entry.captured_at,
                    entry.captured_at, (), {"inference": "absent_from_complete_sql_table_scope"},
                    Provenance(entry.file_id, entry.file_path, entry.origin,
                               f"table={physical};absence={resource_id}", "sql-scope-v1"),
                    TemporalSemantics.POINT_IN_TIME, EvidenceNature.STATE_OBSERVATION,
                ))
        if not matches:
            return ()
        newest_capture = max(item.captured_at for item in matches)
        return tuple(item for item in matches if item.captured_at == newest_capture)

    def discover(self, request: DeletionRequest) -> DiscoveryResult:
        resolution = self.graph.resolve_email(request.email, at=request.audit_at)
        if resolution.resolved_user_id is None:
            reason = "request identity is ambiguous" if resolution.ambiguous else "request identity is unresolved"
            return DiscoveryResult("", {}, (), (reason,))
        user_id = resolution.resolved_user_id
        resources = (self._direct_resources(user_id, request)
                     | self._details_resources(user_id, request)
                     | set(self.relationship_graph.resources_for_user(user_id, request.audit_at)))
        if not resources:
            resources |= self._workflow_candidates(resources, request)

        account_resources = {value for value in resources if value.casefold().startswith("account_")}
        if len(account_resources) > 1:
            lifecycle_ceiling = request.reported_at + timedelta(hours=2)
            lifecycle_accounts = {
                value for value in account_resources
                if any(request.requested_at <= activity.event_time <= lifecycle_ceiling
                       and activity.event_type == "DELETE_RECORD"
                       for activity in self.activity_by_resource.get(value, ()))
            }
            if lifecycle_accounts:
                resources -= account_resources - lifecycle_accounts

        # A narrowly bounded account workflow close to reported_at can establish the expected
        # resource ID; its state still requires evidence, never the reported activity result.
        nearby_accounts = [activity for activity in self.activities
                           if activity.event_type == "DELETE_RECORD" and activity.target_system == "account_service"
                           and abs(activity.event_time - request.reported_at) <= timedelta(minutes=15)]
        if len(nearby_accounts) == 1:
            resources.add(nearby_accounts[0].resource_id)

        grouped: dict[str, tuple[Observation, ...]] = {}
        for resource_id in sorted(resources):
            observations = self._eligible(resource_id, request)
            if not observations:
                observations = self._sql_absence(resource_id, request)
            if observations:
                grouped[resource_id] = observations
        relevant_activity = tuple(activity for activity in self.activities
                                  if activity.resource_id in grouped and activity.event_time <= request.audit_at)
        unresolved = () if grouped else ("no identity-grounded resource state observations",)
        return DiscoveryResult(user_id, grouped, relevant_activity, unresolved)
