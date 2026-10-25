"""Typed, provenance-preserving resource relationship graph.

Only validated or corroborated edges are traversable during prediction. Ambiguous
edges are retained for diagnostics, which lets the audit explain why a possible
association was rejected without silently turning coincidence into ownership.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from .identity import IdentityGraph
from .models import (
    ActivityEvent, EvidenceNature, Identifier, IdentifierKind, Observation, RelationshipType,
    RelationshipValidity, ResourceRelationship,
)
from .parsers.common import extract_identifiers

RESOURCE_RE = re.compile(
    r"^(?:account|search|support|analytics|backup|data_flow|export|tombstone|"
    r"audit_record|cache|email_delivery|marketing|object)_[A-Za-z0-9-]+$|"
    r"^(?:ORD|FIN)-[A-Za-z0-9-]+$", re.I,
)
CORRELATION_RE = re.compile(r"^(?:tr|rb|req|request|op|corr|trace)[-_:][A-Za-z0-9-]+$", re.I)
SAFE_VALIDITIES = {RelationshipValidity.VALIDATED, RelationshipValidity.CORROBORATED}


def user_node(user_id: str) -> str:
    return f"user:{user_id.casefold()}"


def resource_node(resource_id: str) -> str:
    return f"resource:{resource_id}"


def activity_node(activity_id: str) -> str:
    return f"activity:{activity_id}"


def physical_node(system_id: str, resource_id: str) -> str:
    return f"physical:{system_id}:{resource_id}"


def _walk(value: Any, path: str = "$"):
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _relationship_type(key: str) -> RelationshipType | None:
    lower = key.casefold()
    if lower == "resource_id":
        return None
    if "parent" in lower or lower in {"account_id", "profile_id", "support_resource_id"}:
        return RelationshipType.PARENT_CHILD
    if lower.startswith(("source_", "target_")) and "resource" in lower:
        return RelationshipType.SOURCE_TARGET_FLOW
    if any(token in lower for token in ("backup_resource", "archive_resource", "restore_resource")):
        return RelationshipType.BACKUP_REFERENCE
    if lower.endswith("_resource_id") or lower in {"related_resource", "resource_reference"}:
        return RelationshipType.FOREIGN_KEY
    return None


class ResourceRelationshipGraph:
    """A deterministic graph whose unsafe edges remain non-traversable."""

    def __init__(self, relationships: Iterable[ResourceRelationship] = ()):
        unique: dict[tuple, ResourceRelationship] = {}
        for edge in relationships:
            key = (
                edge.source_id, edge.target_id, edge.relationship_type.value,
                edge.supporting_provenance, edge.valid_from, edge.valid_to,
                edge.captured_at, edge.validity.value,
            )
            unique[key] = edge
        self.relationships = tuple(sorted(unique.values(), key=lambda edge: (
            edge.source_id, edge.target_id, edge.relationship_type.value,
            edge.valid_from or datetime.min.replace(tzinfo=edge.captured_at.tzinfo),
            edge.captured_at, edge.supporting_provenance,
        )))
        adjacency: dict[str, list[ResourceRelationship]] = defaultdict(list)
        for edge in self.relationships:
            adjacency[edge.source_id].append(edge)
            adjacency[edge.target_id].append(edge)
        self._adjacency = {node: tuple(values) for node, values in adjacency.items()}

    @classmethod
    def build(cls, identity_graph: IdentityGraph, observations: Iterable[Observation],
              activities: Iterable[ActivityEvent]) -> "ResourceRelationshipGraph":
        observations = tuple(observations)
        edges: list[ResourceRelationship] = []
        for observation in observations:
            edges.extend(cls._observation_edges(identity_graph, observation))
        edges.extend(cls._correlation_edges(observations))
        for activity in activities:
            edges.extend(cls._activity_edges(identity_graph, activity))
        return cls(cls._enforce_identity_safety(edges))

    @staticmethod
    def _enforce_identity_safety(edges: list[ResourceRelationship]) -> list[ResourceRelationship]:
        """Reject ownership traversal for a resource that points at multiple users."""
        identity_types = {
            RelationshipType.STABLE_USER_ID, RelationshipType.HISTORICAL_IDENTITY,
            RelationshipType.EXPLICIT_IDENTITY_REFERENCE,
        }
        owners: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            if edge.relationship_type in identity_types and edge.source_id.startswith("user:") \
                    and edge.target_id.startswith("resource:"):
                owners[edge.target_id].add(edge.source_id)
        ambiguous_resources = {node for node, users in owners.items() if len(users) > 1}
        return [
            replace(edge, validity=RelationshipValidity.AMBIGUOUS, confidence=min(edge.confidence, 0.25),
                    rationale="resource has participant-visible references to multiple users")
            if edge.target_id in ambiguous_resources and edge.relationship_type in identity_types
            else edge
            for edge in edges
        ]

    @staticmethod
    def _resolved_users(identity_graph: IdentityGraph, identifiers: Iterable[Identifier],
                        at: datetime) -> tuple[set[str], list[tuple[Identifier, object]]]:
        users: set[str] = set()
        resolved: list[tuple[Identifier, object]] = []
        for identifier in identifiers:
            if identifier.kind in {IdentifierKind.NAME, IdentifierKind.OTHER}:
                continue
            resolution = identity_graph.resolve(identifier.kind, identifier.raw_value,
                                                at=at, include_historical=True)
            users.update(resolution.user_ids)
            resolved.extend((identifier, association) for association in resolution.associations)
        return users, resolved

    @classmethod
    def _observation_edges(cls, identity_graph: IdentityGraph,
                           observation: Observation) -> list[ResourceRelationship]:
        edges: list[ResourceRelationship] = []
        provenance = (observation.provenance.evidence_id,)
        users, resolved = cls._resolved_users(identity_graph, observation.identifiers,
                                              observation.observed_at)
        validity = (RelationshipValidity.VALIDATED if len(users) == 1
                    else RelationshipValidity.AMBIGUOUS)
        confidence = 1.0 if validity == RelationshipValidity.VALIDATED else 0.25
        identity_users = (sorted(users) if observation.nature == EvidenceNature.STATE_OBSERVATION
                          and RESOURCE_RE.match(observation.resource.resource_id) else ())
        for user_id in identity_users:
            associations = [association for _, association in resolved
                            if association.user_id == user_id]
            kinds = {identifier.kind for identifier, association in resolved
                     if association.user_id == user_id}
            historical = any(not association.active_at(observation.observed_at)
                             for association in associations)
            relationship_type = (
                RelationshipType.STABLE_USER_ID if IdentifierKind.USER_ID in kinds
                else RelationshipType.HISTORICAL_IDENTITY if historical
                else RelationshipType.EXPLICIT_IDENTITY_REFERENCE
            )
            identity_provenance = tuple(sorted({association.provenance_id for association in associations
                                                if association.provenance_id
                                                and not association.provenance_id.startswith("identity:")}))
            edges.append(ResourceRelationship(
                user_node(user_id), resource_node(observation.resource.resource_id),
                relationship_type, tuple(dict.fromkeys(provenance + identity_provenance)),
                observation.observed_at, None, observation.captured_at, confidence, validity,
                "unique normalized identity reference" if len(users) == 1
                else "resource observation resolves to multiple users",
            ))

        for _, key, value in _walk(observation.attributes):
            relationship_type = _relationship_type(key)
            if relationship_type is None:
                continue
            values = value if isinstance(value, (list, tuple)) else (value,)
            for candidate in values:
                if not isinstance(candidate, str) or not RESOURCE_RE.match(candidate):
                    continue
                if candidate.casefold() == observation.resource.resource_id.casefold():
                    continue
                source, target = resource_node(observation.resource.resource_id), resource_node(candidate)
                if key.casefold().startswith(("parent_", "source_")):
                    source, target = target, source
                edges.append(ResourceRelationship(
                    source, target, relationship_type, provenance,
                    observation.observed_at, None, observation.captured_at, 1.0,
                    RelationshipValidity.VALIDATED, f"explicit {key} field",
                ))

        edges.append(ResourceRelationship(
            resource_node(observation.resource.resource_id),
            physical_node(observation.resource.physical_system, observation.resource.resource_id),
            RelationshipType.PHYSICAL_REPLICA, provenance, observation.observed_at, None,
            observation.captured_at, 1.0, RelationshipValidity.VALIDATED,
            "observation names the logical resource and physical store",
        ))
        return edges

    @classmethod
    def _activity_edges(cls, identity_graph: IdentityGraph,
                        activity: ActivityEvent) -> list[ResourceRelationship]:
        provenance = (activity.activity_id,)
        activity_id = activity_node(activity.activity_id)
        resource_id = resource_node(activity.resource_id)
        if not RESOURCE_RE.match(activity.resource_id):
            return []
        edges = [ResourceRelationship(
            activity_id, resource_id, RelationshipType.OPERATION_READBACK, provenance,
            activity.event_time, None, activity.event_time, 0.5,
            RelationshipValidity.REJECTED,
            "operation names a target resource but is not ownership or state proof",
        )]
        identifiers = extract_identifiers({"details": activity.details})
        users, _ = cls._resolved_users(identity_graph, identifiers, activity.event_time)
        validity = (RelationshipValidity.VALIDATED if len(users) == 1
                    else RelationshipValidity.AMBIGUOUS)
        for user_id in sorted(users):
            edges.append(ResourceRelationship(
                user_node(user_id), resource_id,
                RelationshipType.EXPLICIT_IDENTITY_REFERENCE, provenance,
                activity.event_time, None, activity.event_time,
                1.0 if len(users) == 1 else 0.25, validity,
                "activity details contain a unique identity" if len(users) == 1
                else "activity details resolve to multiple users",
            ))
        return edges

    @staticmethod
    def _correlation_edges(observations: tuple[Observation, ...]) -> list[ResourceRelationship]:
        groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
        for observation in observations:
            if observation.correlation_id and CORRELATION_RE.match(observation.correlation_id):
                groups[(observation.provenance.evidence_id,
                        observation.correlation_id)].append(observation)
        edges: list[ResourceRelationship] = []
        for (_, correlation_id), values in sorted(groups.items()):
            resources = sorted({item.resource.resource_id for item in values
                                if RESOURCE_RE.match(item.resource.resource_id)})
            # A correlation token shared by a broad batch is not a request/response key.
            natures = {item.nature for item in values}
            if len(resources) != 2 or not {
                    EvidenceNature.OPERATION_EVENT, EvidenceNature.STATE_OBSERVATION}.issubset(natures):
                continue
            provenance = tuple(sorted({item.provenance.evidence_id for item in values}))
            captured_at = max(item.captured_at for item in values)
            valid_from = min(item.observed_at for item in values)
            for index, source in enumerate(resources):
                for target in resources[index + 1:]:
                    edges.append(ResourceRelationship(
                        resource_node(source), resource_node(target),
                        RelationshipType.OPERATION_READBACK, provenance,
                        valid_from, None, captured_at, 0.6,
                        RelationshipValidity.AMBIGUOUS,
                        f"shared correlation identifier {correlation_id}; correlation alone does not prove ownership",
                    ))
        return edges

    def resources_for_user(self, user_id: str, audit_at: datetime) -> tuple[str, ...]:
        """Return resources reachable solely through cutoff-valid, safe edges."""
        start = user_node(user_id)
        queue = deque([start])
        visited = {start}
        resources: set[str] = set()
        while queue:
            node = queue.popleft()
            for edge in self._adjacency.get(node, ()):
                if edge.validity not in SAFE_VALIDITIES or not edge.applicable_at(audit_at):
                    continue
                other = edge.target_id if edge.source_id == node else edge.source_id
                if other in visited:
                    continue
                visited.add(other)
                queue.append(other)
                if other.startswith("resource:"):
                    resources.add(other.removeprefix("resource:"))
        return tuple(sorted(resources))

    def supporting_edges(self, user_id: str, resource_id: str,
                         audit_at: datetime) -> tuple[ResourceRelationship, ...]:
        """Return safe direct edges for diagnostics and provenance validation."""
        nodes = {user_node(user_id), resource_node(resource_id)}
        return tuple(edge for edge in self.relationships
                     if {edge.source_id, edge.target_id} == nodes
                     and edge.validity in SAFE_VALIDITIES and edge.applicable_at(audit_at))

    def ambiguous_edges(self) -> tuple[ResourceRelationship, ...]:
        return tuple(edge for edge in self.relationships
                     if edge.validity == RelationshipValidity.AMBIGUOUS)
