from pathlib import Path
import tempfile
import unittest

from audit_agent.evaluation import compare_outputs


class EvaluationTests(unittest.TestCase):
    def test_exact_and_field_metrics(self):
        header = "case_id,deletion_status,steps_json\n"
        exact = 'case_1,COMPLETE,"[{""step_no"":1,""phase"":""VERIFICATION"",""system_id"":""a"",""resource_id"":""r"",""operation"":""VERIFY_RECORD_ABSENT"",""state"":""ABSENT"",""evidence_id"":""e1""}]"\n'
        changed = 'case_1,INCOMPLETE,"[{""step_no"":1,""phase"":""VERIFICATION"",""system_id"":""a"",""resource_id"":""r"",""operation"":""VERIFY_RECORD_ABSENT"",""state"":""PRESENT"",""evidence_id"":""e1""}]"\n'
        with tempfile.TemporaryDirectory() as directory:
            canonical = Path(directory) / "canonical.csv"
            prediction = Path(directory) / "prediction.csv"
            canonical.write_text(header + exact, encoding="utf-8")
            prediction.write_text(header + exact, encoding="utf-8")
            metrics = compare_outputs(prediction, canonical)
            self.assertEqual(metrics.status_accuracy, 1.0)
            self.assertEqual(metrics.sequence_accuracy, 1.0)
            self.assertEqual(metrics.field_accuracy, 1.0)
            prediction.write_text(header + changed, encoding="utf-8")
            metrics = compare_outputs(prediction, canonical)
            self.assertEqual(metrics.status_accuracy, 0.0)
            self.assertEqual(metrics.step_f1, 0.0)
            self.assertEqual(metrics.field_correct, 6)
            self.assertEqual(metrics.field_total, 7)


if __name__ == "__main__":
    unittest.main()
