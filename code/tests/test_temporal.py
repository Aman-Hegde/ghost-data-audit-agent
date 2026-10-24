from datetime import datetime, timezone
from pathlib import Path
import unittest

from audit_agent.models import Observation, Provenance, Resource, TemporalSemantics
from audit_agent.temporal import observation_usable_at, reconstruct_resource_history

UTC = timezone.utc


def observation(state, observed, captured, physical, semantics=TemporalSemantics.POINT_IN_TIME):
    return Observation(Resource("record_1", "account_service", physical, "USER_PROFILE"), state,
                       observed, captured, (), {}, Provenance("e1", Path("x"), "test", "row", "test"), semantics)


class TemporalTests(unittest.TestCase):
    def test_later_current_state_is_not_backdated(self):
        cutoff = datetime(2026, 1, 10, tzinfo=UTC)
        item = observation("ABSENT", datetime(2026, 1, 9, tzinfo=UTC), datetime(2026, 1, 11, tzinfo=UTC), "primary")
        self.assertFalse(observation_usable_at(item, cutoff))
        self.assertFalse(observation_usable_at(item, cutoff, allow_retrospective=True))

    def test_later_historical_event_requires_explicit_retrospective_mode(self):
        cutoff = datetime(2026, 1, 10, tzinfo=UTC)
        item = observation("SUCCESS", datetime(2026, 1, 9, tzinfo=UTC), datetime(2026, 1, 11, tzinfo=UTC),
                           "event_log", TemporalSemantics.EVENT_OCCURRED)
        self.assertFalse(observation_usable_at(item, cutoff))
        self.assertTrue(observation_usable_at(item, cutoff, allow_retrospective=True))

    def test_contradictory_replicas_remain_visible(self):
        cutoff = datetime(2026, 1, 10, tzinfo=UTC)
        items = [
            observation("ABSENT", datetime(2026, 1, 9, 10, tzinfo=UTC), datetime(2026, 1, 9, 11, tzinfo=UTC), "primary"),
            observation("PRESENT", datetime(2026, 1, 9, 10, tzinfo=UTC), datetime(2026, 1, 9, 11, tzinfo=UTC), "replica"),
        ]
        history = reconstruct_resource_history("record_1", items, cutoff)
        self.assertTrue(history.contradictory)
        self.assertEqual(set(history.latest_by_physical_system), {"primary", "replica"})


if __name__ == "__main__":
    unittest.main()
