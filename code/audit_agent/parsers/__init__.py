"""Structured evidence parser dispatch."""

from __future__ import annotations

from ..errors import EvidenceParseError
from ..models import EvidenceManifestEntry, Observation
from .json_parser import parse_json_evidence
from .log_parser import parse_log_evidence
from .sql_parser import parse_sql_evidence


def parse_structured_evidence(entry: EvidenceManifestEntry) -> list[Observation]:
    suffix = entry.file_path.suffix.casefold()
    if suffix == ".json":
        return parse_json_evidence(entry)
    if suffix == ".sql":
        return parse_sql_evidence(entry)
    if suffix in {".log", ".txt"}:
        return parse_log_evidence(entry)
    raise EvidenceParseError(f"{entry.file_id}: unsupported structured evidence type {suffix!r}")


__all__ = ["parse_structured_evidence"]
