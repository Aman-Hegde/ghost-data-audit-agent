import unittest

from audit_agent.intent import IntentClassifier, MultilingualRuleAdjudicator
from audit_agent.models import IntentKind


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.classifier = IntentClassifier(MultilingualRuleAdjudicator())

    def test_clear_deletion(self):
        self.assertEqual(self.classifier.classify("Please permanently delete my account.").kind, IntentKind.DELETION)

    def test_clear_non_deletion_negation_wins(self):
        decision = self.classifier.classify("Please send a copy of my data. Do not delete my account.")
        self.assertEqual(decision.kind, IntentKind.NON_DELETION)

    def test_ambiguous_request_stays_ambiguous(self):
        self.assertEqual(self.classifier.classify("Please take care of my privacy request.").kind, IntentKind.AMBIGUOUS)

    def test_multilingual_adjudication(self):
        decision = self.classifier.classify("Solicito eliminar permanentemente mi cuenta y mis datos.")
        self.assertEqual(decision.kind, IntentKind.DELETION)
        self.assertEqual(decision.mechanism, "multilingual_rule_adjudicator")


if __name__ == "__main__":
    unittest.main()
