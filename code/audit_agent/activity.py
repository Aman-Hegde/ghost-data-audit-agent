"""Convert reported workflow activity into non-authoritative operation events."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import (ActivityEvent, EvidenceNature, Observation, OperationStatus,
                     Provenance, Resource, TemporalSemantics)
from .parsers.common import extract_identifiers, immutable_attributes


def _status(value: str) -> OperationStatus:
    normalized = value.strip().casefold()
    if normalized in {"success", "succeeded", "complete", "completed"}:
        return OperationStatus.SUCCEEDED
    if normalized in {"failed", "failure", "error", "denied"}:
        return OperationStatus.FAILED
    if normalized in {"pending", "queued", "scheduled"}:
        return OperationStatus.PENDING
    if normalized in {"partial", "partially_complete"}:
        return OperationStatus.PARTIAL
    return OperationStatus.ATTEMPTED


def activity_observations(events: Iterable[ActivityEvent], source_path: Path) -> tuple[Observation, ...]:
    """Preserve activity IDs while ensuring reported outcomes never become state proof."""
    output = []
    for event in events:
        attributes = {
            "activity_id": event.activity_id, "event_type": event.event_type,
            "source_system": event.source_system, "target_system": event.target_system,
            "reported_result": event.reported_result, "details": event.details,
        }
        output.append(Observation(
            Resource(event.resource_id, event.target_system or event.source_system,
                     event.target_system or event.source_system, "WORKFLOW_ACTIVITY"),
            event.reported_result.upper() or "REPORTED", event.event_time, event.event_time,
            extract_identifiers(attributes), immutable_attributes(attributes),
            Provenance(event.activity_id, source_path, "system_activity", "csv_row", "activity-csv-v1"),
            TemporalSemantics.EVENT_OCCURRED, EvidenceNature.OPERATION_EVENT,
            event.activity_id, _status(event.reported_result),
        ))
    return tuple(sorted(output, key=lambda item: (item.observed_at, item.provenance.evidence_id)))
