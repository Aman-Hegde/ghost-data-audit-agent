from pathlib import Path
import tempfile
import unittest

from audit_agent.errors import DataValidationError
from audit_agent.loaders import load_requests


class LoaderTests(unittest.TestCase):
    def test_schema_validation_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("case_id,email\ncase_2,a@example.test\n", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "expected columns"):
                load_requests(path)

    def test_requests_are_naturally_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requests.csv"
            header = "case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n"
            rows = [
                "case_10,a@example.test,2026-01-01T00:00:00Z,COMPLETE,2026-01-02T00:00:00Z,2026-01-03T00:00:00Z,delete my account\n",
                "case_2,b@example.test,2026-01-01T00:00:00Z,NOT_STARTED,2026-01-02T00:00:00Z,2026-01-03T00:00:00Z,delete my account\n",
            ]
            path.write_text(header + "".join(rows), encoding="utf-8")
            self.assertEqual([r.case_id for r in load_requests(path)], ["case_2", "case_10"])


if __name__ == "__main__":
    unittest.main()
