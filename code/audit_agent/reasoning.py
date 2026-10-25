"""Case-level deletion audit reasoning."""

from __future__ import annotations

from .intent import IntentClassifier
from .linking import ResourceLinker
from .models import (CasePrediction, ComplianceStatus, DeletionRequest, IntentKind,
                     ResourceAssessment)
from .planning import plan_steps
from .policy import PolicyEngine


class DeletionAuditor:
    def __init__(self, classifier: IntentClassifier, linker: ResourceLinker, policies: PolicyEngine):
        self.classifier = classifier
        self.linker = linker
        self.policies = policies

    @staticmethod
    def _applicable(item: ResourceAssessment) -> bool:
        if item.policy.data_category != "LEGAL_HOLD_RECORD":
            return True
        text = " ".join(str(obs.attributes).casefold() for obs in item.observations)
        return "legal hold" in text and any(token in text for token in ("active", "hold_active", "'active': true"))

    def predict(self, request: DeletionRequest) -> CasePrediction:
        intent = self.classifier.classify(request.request_text)
        if intent.kind == IntentKind.NON_DELETION:
            return CasePrediction(request.case_id, "NOT_APPLICABLE", ())
        if intent.kind == IntentKind.AMBIGUOUS:
            return CasePrediction(request.case_id, "INCOMPLETE", (),
                                  ("deletion intent requires adjudication",))
        discovery = self.linker.discover(request)
        assessments = []
        unresolved = list(discovery.unresolved_reasons)
        for resource_id, observations in sorted(discovery.by_resource.items()):
            try:
                item = self.policies.assess(observations, request.audit_at)
            except Exception as exc:
                unresolved.append(f"{resource_id}: {exc}")
                continue
            if self._applicable(item):
                assessments.append(item)
        assessments_tuple = tuple(assessments)
        complete = bool(assessments_tuple) and not unresolved and all(
            item.compliance == ComplianceStatus.COMPLIANT for item in assessments_tuple)
        status = "COMPLETE" if complete else "INCOMPLETE"
        return CasePrediction(request.case_id, status, plan_steps(assessments_tuple, complete=complete),
                              tuple(unresolved))
