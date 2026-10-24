"""High-level structured-evidence ingestion orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence_store import EvidenceStore
from .models import EvidenceManifestEntry
from .parsers import parse_structured_evidence

STRUCTURED_SUFFIXES = {".json", ".sql", ".log", ".txt"}


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    parsed_files: int
    skipped_unstructured_files: int
    observations: int
    store: EvidenceStore


def ingest_structured_evidence(entries: list[EvidenceManifestEntry]) -> IngestionSummary:
    observations = []
    parsed = skipped = 0
    for entry in sorted(entries, key=lambda item: item.file_id):
        if entry.file_path.suffix.casefold() not in STRUCTURED_SUFFIXES:
            skipped += 1
            continue
        observations.extend(parse_structured_evidence(entry))
        parsed += 1
    store = EvidenceStore(observations)
    return IngestionSummary(parsed, skipped, len(observations), store)
