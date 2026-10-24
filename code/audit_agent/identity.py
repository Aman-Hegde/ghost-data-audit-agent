"""Collision-safe, timestamp-aware identity reconstruction."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .errors import DataValidationError
from .models import (
    IdentifierKind, IdentityAssociation, IdentityEvent, IdentityResolution,
    IdentitySnapshot,
)
from .normalization import normalize_identifier

FIELD_KINDS = {
    "name": IdentifierKind.NAME,
    "email": IdentifierKind.EMAIL,
    "phone": IdentifierKind.PHONE,
    "email_hash": IdentifierKind.EMAIL_HASH,
}


class IdentityGraph:
    """Indexes exact identifiers while preserving cross-user collisions."""

    def __init__(self, snapshots: Iterable[IdentitySnapshot], events: Iterable[IdentityEvent]):
        self.snapshots = {item.user_id: item for item in snapshots}
        if not self.snapshots:
            raise DataValidationError("identity graph requires at least one identity snapshot")
        grouped: dict[tuple[str, str], list[IdentityEvent]] = defaultdict(list)
        for event in events:
            if event.user_id not in self.snapshots:
                raise DataValidationError(f"identity event {event.audit_id} references unknown user {event.user_id}")
            grouped[(event.user_id, event.field_name)].append(event)

        associations: list[IdentityAssociation] = []
        for snapshot in self.snapshots.values():
            associations.append(self._association(snapshot.user_id, IdentifierKind.USER_ID, snapshot.user_id,
                                                  None, None, f"identity:{snapshot.user_id}"))
            for field_name, kind in FIELD_KINDS.items():
                current = getattr(snapshot, field_name)
                field_events = sorted(grouped.get((snapshot.user_id, field_name), []), key=lambda item: (item.event_time, item.audit_id))
                associations.extend(self._field_history(snapshot.user_id, kind, current, field_events))

        self.associations = tuple(sorted(associations, key=self._association_key))
        index: dict[tuple[IdentifierKind, str], list[IdentityAssociation]] = defaultdict(list)
        by_user: dict[str, list[IdentityAssociation]] = defaultdict(list)
        for association in self.associations:
            if association.normalized_value:
                index[(association.kind, association.normalized_value)].append(association)
            by_user[association.user_id].append(association)
        self._index = {key: tuple(value) for key, value in index.items()}
        self._by_user = {key: tuple(value) for key, value in by_user.items()}

    @staticmethod
    def _association_key(item: IdentityAssociation) -> tuple:
        floor = datetime.min.replace(tzinfo=timezone.utc)
        return (item.user_id, item.kind.value, item.valid_from or floor, item.normalized_value, item.provenance_id)

    @staticmethod
    def _association(user_id: str, kind: IdentifierKind, value: str, start: datetime | None,
                     end: datetime | None, provenance_id: str) -> IdentityAssociation:
        return IdentityAssociation(user_id, kind, value, normalize_identifier(kind, value), start, end, provenance_id)

    def _field_history(self, user_id: str, kind: IdentifierKind, current: str,
                       events: list[IdentityEvent]) -> list[IdentityAssociation]:
        if not events:
            return [self._association(user_id, kind, current, None, None, f"identity:{user_id}")]
        result = []
        expected = events[0].old_value
        result.append(self._association(user_id, kind, expected, None, events[0].event_time, events[0].audit_id))
        for position, event in enumerate(events):
            if normalize_identifier(kind, event.old_value) != normalize_identifier(kind, expected):
                raise DataValidationError(
                    f"identity history discontinuity for {user_id}/{kind.value} at {event.audit_id}: "
                    f"expected old value {expected!r}, found {event.old_value!r}"
                )
            next_time = events[position + 1].event_time if position + 1 < len(events) else None
            result.append(self._association(user_id, kind, event.new_value, event.event_time, next_time, event.audit_id))
            expected = event.new_value
        if normalize_identifier(kind, current) != normalize_identifier(kind, expected):
            raise DataValidationError(
                f"identity snapshot for {user_id}/{kind.value} is {current!r}, but audit history ends at {expected!r}"
            )
        return result

    def resolve(self, kind: IdentifierKind, value: str, *, at: datetime | None = None,
                include_historical: bool = True) -> IdentityResolution:
        normalized = normalize_identifier(kind, value)
        candidates = self._index.get((kind, normalized), ())
        if at is not None:
            if include_historical:
                candidates = tuple(item for item in candidates if item.valid_from is None or item.valid_from <= at)
            else:
                candidates = tuple(item for item in candidates if item.active_at(at))
        user_ids = tuple(sorted({item.user_id for item in candidates}))
        return IdentityResolution(normalized, user_ids, tuple(candidates))

    def resolve_email(self, value: str, *, at: datetime | None = None,
                      include_historical: bool = True) -> IdentityResolution:
        return self.resolve(IdentifierKind.EMAIL, value, at=at, include_historical=include_historical)

    def identifiers_for_user(self, user_id: str, *, known_by: datetime | None = None) -> tuple[IdentityAssociation, ...]:
        values = self._by_user.get(user_id, ())
        if known_by is not None:
            values = tuple(item for item in values if item.valid_from is None or item.valid_from <= known_by)
        return values
