from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from audit_agent.evidence_store import EvidenceStore
from audit_agent.identity import IdentityGraph
from audit_agent.linking import ResourceLinker
from audit_agent.models import (
    ActivityEvent, EvidenceNature, Identifier, IdentifierKind, IdentityEvent,
    IdentitySnapshot, Observation, Provenance, Resource,
    RelationshipType, RelationshipValidity, ResourceRelationship,
)
from audit_agent.normalization import normalize_identifier
from audit_agent.policy import PolicyEngine
from audit_agent.provenance import ProvenanceValidator
from audit_agent.relationships import ResourceRelationshipGraph
from tests.test_policy_planning import rules

UTC = timezone.utc
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def identifier(kind: IdentifierKind, value: str, path: str = "$.subject") -> Identifier:
    return Identifier(kind, value, normalize_identifier(kind, value), path)


def identity_graph() -> IdentityGraph:
    snapshots = [
        IdentitySnapshot("user_a", "Alex One", "new-a@example.test", "+10000000001", "a" * 64, NOW),
        IdentitySnapshot("user_b", "Alex Two", "b@example.test", "+10000000002", "b" * 64, NOW),
    ]
    events = [IdentityEvent("audit_a", "user_a", NOW - timedelta(days=30), "email",
                            "old-a@example.test", "new-a@example.test")]
    return IdentityGraph(snapshots, events)


def observation(resource_id: str, category: str, state: str, identifiers=(), attrs=None,
                *, observed_at=NOW, captured_at=NOW, evidence="evidence_synthetic") -> Observation:
    return Observation(
        Resource(resource_id, "test_system", "test_primary", category), state,
        observed_at, captured_at, tuple(identifiers), attrs or {},
        Provenance(evidence, Path("synthetic.json"), "synthetic", "row=1", "synthetic-v1"),
        nature=EvidenceNature.STATE_OBSERVATION,
    )


class RelationshipSafetyTests(unittest.TestCase):
    def test_two_users_sharing_resource_are_not_merged(self):
        graph = identity_graph()
        observations = [
            observation("support_7001", "SUPPORT_MESSAGE", "PRESENT",
                        [identifier(IdentifierKind.USER_ID, "user_a")]),
            observation("support_7001", "SUPPORT_MESSAGE", "PRESENT",
                        [identifier(IdentifierKind.USER_ID, "user_b")], evidence="evidence_other"),
        ]
        relationships = ResourceRelationshipGraph.build(graph, observations, ())
        self.assertNotIn("support_7001", relationships.resources_for_user("user_a", NOW))
        self.assertNotIn("support_7001", relationships.resources_for_user("user_b", NOW))

    def test_identifier_free_retained_record_follows_explicit_parent_link(self):
        graph = identity_graph()
        parent = observation("account_7001", "USER_PROFILE", "ABSENT",
                             [identifier(IdentifierKind.USER_ID, "user_a")])
        retained = observation("audit_record_7001", "SECURITY_AUDIT_LOG", "PRESENT", (),
                               {"parent_resource_id": "account_7001", "integrity": "sealed"})
        relationships = ResourceRelationshipGraph.build(graph, [parent, retained], ())
        self.assertIn("audit_record_7001", relationships.resources_for_user("user_a", NOW))
        assessment = PolicyEngine(rules()).assess([retained], NOW)
        self.assertEqual(assessment.compliance.value, "COMPLIANT")

    def test_relationship_captured_after_audit_is_not_applicable(self):
        graph = identity_graph()
        later = observation("search_7001", "SEARCH_INDEX_ENTRY", "PRESENT",
                            [identifier(IdentifierKind.USER_ID, "user_a")],
                            observed_at=NOW + timedelta(hours=1),
                            captured_at=NOW + timedelta(hours=1))
        relationships = ResourceRelationshipGraph.build(graph, [later], ())
        self.assertNotIn("search_7001", relationships.resources_for_user("user_a", NOW))

    def test_backup_referencing_multiple_users_is_ambiguous(self):
        graph = identity_graph()
        backup = observation(
            "backup_7001", "BACKUP_ARCHIVE", "ACTIVE",
            [identifier(IdentifierKind.USER_ID, "user_a", "$.subjects[0]"),
             identifier(IdentifierKind.USER_ID, "user_b", "$.subjects[1]")],
            {"restore_allowed": True},
        )
        relationships = ResourceRelationshipGraph.build(graph, [backup], ())
        self.assertNotIn("backup_7001", relationships.resources_for_user("user_a", NOW))
        self.assertTrue(relationships.ambiguous_edges())

    def test_operation_without_identity_is_not_proof_of_resource_ownership(self):
        graph = identity_graph()
        activity = ActivityEvent("activity_7001", NOW, "DELETE_RECORD", "worker",
                                 "account_service", "account_7999", "SUCCESS",
                                 "Deletion completed for the named resource.")
        relationships = ResourceRelationshipGraph.build(graph, (), [activity])
        self.assertNotIn("account_7999", relationships.resources_for_user("user_a", NOW))

    def test_compliant_tombstone_with_stable_user_id_is_linked(self):
        graph = identity_graph()
        tombstone = observation(
            "tombstone_7001", "ACCOUNT_TOMBSTONE", "PRESENT",
            [identifier(IdentifierKind.USER_ID, "user_a")],
            {"subject_reference": "user_a", "name": None, "email": None,
             "phone": None, "email_hash": None},
        )
        relationships = ResourceRelationshipGraph.build(graph, [tombstone], ())
        self.assertIn("tombstone_7001", relationships.resources_for_user("user_a", NOW))
        assessment = PolicyEngine(rules()).assess([tombstone], NOW)
        self.assertEqual(assessment.compliance.value, "COMPLIANT")

    def test_historical_email_provenance_links_without_using_name(self):
        graph = identity_graph()
        record = observation("search_7010", "SEARCH_INDEX_ENTRY", "PRESENT",
                             [identifier(IdentifierKind.EMAIL, "old-a@example.test")])
        relationships = ResourceRelationshipGraph.build(graph, [record], ())
        self.assertIn("search_7010", relationships.resources_for_user("user_a", NOW))
        edges = relationships.supporting_edges("user_a", "search_7010", NOW)
        self.assertEqual(edges[0].relationship_type.value, "HISTORICAL_IDENTITY")
        self.assertIn("audit_a", edges[0].supporting_provenance)

    def test_explicit_source_resource_relationship_is_traversable(self):
        graph = identity_graph()
        account = observation("account_7011", "USER_PROFILE", "ABSENT",
                              [identifier(IdentifierKind.USER_ID, "user_a")])
        search = observation("search_7011", "SEARCH_INDEX_ENTRY", "ABSENT", (),
                             {"source_resource_id": "account_7011"})
        relationships = ResourceRelationshipGraph.build(graph, [account, search], ())
        self.assertIn("search_7011", relationships.resources_for_user("user_a", NOW))

    def test_unknown_relationship_provenance_is_rejected(self):
        edge = ResourceRelationship(
            "user:user_a", "resource:account_7012", RelationshipType.STABLE_USER_ID,
            ("invented_evidence",), NOW, None, NOW, 1.0,
            RelationshipValidity.VALIDATED,
        )
        result = ProvenanceValidator([], [], [], EvidenceStore()).validate_relationships((edge,))
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "UNKNOWN_RELATIONSHIP_PROVENANCE")


if __name__ == "__main__":
    unittest.main()
