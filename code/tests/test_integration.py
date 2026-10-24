from pathlib import Path
import unittest

from audit_agent.identity import IdentityGraph
from audit_agent.ingestion import ingest_structured_evidence
from audit_agent.loaders import load_evidence_manifest, load_identities, load_identity_events, load_requests

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "dataset"


class ParticipantDataIntegrationTests(unittest.TestCase):
    def test_all_requests_resolve_without_merging(self):
        graph = IdentityGraph(load_identities(DATASET / "user_identities.csv"),
                              load_identity_events(DATASET / "user_audit_log.csv"))
        requests = load_requests(DATASET / "deletion_requests.csv")
        resolutions = [graph.resolve_email(item.email, at=item.audit_at) for item in requests]
        self.assertEqual(len(requests), 518)
        self.assertTrue(all(item.resolved_user_id is not None for item in resolutions))
        self.assertTrue(all(not item.ambiguous for item in resolutions))

    def test_entire_structured_corpus_is_indexed(self):
        manifest = load_evidence_manifest(DATASET / "evidence_files.csv", DATASET)
        summary = ingest_structured_evidence(manifest)
        self.assertEqual(summary.parsed_files, 79)
        self.assertEqual(summary.skipped_unstructured_files, 15)
        self.assertGreater(summary.observations, 3000)
        first = summary.store.observations[0]
        self.assertTrue(summary.store.by_resource_id(first.resource.resource_id))
        self.assertTrue(summary.store.by_system_id(first.resource.logical_system))


if __name__ == "__main__":
    unittest.main()
