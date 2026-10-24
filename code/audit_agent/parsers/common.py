"""Shared evidence normalization helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Iterable, Mapping

from ..models import Identifier, IdentifierKind
from ..normalization import normalize_identifier, parse_timestamp

EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
USER_RE = re.compile(r"\buser_[A-Za-z0-9-]+\b", re.I)
HASH_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")

COLLECTION_CATEGORIES = {
    "customer_profiles": "USER_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY",
    "customer_analytics_reports": "ANALYTICS_PROFILE",
    "support_conversations": "SUPPORT_MESSAGE",
    "support_records": "SUPPORT_MESSAGE",
    "ticket_attachments": "SUPPORT_ATTACHMENT",
    "customer_export_jobs": "USER_EXPORT",
    "customer_exports": "USER_EXPORT",
    "connector_configurations": "DATA_FLOW",
    "connector_subscriptions": "DATA_FLOW",
    "backup_catalog": "BACKUP_ARCHIVE",
    "backup_restore_entries": "BACKUP_ARCHIVE",
    "security_audit_events": "SECURITY_AUDIT_LOG",
    "security_audit_records": "SECURITY_AUDIT_LOG",
    "retained_order_records": "LEGAL_HOLD_RECORD",
    "deleted_customer_references": "ACCOUNT_TOMBSTONE",
    "customer_analytics_profiles": "ANALYTICS_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY",
    "profile_lookups": "USER_PROFILE",
    "profiles": "ANALYTICS_PROFILE",
    "restore_entries": "BACKUP_ARCHIVE",
    "exports": "USER_EXPORT",
    "connectors": "DATA_FLOW",
    "index_queries": "SEARCH_INDEX_ENTRY",
    "audit_records": "SECURITY_AUDIT_LOG",
}

TABLE_SYSTEMS = {
    "customer_profiles": "account_service",
    "customer_search_documents": "search_service",
    "search_documents_primary": "search_service",
    "customer_analytics_profiles": "analytics_platform",
    "support_records": "support_platform",
    "customer_exports": "export_service",
    "connector_subscriptions": "integration_service",
    "backup_restore_entries": "backup_service",
    "security_audit_records": "security_service",
    "deleted_customer_references": "identity_service",
}


def category_for(collection: str, record: Mapping[str, Any]) -> str:
    explicit = record.get("record_type")
    if isinstance(explicit, str) and explicit:
        return explicit.upper()
    return COLLECTION_CATEGORIES.get(collection, collection.upper() if collection else "UNKNOWN")


def system_for(collection: str, record: Mapping[str, Any], fallback: str) -> str:
    for key in ("origin_system", "system", "data_store"):
        if isinstance(record.get(key), str) and record[key]:
            return str(record[key])
    return TABLE_SYSTEMS.get(collection, fallback)


def parse_optional_timestamp(value: Any, *, fallback: datetime, context: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return parse_timestamp(value, context=context)
    except Exception:
        return fallback


def observation_time(record: Mapping[str, Any], *, fallback: datetime, context: str) -> datetime:
    for key in ("observed_at", "captured_at", "updated_at", "recorded_at", "created_at", "event_time", "timestamp"):
        if key in record:
            return parse_optional_timestamp(record[key], fallback=fallback, context=f"{context}:{key}")
    return fallback


def infer_state(record: Mapping[str, Any], category: str) -> str:
    result = str(record.get("result", "")).upper()
    if record.get("status_code") == 404 or result in {"NOT_FOUND", "MISSING", "ABSENT"}:
        return "ABSENT"
    hits = record.get("hits")
    if isinstance(hits, Mapping) and isinstance(hits.get("total"), int):
        return "PRESENT" if hits["total"] > 0 else "ABSENT"
    if "enabled" in record and isinstance(record["enabled"], (bool, int)):
        return "ACTIVE" if bool(record["enabled"]) else "DISABLED"
    if "restore_allowed" in record and isinstance(record["restore_allowed"], (bool, int)):
        return "ACTIVE" if bool(record["restore_allowed"]) else "BLOCKED"
    if "download_available" in record and isinstance(record["download_available"], (bool, int)):
        return "PRESENT" if bool(record["download_available"]) else "ABSENT"
    if record.get("status_code") == 200 or result in {"FOUND", "PRESENT"}:
        return "PRESENT"
    direct = [record.get(name) for name in ("name", "full_name", "email", "phone", "email_hash")]
    if category == "ACCOUNT_TOMBSTONE" and direct and all(value in (None, "") for value in direct):
        return "REDACTED"
    if category in {"ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"} and direct and all(value in (None, "") for value in direct):
        return "ANONYMIZED"
    return result or "PRESENT"


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def extract_identifiers(record: Mapping[str, Any]) -> tuple[Identifier, ...]:
    found: dict[tuple[IdentifierKind, str, str], Identifier] = {}

    def add(kind: IdentifierKind, raw: str, path: str) -> None:
        normalized = normalize_identifier(kind, raw)
        if normalized:
            found[(kind, normalized, path)] = Identifier(kind, raw, normalized, path)

    for path, key, value in _walk(record):
        if not isinstance(value, str) or not value:
            continue
        lower = key.casefold()
        if lower in {"user_id", "subject_reference", "customer_reference", "customer_ref"} and value.casefold().startswith("user_"):
            add(IdentifierKind.USER_ID, value, path)
        if "email_hash" in lower:
            add(IdentifierKind.EMAIL_HASH, value, path)
        if "phone" in lower:
            add(IdentifierKind.PHONE, value, path)
        if lower in {"name", "full_name", "display_name", "requester_name"}:
            add(IdentifierKind.NAME, value, path)
        for match in EMAIL_RE.findall(value):
            add(IdentifierKind.EMAIL, match, path)
        for match in USER_RE.findall(value):
            add(IdentifierKind.USER_ID, match, path)
        for match in HASH_RE.findall(value):
            add(IdentifierKind.EMAIL_HASH, match, path)
        if lower in {"record_json", "document"} and value[:1] in "[{":
            try:
                nested = json.loads(value)
                if isinstance(nested, Mapping):
                    for item in extract_identifiers(nested):
                        found[(item.kind, item.normalized_value, path + item.field_path[1:])] = item
            except json.JSONDecodeError:
                pass
    return tuple(sorted(found.values(), key=lambda item: (item.kind.value, item.normalized_value, item.field_path)))


def immutable_attributes(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Round-trip through JSON to detach sqlite rows and mutable parser objects."""
    return json.loads(json.dumps(record, ensure_ascii=False, default=str))
