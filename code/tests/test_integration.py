from pathlib import Path
import unittest

from audit_agent.identity import IdentityGraph
from audit_agent.ingestion import ingest_evidence, ingest_structured_evidence
from audit_agent.loaders import (load_activity, load_evidence_manifest, load_identities,
                                 load_identity_events, load_requests)
from audit_agent.provenance import ProvenanceValidator

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

    def test_all_multimodal_evidence_is_accounted_for(self):
        manifest = load_evidence_manifest(DATASET / "evidence_files.csv", DATASET)
        identity_events = load_identity_events(DATASET / "user_audit_log.csv")
        graph = IdentityGraph(load_identities(DATASET / "user_identities.csv"), identity_events)
        result = ingest_evidence(manifest, identity_graph=graph)
        self.assertEqual(result.coverage.manifest_files, 94)
        self.assertEqual(result.coverage.parsed_files, 94)
        self.assertEqual(result.coverage.unresolved_files, 0)
        self.assertEqual(result.coverage.parser_errors, 0)
        self.assertEqual(len([a for a in result.artifacts if a.method.startswith("embedded_text")]), 4)
        self.assertEqual(len([a for a in result.artifacts if a.method.startswith("content_hash_cache")]), 11)
        validation = ProvenanceValidator(manifest, load_activity(DATASET / "system_activity.csv"),
                                         identity_events, result.store).validate_index()
        self.assertTrue(validation.valid, validation.issues)


if __name__ == "__main__":
    unittest.main()
