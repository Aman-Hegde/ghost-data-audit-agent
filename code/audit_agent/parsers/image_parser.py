"""Content-hash cached extraction for screenshot evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from ..errors import EvidenceParseError
from ..identity import IdentityGraph
from ..models import (
    ArtifactExtraction, EvidenceManifestEntry, EvidenceNature, ExtractionIssue,
    IdentifierKind, Observation, Provenance, Resource, TemporalSemantics,
)
from ..normalization import parse_timestamp
from .common import extract_identifiers, immutable_attributes


class ImageExtractionCache:
    def __init__(self, path: Path):
        self.path = path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceParseError(f"cannot load image extraction cache {path}: {exc}") from exc
        if payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), dict):
            raise EvidenceParseError(f"invalid image extraction cache schema: {path}")
        self.metadata = payload.get("metadata", {})
        self.entries: Mapping[str, Any] = payload["entries"]

    def get(self, digest: str) -> Mapping[str, Any] | None:
        value = self.entries.get(digest.casefold())
        return value if isinstance(value, Mapping) else None


def _identity_issues(entry: EvidenceManifestEntry, observation: Observation,
                     graph: IdentityGraph | None) -> list[ExtractionIssue]:
    if graph is None:
        return []
    resolved_users, unknown = set(), []
    seen = set()
    for identifier in observation.identifiers:
        if identifier.kind not in {IdentifierKind.USER_ID, IdentifierKind.EMAIL}:
            continue
        key = (identifier.kind, identifier.normalized_value)
        if key in seen:
            continue
        seen.add(key)
        resolution = graph.resolve(identifier.kind, identifier.raw_value, at=entry.captured_at)
        if resolution.resolved_user_id:
            resolved_users.add(resolution.resolved_user_id)
        elif not resolution.ambiguous:
            unknown.append(identifier.raw_value)
    issues = []
    if len(resolved_users) > 1:
        issues.append(ExtractionIssue(entry.file_id, "IDENTITY_CONFLICT",
                                      f"{observation.resource.resource_id} links distinct users {sorted(resolved_users)}",
                                      "ERROR"))
    if unknown:
        issues.append(ExtractionIssue(entry.file_id, "IDENTIFIER_NOT_IN_IDENTITY_GRAPH",
                                      f"unmatched visible identifiers for {observation.resource.resource_id}: {sorted(unknown)}"))
    return issues


def parse_image_evidence(entry: EvidenceManifestEntry, cache: ImageExtractionCache,
                         identity_graph: IdentityGraph | None = None) -> ArtifactExtraction:
    raw = entry.file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        with Image.open(entry.file_path) as image:
            image.verify()
            image_format = image.format
    except Exception as exc:
        raise EvidenceParseError(f"{entry.file_id}: invalid image: {exc}") from exc
    cached = cache.get(digest)
    if cached is None:
        issue = ExtractionIssue(entry.file_id, "IMAGE_EXTRACTION_UNAVAILABLE",
                                "no content-hash cache entry and no runtime vision provider configured", "ERROR")
        return ArtifactExtraction(entry.file_id, "UNRESOLVED", (), (issue,), digest, "none")
    if image_format != "PNG":
        issue = ExtractionIssue(entry.file_id, "IMAGE_FORMAT_MISMATCH", f"expected PNG, found {image_format}", "ERROR")
        return ArtifactExtraction(entry.file_id, "UNRESOLVED", (), (issue,), digest, "cache")
    observations, issues = [], []
    for index, record in enumerate(cached.get("observations", [])):
        if not isinstance(record, Mapping):
            issues.append(ExtractionIssue(entry.file_id, "INVALID_CACHED_OBSERVATION",
                                          f"cache observation {index} is not an object", "ERROR"))
            continue
        required = {"resource_id", "logical_system", "category", "state"}
        if not required.issubset(record):
            issues.append(ExtractionIssue(entry.file_id, "INVALID_CACHED_OBSERVATION",
                                          f"cache observation {index} lacks {sorted(required - set(record))}", "ERROR"))
            continue
        observed_at = parse_timestamp(record.get("observed_at", entry.captured_at.isoformat()),
                                      context=f"{entry.file_id}:cache[{index}]:observed_at")
        attributes = dict(record.get("attributes", {}))
        for key in ("user_id", "email", "phone", "email_hash", "name"):
            if key in record:
                attributes[key] = record[key]
        observation = Observation(
            Resource(str(record["resource_id"]), str(record["logical_system"]),
                     f"screenshot:{entry.file_path.name}", str(record["category"])),
            str(record["state"]), observed_at, entry.captured_at, extract_identifiers(attributes),
            immutable_attributes(attributes),
            Provenance(entry.file_id, entry.file_path, entry.origin,
                       str(record.get("locator", f"cache.observations[{index}]")), "image-cache-v1"),
            TemporalSemantics.POINT_IN_TIME, EvidenceNature.STATE_OBSERVATION,
        )
        observations.append(observation)
        issues.extend(_identity_issues(entry, observation, identity_graph))
    status = "UNRESOLVED" if not observations or any(issue.severity == "ERROR" for issue in issues) else "PARSED"
    method = str(cached.get("method", "content_hash_cache"))
    return ArtifactExtraction(entry.file_id, status, tuple(observations), tuple(issues), digest, method)
