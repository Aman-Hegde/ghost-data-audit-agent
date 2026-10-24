"""Grammar-tolerant parsing for line-oriented logs and handover text."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from ..errors import EvidenceParseError
from ..models import EvidenceManifestEntry, Observation, Provenance, Resource, TemporalSemantics
from ..normalization import parse_timestamp
from .common import category_for, extract_identifiers, immutable_attributes, infer_state

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*(.*)$")
KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)=(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s|]+)")
RESOURCE_RE = re.compile(r"\b(?:account|analytics|audit_record|backup|cache|data_flow|email_delivery|export|marketing|search|support|tombstone)_[A-Za-z0-9-]+\b", re.I)


def _kv(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, raw in KV_RE.findall(text):
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
            raw = raw[1:-1].replace(r'\"', '"')
        result[key] = raw
    return result


def _line_record(body: str) -> dict[str, Any]:
    json_start = body.find("{")
    if json_start >= 0:
        try:
            parsed = json.loads(body[json_start:])
            if isinstance(parsed, Mapping):
                return dict(parsed)
        except json.JSONDecodeError:
            pass
    record = _kv(body)
    parts = [part.strip() for part in body.split("|")]
    if len(parts) >= 5:
        record.setdefault("level", parts[0])
        record.setdefault("service", parts[1])
        record.setdefault("trace_id", parts[2])
        record.setdefault("event", parts[3])
    bracket = re.match(r"\[(\w+)]\s+\[([^]]+)]\s+\[([^]]+)]\s+([^:]+):", body)
    if bracket:
        record.setdefault("level", bracket.group(1))
        record.setdefault("service", bracket.group(2))
        record.setdefault("trace_id", bracket.group(3))
        record.setdefault("event", bracket.group(4).strip())
    if "resource_id" not in record:
        match = RESOURCE_RE.search(body)
        if match:
            record["resource_id"] = match.group(0)
    record["raw_message"] = body
    return record


def _system(record: Mapping[str, Any], resource_id: str) -> str:
    for key in ("system", "service", "target_system", "source_system", "function"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    prefix = resource_id.rsplit("_", 1)[0]
    return {"account": "account_service", "search": "search_service", "support": "support_platform",
            "analytics": "analytics_platform", "backup": "backup_service", "data_flow": "integration_service",
            "audit_record": "security_service", "export": "export_service", "tombstone": "identity_service"}.get(prefix, "unknown")


def parse_log_evidence(entry: EvidenceManifestEntry) -> list[Observation]:
    try:
        lines = entry.file_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise EvidenceParseError(f"{entry.file_id}: cannot read log evidence: {exc}") from exc
    observations = []
    for line_no, line in enumerate(lines, start=1):
        match = TIMESTAMP_RE.match(line.strip())
        if not match:
            continue
        observed_at = parse_timestamp(match.group(1), context=f"{entry.file_id}:line {line_no}")
        record = _line_record(match.group(2))
        resource_id = record.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            continue
        system = _system(record, resource_id)
        event = str(record.get("event") or record.get("record_type") or "LOG_EVENT")
        category = category_for(str(record.get("collection") or event), record)
        observations.append(Observation(
            Resource(resource_id, system, system, category), infer_state(record, category), observed_at,
            entry.captured_at, extract_identifiers(record), immutable_attributes(record),
            Provenance(entry.file_id, entry.file_path, entry.origin, f"line={line_no}", "log-v1"),
            TemporalSemantics.EVENT_OCCURRED,
        ))
    return sorted(observations, key=lambda item: (
        item.observed_at, item.resource.logical_system, item.resource.resource_id, item.provenance.locator,
    ))
