"""Temporal eligibility and non-destructive resource reconstruction."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import Observation, ResourceHistory, TemporalSemantics


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
