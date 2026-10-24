"""Safe in-memory ingestion of SQLite-compatible SQL snapshot exports."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping

from ..errors import EvidenceParseError
from ..models import EvidenceManifestEntry, Observation, Provenance, Resource, TemporalSemantics
from .common import category_for, extract_identifiers, immutable_attributes, infer_state, observation_time, system_for

UNSAFE_SQL = re.compile(r"\b(ATTACH|DETACH|VACUUM|LOAD_EXTENSION|WRITABLE_SCHEMA)\b", re.I)


def parse_sql_evidence(entry: EvidenceManifestEntry) -> list[Observation]:
    try:
        script = entry.file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise EvidenceParseError(f"{entry.file_id}: cannot read SQL evidence: {exc}") from exc
    if UNSAFE_SQL.search(script):
        raise EvidenceParseError(f"{entry.file_id}: SQL evidence contains a disallowed statement")
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    observations: list[Observation] = []
    try:
        connection.executescript(script)
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for table in tables:
            quoted = table.replace('"', '""')
            for row_index, sql_row in enumerate(connection.execute(f'SELECT * FROM "{quoted}"')):
                record = dict(sql_row)
                nested = record.get("record_json")
                if isinstance(nested, str):
                    try:
                        decoded = json.loads(nested)
                        if isinstance(decoded, Mapping):
                            record = {**record, **decoded, "record_json": nested}
                    except json.JSONDecodeError:
                        record["record_json_invalid"] = True
                resource_id = record.get("resource_id")
                if not isinstance(resource_id, str) or not resource_id:
                    resource_id = f"scope:{table}:{row_index}"
                collection = str(record.get("collection_name") or table)
                logical = system_for(collection, record, table)
                category = category_for(collection, record)
                observed = observation_time(record, fallback=entry.captured_at,
                                            context=f"{entry.file_id}:{table}:{row_index}")
                observations.append(Observation(
                    Resource(resource_id, logical, table, category), infer_state(record, category),
                    observed, entry.captured_at, extract_identifiers(record), immutable_attributes(record),
                    Provenance(entry.file_id, entry.file_path, entry.origin, f"table={table};row={row_index}", "sql-v1"),
                    TemporalSemantics.POINT_IN_TIME,
                ))
    except sqlite3.Error as exc:
        raise EvidenceParseError(f"{entry.file_id}: SQLite rejected snapshot: {exc}") from exc
    finally:
        connection.close()
    return sorted(observations, key=lambda item: (
        item.observed_at, item.resource.logical_system, item.resource.physical_system,
        item.resource.resource_id, item.provenance.locator,
    ))
