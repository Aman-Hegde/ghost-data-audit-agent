from datetime import datetime, timezone
from pathlib import Path
import random
import unittest

from audit_agent.models import (AuditStep, CasePrediction, ComplianceStatus, Observation, PolicyRule,
                                Provenance, Resource)
from audit_agent.ordering import order_steps
from audit_agent.planning import plan_steps
from audit_agent.policy import PolicyEngine
from audit_agent.serialization import output_rows

UTC = timezone.utc
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def rules():
    categories = [
        ("USER_PROFILE", "DELETE"), ("SECONDARY_IDENTIFIER", "DELETE"),
        ("SEARCH_INDEX_ENTRY", "DELETE"), ("CACHE_ENTRY", "DELETE"),
        ("SUPPORT_MESSAGE", "REDACT"), ("SUPPORT_ATTACHMENT", "DELETE"),
        ("ANALYTICS_PROFILE", "ANONYMIZE"), ("PRODUCT_TELEMETRY", "ANONYMIZE"),
        ("USER_EXPORT", "DELETE"), ("MARKETING_PROFILE", "DELETE"),
        ("EMAIL_DELIVERY_LOG", "REDACT"), ("SECURITY_AUDIT_LOG", "RETAIN"),
        ("LEGAL_HOLD_RECORD", "RETAIN"), ("BACKUP_ARCHIVE", "RETAIN"),
        ("ACCOUNT_TOMBSTONE", "REDACT"),
    ]
    return [PolicyRule(f"rule_{index:02}", category, "Always", action)
            for index, (category, action) in enumerate(categories, 1)]


def observation(resource_id, category, state, attrs=None, system="test_system"):
    return Observation(Resource(resource_id, system, system, category), state, NOW, NOW, (), attrs or {},
                       Provenance("evidence_1", Path("evidence.json"), "test", "row=1", "test"))


class PolicyTests(unittest.TestCase):
    def test_all_rule_actions_compile_to_terminal_states(self):
        engine = PolicyEngine(rules())
        expected = {"DELETE": "ABSENT", "REDACT": "REDACTED",
                    "ANONYMIZE": "ANONYMIZED", "RETAIN": "PRESENT"}
        for rule in rules():
            terminal = engine.decision_for_category(rule.data_category).terminal_state
            self.assertEqual(terminal, "BLOCKED" if rule.data_category == "BACKUP_ARCHIVE"
                             else expected[rule.required_action])

    def test_tombstone_requires_stable_id_and_no_direct_pii(self):
        engine = PolicyEngine(rules())
        good = engine.assess([observation("tombstone_1", "ACCOUNT_TOMBSTONE", "PRESENT",
                                          {"subject_reference": "user_1", "email": None})], NOW)
        bad = engine.assess([observation("tombstone_2", "ACCOUNT_TOMBSTONE", "PRESENT",
                                         {"subject_reference": "user_1", "email": "person@example.test"})], NOW)
        self.assertEqual(good.compliance, ComplianceStatus.COMPLIANT)
        self.assertEqual(bad.compliance, ComplianceStatus.VIOLATION)

    def test_operation_success_is_not_deletion_state_proof(self):
        engine = PolicyEngine(rules())
        present = observation("account_1", "USER_PROFILE", "PRESENT")
        self.assertEqual(engine.assess([present], NOW).compliance, ComplianceStatus.VIOLATION)


class PlanningTests(unittest.TestCase):
    def test_contract_order_is_stable_under_input_shuffle(self):
        raw = [
            AuditStep(0, "VERIFICATION", "z", "r2", "VERIFY_RECORD_PRESENT", "PRESENT", ""),
            AuditStep(0, "FINDING", "a", "r1", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", "e1"),
            AuditStep(0, "REMEDIATION", "a", "r1", "DISABLE_DATA_FLOW", "DISABLED", ""),
            AuditStep(0, "FINDING", "z", "r2", "REPORT_EXPOSED_PII", "PRESENT", "e2"),
        ]
        expected = order_steps(raw)
        random.Random(42).shuffle(raw)
        self.assertEqual(order_steps(raw), expected)
        self.assertEqual([item.step_no for item in expected], [1, 2, 3, 4])

    def test_output_rows_have_exact_contract_and_natural_case_order(self):
        predictions = [CasePrediction("case_10", "NOT_APPLICABLE", ()),
                       CasePrediction("case_2", "NOT_APPLICABLE", ())]
        rows = output_rows(predictions, ["case_2", "case_10"])
        self.assertEqual([row["case_id"] for row in rows], ["case_2", "case_10"])
        self.assertEqual(tuple(rows[0]), ("case_id", "deletion_status", "steps_json"))
        self.assertEqual(rows[0]["steps_json"], "[]")


if __name__ == "__main__":
    unittest.main()
