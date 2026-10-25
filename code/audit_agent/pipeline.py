"""Production assembly; canonical sample answers are intentionally absent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import DataValidationError
from .identity import IdentityGraph
from .ingestion import EvidenceIngestionResult, ingest_evidence
from .intent import IntentClassifier, MultilingualRuleAdjudicator
from .linking import ResourceLinker
from .loaders import (load_activity, load_evidence_manifest, load_identities,
                      load_identity_events, load_policy_rules, load_requests)
from .models import CasePrediction, DeletionRequest
from .policy import PolicyEngine
from .provenance import ProvenanceValidator
from .reasoning import DeletionAuditor
from .validation import validate_predictions_at_requests


@dataclass(frozen=True, slots=True)
class PipelineResult:
    requests: tuple[DeletionRequest, ...]
    predictions: tuple[CasePrediction, ...]
    ingestion: EvidenceIngestionResult


def run_pipeline(dataset: Path, request_file: str) -> PipelineResult:
    requests = load_requests(dataset / request_file)
    identities = load_identities(dataset / "user_identities.csv")
    identity_events = load_identity_events(dataset / "user_audit_log.csv")
    graph = IdentityGraph(identities, identity_events)
    activities = load_activity(dataset / "system_activity.csv")
    manifest = load_evidence_manifest(dataset / "evidence_files.csv", dataset)
    ingestion = ingest_evidence(manifest, identity_graph=graph)
    linker = ResourceLinker(graph, ingestion.store, activities, manifest)
    auditor = DeletionAuditor(IntentClassifier(MultilingualRuleAdjudicator()), linker,
                              PolicyEngine(load_policy_rules(dataset / "deletion_rules.csv")))
    predictions = [auditor.predict(request) for request in requests]
    validator = ProvenanceValidator(manifest, activities, identity_events, ingestion.store)
    relationship_validation = validator.validate_relationships(linker.relationship_graph.relationships)
    if not relationship_validation.valid:
        codes = sorted({item.code for item in relationship_validation.issues})
        raise DataValidationError(f"invalid relationship graph provenance: {codes}")
    validate_predictions_at_requests(predictions, {item.case_id: item for item in requests}, validator)
    return PipelineResult(tuple(requests), tuple(predictions), ingestion)
