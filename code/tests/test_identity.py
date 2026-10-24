from datetime import datetime, timezone
import unittest

from audit_agent.identity import IdentityGraph
from audit_agent.models import IdentityEvent, IdentitySnapshot

UTC = timezone.utc


class IdentityGraphTests(unittest.TestCase):
    def test_historical_email_is_time_aware(self):
        snapshot = IdentitySnapshot("user_a", "A", "new@example.test", "+1 222", "hash-new",
                                    datetime(2026, 2, 1, tzinfo=UTC))
        event = IdentityEvent("audit_1", "user_a", datetime(2026, 1, 15, tzinfo=UTC), "email",
                              "old@example.test", "new@example.test")
        graph = IdentityGraph([snapshot], [event])
        before = graph.resolve_email("OLD@example.test", at=datetime(2026, 1, 10, tzinfo=UTC), include_historical=False)
        after_active = graph.resolve_email("old@example.test", at=datetime(2026, 1, 20, tzinfo=UTC), include_historical=False)
        historical = graph.resolve_email("old@example.test", at=datetime(2026, 1, 20, tzinfo=UTC))
        self.assertEqual(before.resolved_user_id, "user_a")
        self.assertIsNone(after_active.resolved_user_id)
        self.assertEqual(historical.resolved_user_id, "user_a")

    def test_identity_collision_is_not_merged(self):
        when = datetime(2026, 1, 1, tzinfo=UTC)
        snapshots = [
            IdentitySnapshot("user_a", "Same", "shared@example.test", "+1", "h1", when),
            IdentitySnapshot("user_b", "Same", "shared@example.test", "+2", "h2", when),
        ]
        resolution = IdentityGraph(snapshots, []).resolve_email("shared@example.test")
        self.assertTrue(resolution.ambiguous)
        self.assertIsNone(resolution.resolved_user_id)
        self.assertEqual(resolution.user_ids, ("user_a", "user_b"))


if __name__ == "__main__":
    unittest.main()
