from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from audit_agent.evidence_store import EvidenceStore
from audit_agent.activity import activity_observations
from audit_agent.identity import IdentityGraph
from audit_agent.models import (
    ActivityEvent, EvidenceCitation, EvidenceManifestEntry, EvidenceNature, IdentitySnapshot,
    Observation, OperationStatus, Provenance, Resource, TemporalSemantics, TimelineStatus,
)
from audit_agent.parsers.image_parser import ImageExtractionCache, parse_image_evidence
from audit_agent.provenance import ProvenanceValidator
from audit_agent.temporal import assess_resource_timeline

UTC = timezone.utc
BASE = datetime(2026, 1, 10, tzinfo=UTC)


def obs(state, when, physical, *, nature=EvidenceNature.STATE_OBSERVATION,
        operation=OperationStatus.NOT_APPLICABLE, attrs=None, captured=None, semantics=TemporalSemantics.POINT_IN_TIME):
    return Observation(Resource("record_1", "account_service", physical, "USER_PROFILE"), state,
                       when, captured or when, (), attrs or {},
                       Provenance("evidence_1", Path("evidence.log"), "test", "line=1", "test"),
                       semantics, nature, "trace-1", operation)


class TimelineScenarioTests(unittest.TestCase):
    def test_primary_deleted_but_read_replica_present(self):
        result = assess_resource_timeline("record_1", [
            obs("ABSENT", BASE, "primary"), obs("PRESENT", BASE, "read_replica")], BASE)
        self.assertEqual(result.status, TimelineStatus.CONTRADICTORY)
        self.assertIsNone(result.best_state)

    def test_successful_delete_followed_by_sync_recreation(self):
        delete = obs("SUCCESS", BASE - timedelta(hours=3), "event_log",
                     nature=EvidenceNature.OPERATION_EVENT, operation=OperationStatus.SUCCEEDED,
                     attrs={"event": "delete_completed"}, semantics=TemporalSemantics.EVENT_OCCURRED)
        sync = obs("SUCCESS", BASE - timedelta(hours=2), "event_log",
                   nature=EvidenceNature.OPERATION_EVENT, operation=OperationStatus.SUCCEEDED,
                   attrs={"event": "sync_recreated"}, semantics=TemporalSemantics.EVENT_OCCURRED)
        present = obs("PRESENT", BASE - timedelta(hours=1), "replica")
        result = assess_resource_timeline("record_1", [delete, sync, present], BASE)
        self.assertTrue(result.recreation_detected)
        self.assertEqual(result.best_state, "PRESENT")

    def test_retained_restorable_backup_is_not_treated_as_absent(self):
        backup = Observation(Resource("record_1", "backup_service", "backup_catalog", "BACKUP_ARCHIVE"),
                             "ACTIVE", BASE, BASE, (), {"restore_allowed": True},
                             Provenance("evidence_1", Path("backup.json"), "test", "$.records[0]", "test"))
        result = assess_resource_timeline("record_1", [backup], BASE)
        self.assertEqual((result.status, result.best_state), (TimelineStatus.RESOLVED, "ACTIVE"))

    def test_later_document_can_support_event_but_not_current_state(self):
        historical = obs("DELETED", BASE - timedelta(days=1), "document",
                         nature=EvidenceNature.HISTORICAL_FACT,
                         captured=BASE + timedelta(days=1), semantics=TemporalSemantics.HISTORICAL_RECORD)
        result = assess_resource_timeline("record_1", [historical], BASE, allow_retrospective=True)
        self.assertEqual(result.status, TimelineStatus.UNRESOLVED)
        self.assertFalse(result.state_observations)

    def test_same_timestamp_contradiction_is_preserved(self):
        result = assess_resource_timeline("record_1", [
            obs("ABSENT", BASE, "primary"), obs("PRESENT", BASE, "primary")], BASE)
        self.assertEqual(result.status, TimelineStatus.CONTRADICTORY)
        self.assertEqual(len(result.conflicts), 1)


class ImageConflictTests(unittest.TestCase):
    def test_screenshot_conflicting_identifiers_is_unresolved(self):
        snapshots = [
            IdentitySnapshot("user_a", "A", "a@example.test", "1", "a" * 64, BASE),
            IdentitySnapshot("user_b", "B", "b@example.test", "2", "b" * 64, BASE),
        ]
        graph = IdentityGraph(snapshots, [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); image_path = root / "screen.png"
            Image.new("RGB", (2, 2), "white").save(image_path)
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            cache_path = root / "cache.json"
            cache_path.write_text(json.dumps({"schema_version": 1, "entries": {digest: {
                "observations": [{"resource_id": "account_1", "logical_system": "account_service",
                                  "category": "USER_PROFILE", "state": "PRESENT",
                                  "user_id": "user_a", "email": "b@example.test"}]
            }}}), encoding="utf-8")
            entry = EvidenceManifestEntry("evidence_1", image_path, "test", BASE)
            result = parse_image_evidence(entry, ImageExtractionCache(cache_path), graph)
            self.assertEqual(result.status, "UNRESOLVED")
            self.assertIn("IDENTITY_CONFLICT", {item.code for item in result.issues})


class ProvenanceTests(unittest.TestCase):
    def test_dedup_and_hallucinated_citation_validation(self):
        item = obs("PRESENT", BASE, "primary")
        store = EvidenceStore([item, item])
        self.assertEqual((len(store.observations), store.duplicate_count), (1, 1))
        manifest = [EvidenceManifestEntry("evidence_1", Path("evidence.log"), "test", BASE)]
        validator = ProvenanceValidator(manifest, [], [], store)
        self.assertTrue(validator.validate_index().valid)
        invalid = validator.validate_citation(EvidenceCitation("fabricated", "record_1", BASE))
        self.assertFalse(invalid.valid)

    def test_reported_activity_remains_operation_not_state_proof(self):
        event = ActivityEvent("activity_1", BASE, "DELETE", "orchestrator", "account_service",
                              "record_1", "SUCCESS", "delete call returned successfully")
        item = activity_observations([event], Path("system_activity.csv"))[0]
        self.assertEqual(item.provenance.evidence_id, "activity_1")
        self.assertEqual(item.nature, EvidenceNature.OPERATION_EVENT)
        self.assertEqual(assess_resource_timeline("record_1", [item], BASE).status,
                         TimelineStatus.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
