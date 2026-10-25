"""Prediction contract validation independent of CSV writing."""

from __future__ import annotations

from .errors import DataValidationError
from .models import CasePrediction, EvidenceCitation
from .ordering import order_steps
from .provenance import ProvenanceValidator


def validate_predictions_at_requests(predictions: list[CasePrediction], requests_by_id: dict,
                                     provenance: ProvenanceValidator) -> None:
    """Validate citations with request-specific audit cutoffs."""
    validate_predictions_structure(predictions, list(requests_by_id))
    for prediction in predictions:
        request = requests_by_id[prediction.case_id]
        for step in prediction.steps:
            if not step.evidence_id:
                continue
            result = provenance.validate_citation(EvidenceCitation(
                step.evidence_id, step.resource_id, request.audit_at))
            if not result.valid:
                codes = ",".join(item.code for item in result.issues)
                raise DataValidationError(f"{prediction.case_id}: invalid citation {step.evidence_id}: {codes}")


def validate_predictions_structure(predictions: list[CasePrediction], expected_case_ids: list[str]) -> None:
    """Structural subset used before a provenance validator is available."""
    if len(predictions) != len(expected_case_ids) or {p.case_id for p in predictions} != set(expected_case_ids):
        raise DataValidationError("prediction row count or case IDs do not match requests")
    if len({p.case_id for p in predictions}) != len(predictions):
        raise DataValidationError("duplicate prediction case ID")
    for prediction in predictions:
        if prediction.deletion_status not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}:
            raise DataValidationError(f"{prediction.case_id}: invalid status")
        if prediction.deletion_status == "NOT_APPLICABLE" and prediction.steps:
            raise DataValidationError(f"{prediction.case_id}: NOT_APPLICABLE must use []")
        if tuple(prediction.steps) != order_steps(list(prediction.steps)):
            raise DataValidationError(f"{prediction.case_id}: noncanonical steps")
        for step in prediction.steps:
            future = prediction.deletion_status == "INCOMPLETE" and step.phase in {"REMEDIATION", "VERIFICATION"}
            if future and step.evidence_id:
                raise DataValidationError(f"{prediction.case_id}: future step cites evidence")
            if (step.phase == "FINDING" or prediction.deletion_status == "COMPLETE") and not step.evidence_id:
                raise DataValidationError(f"{prediction.case_id}: evidence-backed step lacks evidence")
