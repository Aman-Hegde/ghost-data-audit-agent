"""Deterministic multi-key index for normalized evidence observations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

from .models import IdentifierKind, Observation
from .normalization import normalize_email, normalize_identifier
from .temporal import observation_usable_at


def _observation_key(item: Observation) -> tuple:
    return (item.observed_at, item.captured_at, item.provenance.evidence_id,
            item.resource.logical_system, item.resource.physical_system,
            item.resource.resource_id, item.provenance.locator)


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(child)) for key, child in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _deduplication_key(item: Observation) -> tuple:
    """Exact semantic/provenance identity; conflicting states remain distinct."""
    return (
        item.resource.resource_id, item.resource.logical_system, item.resource.physical_system,
        item.resource.category, item.state, item.observed_at, item.captured_at,
        tuple((identifier.kind.value, identifier.normalized_value, identifier.field_path)
              for identifier in item.identifiers), _freeze(dict(item.attributes)),
        item.provenance.evidence_id, str(item.provenance.source_path), item.provenance.locator,
        item.temporal_semantics.value, item.nature.value, item.correlation_id,
        item.operation_status.value,
    )


class EvidenceStore:
    def __init__(self, observations: Iterable[Observation] = ()):
        self._all: list[Observation] = []
        self._by_user: dict[str, list[Observation]] = defaultdict(list)
        self._by_email: dict[str, list[Observation]] = defaultdict(list)
        self._by_resource: dict[str, list[Observation]] = defaultdict(list)
        self._by_system: dict[str, list[Observation]] = defaultdict(list)
        self._by_identifier: dict[tuple[IdentifierKind, str], list[Observation]] = defaultdict(list)
        self._seen: set[tuple] = set()
        self.duplicate_count = 0
        for observation in observations:
            self.add(observation)
        self._sort()

    def add(self, observation: Observation) -> None:
        key = _deduplication_key(observation)
        if key in self._seen:
            self.duplicate_count += 1
            return
        self._seen.add(key)
        self._all.append(observation)
        self._by_resource[observation.resource.resource_id].append(observation)
        self._by_system[observation.resource.logical_system].append(observation)
        if observation.resource.physical_system != observation.resource.logical_system:
            self._by_system[observation.resource.physical_system].append(observation)
        indexed: set[tuple[IdentifierKind, str]] = set()
        for identifier in observation.identifiers:
            key = (identifier.kind, identifier.normalized_value)
            if key in indexed:
                continue
            indexed.add(key)
            self._by_identifier[key].append(observation)
            if identifier.kind == IdentifierKind.USER_ID:
                self._by_user[identifier.normalized_value].append(observation)
            elif identifier.kind == IdentifierKind.EMAIL:
                self._by_email[identifier.normalized_value].append(observation)

    def _sort(self) -> None:
        self._all.sort(key=_observation_key)
        for index in (self._by_user, self._by_email, self._by_resource, self._by_system, self._by_identifier):
            for values in index.values():
                values.sort(key=_observation_key)

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(self._all)

    def by_user_id(self, user_id: str) -> tuple[Observation, ...]:
        key = normalize_identifier(IdentifierKind.USER_ID, user_id)
        return tuple(self._by_user.get(key, ()))

    def by_email(self, email: str) -> tuple[Observation, ...]:
        return tuple(self._by_email.get(normalize_email(email), ()))

    def by_resource_id(self, resource_id: str) -> tuple[Observation, ...]:
        return tuple(self._by_resource.get(resource_id, ()))

    def by_system_id(self, system_id: str) -> tuple[Observation, ...]:
        return tuple(self._by_system.get(system_id, ()))

    def by_identifier(self, kind: IdentifierKind, value: str) -> tuple[Observation, ...]:
        key = normalize_identifier(kind, value)
        return tuple(self._by_identifier.get((kind, key), ()))

    @staticmethod
    def at(observations: Iterable[Observation], audit_at: datetime, *,
           allow_retrospective: bool = False) -> tuple[Observation, ...]:
        return tuple(item for item in observations
                     if observation_usable_at(item, audit_at, allow_retrospective=allow_retrospective))
