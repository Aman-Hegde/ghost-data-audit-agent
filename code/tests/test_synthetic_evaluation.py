import unittest

from evaluation.synthetic_cases import evaluate, predictions


class SyntheticEvaluationTests(unittest.TestCase):
    def test_complete_incomplete_and_non_deletion_cases(self):
        passed, failures = evaluate()
        self.assertTrue(passed, failures)
        self.assertEqual(
            [item.deletion_status for item in predictions()],
            ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"],
        )


if __name__ == "__main__":
    unittest.main()
