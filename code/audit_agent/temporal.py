"""Temporal eligibility and non-destructive resource reconstruction."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import (EvidenceNature, Observation, OperationStatus, ResourceHistory,
                     TemporalSemantics, TimelineAssessment, TimelineStatus)


def observation_usable_at(observation: Observation, audit_at: datetime, *,
                          allow_retrospective: bool = False) -> bool:
    """Apply the capture-time gate, with explicit semantics for retrospective facts.

    Point-in-time state captured after the cutoff is never backdated. Event or
    historical-record evidence may be used retrospectively only when the caller
    explicitly requests it, and only for its event/history fact—not as proof of
    current state.
    """
    if observation.observed_at > audit_at:
        return False
    if observation.captured_at <= audit_at:
        return True
    return (allow_retrospective and observation.temporal_semantics
            in {TemporalSemantics.EVENT_OCCURRED, TemporalSemantics.HISTORICAL_RECORD})


def reconstruct_resource_history(resource_id: str, observations: Iterable[Observation],
                                 audit_at: datetime) -> ResourceHistory:
    eligible = sorted(
        (item for item in observations
         if item.resource.resource_id == resource_id and observation_usable_at(item, audit_at)),
        key=lambda item: (item.observed_at, item.captured_at, item.provenance.evidence_id, item.provenance.locator),
    )
    latest = {}
    for item in eligible:
        latest[item.resource.physical_system] = item
    states = {item.state for item in latest.values()}
    return ResourceHistory(resource_id, dict(sorted(latest.items())), tuple(eligible), len(states) > 1)


def assess_resource_timeline(resource_id: str, observations: Iterable[Observation],
                             audit_at: datetime, *, allow_retrospective: bool = False) -> TimelineAssessment:
    """Reconcile peer stores without granting automatic authority to a primary.

    Later-captured event/history facts can describe an earlier event when explicitly
    enabled, but they never become point-in-time state observations.
    """
    eligible = sorted(
        (item for item in observations if item.resource.resource_id == resource_id
         and observation_usable_at(item, audit_at, allow_retrospective=allow_retrospective)),
        key=lambda item: (item.observed_at, item.captured_at, item.provenance.evidence_id,
                          item.provenance.locator),
    )
    states = [item for item in eligible if item.nature == EvidenceNature.STATE_OBSERVATION
              and item.captured_at <= audit_at]
    operations = [item for item in eligible if item.nature == EvidenceNature.OPERATION_EVENT]
    by_physical: dict[str, list[Observation]] = {}
    for item in states:
        by_physical.setdefault(item.resource.physical_system, []).append(item)
    latest: dict[str, Observation] = {}
    conflicts: list[tuple[Observation, Observation]] = []
    for system, values in sorted(by_physical.items()):
        max_time = max(item.observed_at for item in values)
        contemporaneous = [item for item in values if item.observed_at == max_time]
        latest[system] = contemporaneous[-1]
        for left_index, left in enumerate(contemporaneous):
            for right in contemporaneous[left_index + 1:]:
                if left.state != right.state:
                    conflicts.append((left, right))
    current_states = {item.state for item in latest.values()}
    if conflicts or len(current_states) > 1:
        status, best_state = TimelineStatus.CONTRADICTORY, None
        if len(current_states) > 1:
            ordered = list(latest.values())
            for left_index, left in enumerate(ordered):
                for right in ordered[left_index + 1:]:
                    if left.state != right.state:
                        conflicts.append((left, right))
    elif current_states:
        status, best_state = TimelineStatus.RESOLVED, next(iter(current_states))
    else:
        status, best_state = TimelineStatus.UNRESOLVED, None

    delete_times = [item.observed_at for item in operations
                    if item.operation_status == OperationStatus.SUCCEEDED
                    and "delete" in str(item.attributes).casefold()]
    recreate_times = [item.observed_at for item in operations
                      if item.operation_status == OperationStatus.SUCCEEDED
                      and any(word in str(item.attributes).casefold()
                              for word in ("sync", "replic", "restore", "recreat", "create"))]
    recreation = any(delete < recreate for delete in delete_times for recreate in recreate_times)
    if recreation:
        recreation = any(item.state in {"PRESENT", "ACTIVE"} and
                         any(delete < item.observed_at for delete in delete_times) for item in states)
    return TimelineAssessment(resource_id, audit_at, status, best_state, latest, tuple(states),
                              tuple(operations), tuple(conflicts), recreation)
