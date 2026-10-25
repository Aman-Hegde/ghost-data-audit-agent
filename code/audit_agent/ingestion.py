"""High-level evidence ingestion with artifact-level accounting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evidence_store import EvidenceStore
from .identity import IdentityGraph
from .models import (ArtifactExtraction, EvidenceCoverage, EvidenceManifestEntry,
                     ExtractionIssue, ModelUsage)
from .parsers import parse_structured_evidence
from .parsers.image_parser import ImageExtractionCache, parse_image_evidence
from .parsers.pdf_parser import parse_pdf_evidence

STRUCTURED_SUFFIXES = {".json", ".sql", ".log", ".txt"}
SUPPORTED_SUFFIXES = STRUCTURED_SUFFIXES | {".pdf", ".png"}
DEFAULT_IMAGE_CACHE = Path(__file__).with_name("extraction_cache") / "image_extractions.json"


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    parsed_files: int
    skipped_unstructured_files: int
    observations: int
    store: EvidenceStore


@dataclass(frozen=True, slots=True)
class EvidenceIngestionResult:
    artifacts: tuple[ArtifactExtraction, ...]
    coverage: EvidenceCoverage
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
    return IngestionSummary(parsed, skipped, len(store.observations), store)


def ingest_evidence(entries: list[EvidenceManifestEntry], *, identity_graph: IdentityGraph | None = None,
                    image_cache_path: Path = DEFAULT_IMAGE_CACHE) -> EvidenceIngestionResult:
    """Parse every supported manifest artifact; errors become visible coverage issues."""
    cache = ImageExtractionCache(image_cache_path)
    artifacts: list[ArtifactExtraction] = []
    issues: list[ExtractionIssue] = []
    all_observations = []
    parser_errors = 0
    for entry in sorted(entries, key=lambda item: item.file_id):
        suffix = entry.file_path.suffix.casefold()
        try:
            if suffix in STRUCTURED_SUFFIXES:
                artifact = ArtifactExtraction(entry.file_id, "PARSED",
                                              tuple(parse_structured_evidence(entry)), method="structured")
            elif suffix == ".pdf":
                artifact = parse_pdf_evidence(entry)
            elif suffix == ".png":
                artifact = parse_image_evidence(entry, cache, identity_graph)
            else:
                artifact = ArtifactExtraction(entry.file_id, "UNRESOLVED", (), (
                    ExtractionIssue(entry.file_id, "UNSUPPORTED_EVIDENCE_TYPE",
                                    f"unsupported suffix {suffix!r}", "ERROR"),), method="none")
        except Exception as exc:  # Artifact isolation is deliberate; the report must remain complete.
            parser_errors += 1
            artifact = ArtifactExtraction(entry.file_id, "ERROR", (), (
                ExtractionIssue(entry.file_id, "PARSER_ERROR", str(exc), "ERROR"),), method="error")
        artifacts.append(artifact)
        issues.extend(artifact.issues)
        all_observations.extend(artifact.observations)
    store = EvidenceStore(all_observations)
    unresolved = tuple(item.evidence_id for item in artifacts if item.status != "PARSED")
    metadata = cache.metadata
    usage = (ModelUsage(
        str(metadata.get("provider", "none")), str(metadata.get("model", "none")),
        "development screenshot interpretation cache",
        int(metadata.get("runtime_calls", 0)), int(metadata.get("input_tokens", 0)),
        int(metadata.get("output_tokens", 0)), float(metadata.get("estimated_cost_usd", 0.0)),
    ),)
    coverage = EvidenceCoverage(
        len(entries), sum(item.status == "PARSED" for item in artifacts), len(unresolved), parser_errors,
        len(all_observations), len(store.observations), store.duplicate_count, unresolved, tuple(issues), usage,
    )
    return EvidenceIngestionResult(tuple(artifacts), coverage, store)
