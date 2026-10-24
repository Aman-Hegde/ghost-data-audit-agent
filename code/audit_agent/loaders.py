"""Strict CSV loaders for every participant-facing structured table."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from .errors import DataValidationError
from .models import (
    ActivityEvent, DeletionRequest, EvidenceManifestEntry, IdentityEvent,
    IdentitySnapshot, PolicyRule,
)
from .normalization import natural_id_key, parse_timestamp

T = TypeVar("T")

REQUEST_COLUMNS = ("case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text")
IDENTITY_COLUMNS = ("user_id", "name", "email", "phone", "email_hash", "updated_at")
AUDIT_COLUMNS = ("audit_id", "user_id", "event_time", "field_name", "old_value", "new_value")
ACTIVITY_COLUMNS = ("activity_id", "event_time", "event_type", "source_system", "target_system", "resource_id", "reported_result", "details")
RULE_COLUMNS = ("rule_id", "data_category", "condition", "required_action")
MANIFEST_COLUMNS = ("file_id", "file_path", "origin", "captured_at")


def _read_csv(path: Path, expected: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise DataValidationError(f"CSV file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = tuple(reader.fieldnames or ())
        if actual != expected:
            raise DataValidationError(f"{path}: expected columns {expected}, found {actual}")
        rows = []
        for line_no, row in enumerate(reader, start=2):
            if None in row:
                raise DataValidationError(f"{path}:{line_no}: too many CSV fields")
            missing = [name for name in expected if row[name] is None]
            if missing:
                raise DataValidationError(f"{path}:{line_no}: missing fields {missing}")
            rows.append(row)
    return rows


def _unique(items: Iterable[T], key: Callable[[T], str], *, path: Path) -> list[T]:
    output, seen = [], set()
    for item in items:
        value = key(item)
        if not value:
            raise DataValidationError(f"{path}: identifier cannot be empty")
        if value in seen:
            raise DataValidationError(f"{path}: duplicate identifier {value!r}")
        seen.add(value)
        output.append(item)
    return output


def load_requests(path: Path) -> list[DeletionRequest]:
    allowed = {"COMPLETE", "PARTIALLY_COMPLETE", "NOT_STARTED"}
    result = []
    for n, row in enumerate(_read_csv(path, REQUEST_COLUMNS), start=2):
        if row["reported_status"] not in allowed:
            raise DataValidationError(f"{path}:{n}: invalid reported_status {row['reported_status']!r}")
        result.append(DeletionRequest(
            row["case_id"], row["email"], parse_timestamp(row["requested_at"], context=f"{path}:{n}:requested_at"),
            row["reported_status"], parse_timestamp(row["reported_at"], context=f"{path}:{n}:reported_at"),
            parse_timestamp(row["audit_at"], context=f"{path}:{n}:audit_at"), row["request_text"],
        ))
    return sorted(_unique(result, lambda x: x.case_id, path=path), key=lambda x: natural_id_key(x.case_id))


def load_identities(path: Path) -> list[IdentitySnapshot]:
    items = [IdentitySnapshot(r["user_id"], r["name"], r["email"], r["phone"], r["email_hash"],
                              parse_timestamp(r["updated_at"], context=f"{path}:updated_at"))
             for r in _read_csv(path, IDENTITY_COLUMNS)]
    return sorted(_unique(items, lambda x: x.user_id, path=path), key=lambda x: natural_id_key(x.user_id))


def load_identity_events(path: Path) -> list[IdentityEvent]:
    allowed = {"email", "email_hash", "phone", "name"}
    items = []
    for n, r in enumerate(_read_csv(path, AUDIT_COLUMNS), start=2):
        if r["field_name"] not in allowed:
            raise DataValidationError(f"{path}:{n}: unsupported identity field {r['field_name']!r}")
        items.append(IdentityEvent(r["audit_id"], r["user_id"], parse_timestamp(r["event_time"], context=f"{path}:{n}:event_time"),
                                   r["field_name"], r["old_value"], r["new_value"]))
    return sorted(_unique(items, lambda x: x.audit_id, path=path), key=lambda x: (x.event_time, natural_id_key(x.audit_id)))


def load_activity(path: Path) -> list[ActivityEvent]:
    items = [ActivityEvent(r["activity_id"], parse_timestamp(r["event_time"], context=f"{path}:event_time"),
                           r["event_type"], r["source_system"], r["target_system"], r["resource_id"],
                           r["reported_result"], r["details"]) for r in _read_csv(path, ACTIVITY_COLUMNS)]
    return sorted(_unique(items, lambda x: x.activity_id, path=path), key=lambda x: (x.event_time, natural_id_key(x.activity_id)))


def load_policy_rules(path: Path) -> list[PolicyRule]:
    allowed = {"DELETE", "REDACT", "ANONYMIZE", "RETAIN"}
    items = []
    for n, r in enumerate(_read_csv(path, RULE_COLUMNS), start=2):
        if r["required_action"] not in allowed:
            raise DataValidationError(f"{path}:{n}: unsupported required_action {r['required_action']!r}")
        items.append(PolicyRule(r["rule_id"], r["data_category"], r["condition"], r["required_action"]))
    return sorted(_unique(items, lambda x: x.rule_id, path=path), key=lambda x: natural_id_key(x.rule_id))


def load_evidence_manifest(path: Path, dataset_root: Path) -> list[EvidenceManifestEntry]:
    root = dataset_root.resolve()
    items = []
    for n, r in enumerate(_read_csv(path, MANIFEST_COLUMNS), start=2):
        candidate = (root / Path(r["file_path"])).resolve()
        if root not in candidate.parents:
            raise DataValidationError(f"{path}:{n}: evidence path escapes dataset root: {r['file_path']!r}")
        if not candidate.is_file():
            raise DataValidationError(f"{path}:{n}: evidence file is missing: {r['file_path']!r}")
        items.append(EvidenceManifestEntry(r["file_id"], candidate, r["origin"],
                                           parse_timestamp(r["captured_at"], context=f"{path}:{n}:captured_at")))
    return sorted(_unique(items, lambda x: x.file_id, path=path), key=lambda x: natural_id_key(x.file_id))
