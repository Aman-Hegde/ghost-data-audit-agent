from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from audit_agent.models import EvidenceManifestEntry, EvidenceNature
from audit_agent.parsers import parse_structured_evidence

UTC = timezone.utc


class Phase3ParserRegressionTests(unittest.TestCase):
    def test_pipe_handover_is_a_state_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handover.txt"
            path.write_text("- 2026-01-01T00:00:00Z | analytics_platform | analytics_1 | ANALYTICS_PROFILE | IDENTIFIABLE | person@example.test\n",
                            encoding="utf-8")
            entry = EvidenceManifestEntry("evidence_1", path, "handover", NOW := datetime(2026, 1, 1, tzinfo=UTC))
            item = parse_structured_evidence(entry)[0]
            self.assertEqual(item.nature, EvidenceNature.STATE_OBSERVATION)
            self.assertEqual(item.state, "IDENTIFIABLE")

    def test_zero_row_log_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "read.log"
            path.write_text("2026-01-01T00:00:00Z service=account_service event=profile_lookup_completed resource_id=account_1 rows=0 http_status=404 lookup_key=person@example.test\n",
                            encoding="utf-8")
            entry = EvidenceManifestEntry("evidence_1", path, "readback", datetime(2026, 1, 1, tzinfo=UTC))
            self.assertEqual(parse_structured_evidence(entry)[0].state, "ABSENT")


if __name__ == "__main__":
    unittest.main()
