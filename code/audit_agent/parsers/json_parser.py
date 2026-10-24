"""Adapters for structured JSON evidence families."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..errors import EvidenceParseError
from ..models import EvidenceManifestEntry, Observation, Provenance, Resource, TemporalSemantics
from .common import category_for, extract_identifiers, immutable_attributes, infer_state, observation_time, system_for


def _make(entry: EvidenceManifestEntry, record: Mapping[str, Any], *, logical_system: str,
          physical_system: str, collection: str, locator: str,
          semantics: TemporalSemantics = TemporalSemantics.POINT_IN_TIME) -> Observation | None:
    resource_id = record.get("resource_id")
    if not isinstance(resource_id, str) or not resource_id:
        return None
    category = category_for(collection, record)
    return Observation(
        Resource(resource_id, logical_system, physical_system, category),
        infer_state(record, category),
        observation_time(record, fallback=entry.captured_at, context=f"{entry.file_id}:{locator}"),
        entry.captured_at,
        extract_identifiers(record),
        immutable_attributes(record),
        Provenance(entry.file_id, entry.file_path, entry.origin, locator, "json-v1"),
        semantics,
    )


def _snapshot_bundle(entry: EvidenceManifestEntry, data: Mapping[str, Any]) -> list[Observation]:
    result = []
    for s_index, snapshot in enumerate(data.get("snapshots", [])):
        if not isinstance(snapshot, Mapping):
            continue
        collection = str(snapshot.get("collection", "unknown"))
        store = str(snapshot.get("data_store", "unknown"))
        for r_index, record in enumerate(snapshot.get("records", [])):
            if not isinstance(record, Mapping):
                continue
            enriched = dict(record)
            enriched.setdefault("captured_at", snapshot.get("captured_at"))
            item = _make(entry, enriched, logical_system=system_for(collection, enriched, store),
                         physical_system=store, collection=collection,
                         locator=f"$.snapshots[{s_index}].records[{r_index}]")
            if item:
                result.append(item)
    return result


def _service_exports(entry: EvidenceManifestEntry, data: Mapping[str, Any]) -> list[Observation]:
    result = []
    exports = data.get("service_exports", {})
    if not isinstance(exports, Mapping):
        return result
    for system, groups in exports.items():
        if not isinstance(groups, Mapping):
            continue
        for collection, records in groups.items():
            if not isinstance(records, list):
                continue
            for index, record in enumerate(records):
                if not isinstance(record, Mapping):
                    continue
                item = _make(entry, record, logical_system=str(system), physical_system=str(system),
                             collection=str(collection), locator=f"$.service_exports.{system}.{collection}[{index}]")
                if item:
                    result.append(item)
    return result


def _generic_records(entry: EvidenceManifestEntry, data: Mapping[str, Any]) -> list[Observation]:
    records = data.get("records", [])
    if not isinstance(records, list):
        return []
    collection = str(data.get("collection", "records"))
    result = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        logical = system_for(collection, record, str(data.get("source", entry.origin)))
        semantics = (TemporalSemantics.HISTORICAL_RECORD
                     if collection == "operational_record_history" or "recorded_at" in record
                     else TemporalSemantics.POINT_IN_TIME)
        item = _make(entry, record, logical_system=logical, physical_system=str(data.get("source", entry.origin)),
                     collection=collection, locator=f"$.records[{index}]", semantics=semantics)
        if item:
            result.append(item)
    return result


def parse_json_evidence(entry: EvidenceManifestEntry) -> list[Observation]:
    try:
        data = json.loads(entry.file_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceParseError(f"{entry.file_id}: invalid JSON evidence: {exc}") from exc
    if not isinstance(data, Mapping):
        raise EvidenceParseError(f"{entry.file_id}: JSON root must be an object")
    if "snapshots" in data:
        observations = _snapshot_bundle(entry, data)
    elif "service_exports" in data:
        observations = _service_exports(entry, data)
    elif "records" in data:
        observations = _generic_records(entry, data)
    else:
        observations = []
    return sorted(observations, key=lambda item: (
        item.observed_at, item.resource.logical_system, item.resource.physical_system,
        item.resource.resource_id, item.provenance.locator,
    ))
