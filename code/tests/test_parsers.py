from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from audit_agent.evidence_store import EvidenceStore
from audit_agent.models import EvidenceManifestEntry
from audit_agent.parsers import parse_structured_evidence

UTC = timezone.utc


class ParserTests(unittest.TestCase):
    def _entry(self, path, file_id="evidence_test"):
        return EvidenceManifestEntry(file_id, path, "synthetic", datetime(2026, 1, 2, tzinfo=UTC))

    def test_json_preserves_nested_identifiers_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            data = {"exported_at": "2026-01-02T00:00:00Z", "source": "test", "snapshots": [{
                "captured_at": "2026-01-02T00:00:00Z", "data_store": "search_service",
                "collection": "customer_search_documents", "records": [{
                    "resource_id": "search_1", "document": {"email": "Old@Example.test", "subject_reference": "user_a"}
                }]
            }]}
            path.write_text(json.dumps(data), encoding="utf-8")
            items = parse_structured_evidence(self._entry(path))
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].provenance.evidence_id, "evidence_test")
            self.assertEqual({i.normalized_value for i in items[0].identifiers}, {"old@example.test", "user_a"})

    def test_sql_replica_rows_remain_physically_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.sql"
            path.write_text("""
                CREATE TABLE primary_copy(resource_id TEXT, origin_system TEXT, collection_name TEXT, record_json TEXT, updated_at TEXT);
                CREATE TABLE replica_copy(resource_id TEXT, origin_system TEXT, collection_name TEXT, record_json TEXT, updated_at TEXT);
                INSERT INTO primary_copy VALUES ('account_1','account_service','customer_profiles','{\"email\":\"a@example.test\"}','2026-01-01T00:00:00Z');
                INSERT INTO replica_copy VALUES ('account_1','account_service','customer_profiles','{\"email\":\"a@example.test\"}','2026-01-01T00:00:00Z');
            """, encoding="utf-8")
            items = parse_structured_evidence(self._entry(path))
            self.assertEqual({i.resource.physical_system for i in items}, {"primary_copy", "replica_copy"})
            self.assertEqual(len(EvidenceStore(items).by_email("A@example.test")), 2)

    def test_log_extracts_resource_and_email(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readback.log"
            path.write_text('2026-01-01T10:00:00Z level=INFO service=account_service event=lookup resource_id=account_7 result=FOUND email="person@example.test"\n', encoding="utf-8")
            items = parse_structured_evidence(self._entry(path))
            self.assertEqual(items[0].resource.resource_id, "account_7")
            self.assertEqual(items[0].state, "PRESENT")
            self.assertEqual(len(EvidenceStore(items).by_email("person@example.test")), 1)


if __name__ == "__main__":
    unittest.main()
