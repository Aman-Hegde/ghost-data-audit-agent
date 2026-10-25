"""Correlation-aware parsing for line-oriented operational evidence."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from ..errors import EvidenceParseError
from ..models import (EvidenceManifestEntry, EvidenceNature, Observation, OperationStatus,
                      Provenance, Resource, TemporalSemantics)
from ..normalization import parse_timestamp
from .common import category_for, extract_identifiers, immutable_attributes, infer_state

TIMESTAMP_RE = re.compile(r"^(?:-\s*)?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*(.*)$")
KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)=(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s|]+)")
RESOURCE_RE = re.compile(r"\b(?:account|analytics|audit_record|backup|cache|data_flow|email_delivery|export|marketing|search|support|tombstone)_[A-Za-z0-9-]+\b", re.I)
CORRELATION_KEYS = ("trace_id", "correlation_id", "request_id", "operation_id")


def _coerce(raw: str) -> Any:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1].replace(r'\"', '"')
    if raw.casefold() in {"true", "false"}:
        return raw.casefold() == "true"
    if raw.casefold() in {"null", "none"}:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def _kv(text: str) -> dict[str, Any]:
    return {key: _coerce(raw) for key, raw in KV_RE.findall(text)}


def _line_record(body: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    json_start = body.find("{")
    if json_start >= 0:
        try:
            parsed = json.loads(body[json_start:])
            if isinstance(parsed, Mapping):
                record.update(parsed)
        except json.JSONDecodeError:
            pass
    record.update({key: value for key, value in _kv(body).items() if key not in record})
    parts = [part.strip() for part in body.split("|")]
    if len(parts) >= 6 and not parts[0]:
        record.setdefault("system", parts[1])
        record.setdefault("resource_id", parts[2])
        record.setdefault("record_type", parts[3])
        record.setdefault("result", parts[4])
        record.setdefault("subject_reference", parts[5])
    if len(parts) >= 4:
        record.setdefault("level", parts[0]); record.setdefault("service", parts[1])
        record.setdefault("trace_id", parts[2]); record.setdefault("event", parts[3])
    bracket = re.match(r"\[(\w+)]\s+\[([^]]+)]\s+\[([^]]+)]\s+([^:]+):", body)
    if bracket:
        record.setdefault("level", bracket.group(1)); record.setdefault("service", bracket.group(2))
        record.setdefault("trace_id", bracket.group(3)); record.setdefault("event", bracket.group(4).strip())
    if "resource_id" not in record:
        match = RESOURCE_RE.search(body)
        if match:
            record["resource_id"] = match.group(0)
    record["raw_message"] = body
    return record


def _system(record: Mapping[str, Any], resource_id: str) -> str:
    for key in ("system", "service", "target_system", "source_system", "function"):
        if isinstance(record.get(key), str) and record[key]:
            return str(record[key])
    prefix = resource_id.rsplit("_", 1)[0]
    return {"account": "account_service", "search": "search_service", "support": "support_platform",
            "analytics": "analytics_platform", "backup": "backup_service", "data_flow": "integration_service",
            "audit_record": "security_service", "export": "export_service",
            "tombstone": "identity_service"}.get(prefix, "unknown")


def _correlation(record: Mapping[str, Any]) -> str:
    for key in CORRELATION_KEYS:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _operation(event: str, record: Mapping[str, Any]) -> tuple[EvidenceNature, OperationStatus]:
    text = " ".join((event, str(record.get("result", "")), str(record.get("status", "")),
                     str(record.get("raw_message", "")))).casefold()
    direct_state = any(token in text for token in
                       ("lookup", "read", "query", "scan", "check", "snapshot", "fetch", "evaluated", "heartbeat"))
    mutating = any(token in text for token in
                   ("delete", "redact", "anonym", "sync", "replic", "restore", "recreat", "create"))
    if direct_state and ("completed" in text or any(key in record for key in
                            ("rows", "hits", "status_code", "http_status", "enabled", "restore_allowed",
                             "download_available", "result", "matched_value", "eligible", "deletion_block"))):
        return EvidenceNature.STATE_OBSERVATION, OperationStatus.NOT_APPLICABLE
    if not mutating:
        return EvidenceNature.HISTORICAL_FACT, OperationStatus.NOT_APPLICABLE
    if any(token in text for token in ("failed", "failure", "error", "denied")):
        return EvidenceNature.OPERATION_EVENT, OperationStatus.FAILED
    if any(token in text for token in ("pending", "queued", "scheduled", "started", "attempt")):
        return EvidenceNature.OPERATION_EVENT, OperationStatus.PENDING
    if any(token in text for token in ("partial", "partially")):
        return EvidenceNature.OPERATION_EVENT, OperationStatus.PARTIAL
    if any(token in text for token in ("success", "succeeded", "completed", "deleted", "restored", "created")):
        return EvidenceNature.OPERATION_EVENT, OperationStatus.SUCCEEDED
    return EvidenceNature.OPERATION_EVENT, OperationStatus.ATTEMPTED


def parse_log_evidence(entry: EvidenceManifestEntry) -> list[Observation]:
    try:
        lines = entry.file_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise EvidenceParseError(f"{entry.file_id}: cannot read log evidence: {exc}") from exc
    parsed: list[tuple[int, Any, dict[str, Any]]] = []
    groups: dict[str, list[int]] = defaultdict(list)
    for line_no, line in enumerate(lines, start=1):
        match = TIMESTAMP_RE.match(line.strip())
        if not match:
            # A physical continuation is preserved on the preceding event.
            if parsed and line.strip():
                parsed[-1][2]["raw_message"] += "\n" + line.strip()
                parsed[-1][2]["_end_line"] = line_no
            continue
        timestamp = parse_timestamp(match.group(1), context=f"{entry.file_id}:line {line_no}")
        record = _line_record(match.group(2))
        record["_end_line"] = line_no
        parsed.append((line_no, timestamp, record))
        if _correlation(record):
            groups[_correlation(record)].append(len(parsed) - 1)

    observations: list[Observation] = []
    for index, (line_no, observed_at, original) in enumerate(parsed):
        record = dict(original)
        correlation = _correlation(record)
        group = groups.get(correlation, [])
        # Carry stable context from related request/response lines without overwriting response facts.
        for related_index in group:
            if related_index > index:
                break
            for key, value in parsed[related_index][2].items():
                if key not in {"raw_message", "event", "result", "status"}:
                    record.setdefault(key, value)
        resource_id = record.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            continue
        event = str(record.get("event") or record.get("record_type") or "LOG_EVENT")
        nature, operation_status = _operation(event, record)
        semantics = TemporalSemantics.EVENT_OCCURRED
        if entry.file_path.suffix.casefold() == ".txt" and record.get("record_type") and record.get("result"):
            nature, operation_status = EvidenceNature.STATE_OBSERVATION, OperationStatus.NOT_APPLICABLE
            semantics = TemporalSemantics.POINT_IN_TIME
        system = _system(record, resource_id)
        category = category_for(str(record.get("collection") or event), record)
        last_line = int(original.get("_end_line", line_no))
        record.pop("_end_line", None)
        observations.append(Observation(
            Resource(resource_id, system, system, category), infer_state(record, category), observed_at,
            entry.captured_at, extract_identifiers(record), immutable_attributes(record),
            Provenance(entry.file_id, entry.file_path, entry.origin,
                       f"lines={line_no}-{last_line}" if last_line != line_no else f"line={line_no}",
                       "log-correlator-v2"), semantics, nature,
            correlation, operation_status,
        ))
    return sorted(observations, key=lambda item: (
        item.observed_at, item.resource.logical_system, item.resource.resource_id, item.provenance.locator,
    ))
