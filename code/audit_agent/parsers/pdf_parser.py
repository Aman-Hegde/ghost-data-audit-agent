"""Embedded-text-first PDF evidence extraction with page provenance."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from pypdf import PdfReader

from ..errors import EvidenceParseError
from ..models import (
    ArtifactExtraction, EvidenceManifestEntry, EvidenceNature, ExtractionIssue,
    Observation, Provenance, Resource, TemporalSemantics,
)
from .common import extract_identifiers, immutable_attributes

RESOURCE_RE = re.compile(
    r"\b(?:account|analytics|audit_record|backup|cache|data_flow|email_delivery|export|marketing|search|support|tombstone)_[A-Za-z0-9-]+\b|"
    r"\b(?:ORD|NST|CS|FIN)-[A-Za-z0-9-]+\b",
    re.I,
)
ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
HUMAN_RE = re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d{2})(?:\s+(\d{1,2})[: ](\d{2}))?\s*(?:UTC)?\b", re.I)


def _timestamps(text: str) -> list[str]:
    values = list(ISO_RE.findall(text))
    months = {name.casefold(): index for index, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
    for day, month, year, hour, minute in HUMAN_RE.findall(text):
        parsed = datetime(int(year), months[month.casefold()], int(day), int(hour or 0), int(minute or 0), tzinfo=timezone.utc)
        values.append(parsed.isoformat().replace("+00:00", "Z"))
    return sorted(set(values))


def _system_category(entry: EvidenceManifestEntry) -> tuple[str, str]:
    name = entry.file_path.name.casefold()
    origin = entry.origin.casefold()
    if "support" in origin or "attachment" in name:
        return "support_platform", "SUPPORT_ATTACHMENT"
    if "security" in origin or "security" in name:
        return "security_service", "SECURITY_AUDIT_LOG"
    if "legal" in origin or "legal" in name:
        return "legal_service", "LEGAL_HOLD_RECORD"
    if "account" in origin or "account" in name:
        return "account_history_service", "BUSINESS_RECORD"
    return entry.origin, "DOCUMENT_RECORD"


def parse_pdf_evidence(entry: EvidenceManifestEntry) -> ArtifactExtraction:
    digest = hashlib.sha256(entry.file_path.read_bytes()).hexdigest()
    try:
        reader = PdfReader(entry.file_path)
    except Exception as exc:
        raise EvidenceParseError(f"{entry.file_id}: cannot open PDF: {exc}") from exc
    observations, issues = [], []
    system, category = _system_category(entry)
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            issues.append(ExtractionIssue(entry.file_id, "PDF_PAGE_EXTRACTION_FAILED",
                                          f"page {page_index}: {exc}", "ERROR"))
            continue
        if not text.strip():
            issues.append(ExtractionIssue(entry.file_id, "PDF_PAGE_REQUIRES_OCR",
                                          f"page {page_index} has no embedded text", "ERROR"))
            continue
        resource_ids = sorted(set(match.group(0) for match in RESOURCE_RE.finditer(text)
                                  if not match.group(0).casefold().startswith("user_")))
        if category == "SUPPORT_ATTACHMENT":
            resource_ids = [value for value in resource_ids if value.casefold().startswith("support_")]
        if not resource_ids:
            resource_ids = [f"document:{entry.file_path.stem}:page:{page_index}"]
        for resource_id in resource_ids:
            matching_lines = [line.strip() for line in text.splitlines() if resource_id.casefold() in line.casefold()]
            excerpt = text if category == "SUPPORT_ATTACHMENT" else ("\n".join(matching_lines) if matching_lines else text)
            record = {
                "document_text": excerpt,
                "mentioned_timestamps": _timestamps(excerpt),
                "page": page_index,
            }
            identifiers = extract_identifiers(record)
            attachment_state = category == "SUPPORT_ATTACHMENT"
            observations.append(Observation(
                Resource(resource_id, system, f"pdf:{entry.file_path.name}:page:{page_index}", category),
                "PRESENT" if attachment_state else "DOCUMENTED", entry.captured_at, entry.captured_at, identifiers,
                immutable_attributes(record),
                Provenance(entry.file_id, entry.file_path, entry.origin, f"page={page_index}", "pypdf-v1"),
                TemporalSemantics.POINT_IN_TIME if attachment_state else TemporalSemantics.HISTORICAL_RECORD,
                EvidenceNature.STATE_OBSERVATION if attachment_state else EvidenceNature.HISTORICAL_FACT,
            ))
    status = "UNRESOLVED" if any(issue.severity == "ERROR" for issue in issues) else "PARSED"
    return ArtifactExtraction(entry.file_id, status, tuple(observations), tuple(issues), digest, "embedded_text:pypdf")
