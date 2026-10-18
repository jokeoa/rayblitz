import unittest
import numpy as np
from reference_policy import ReferenceAssociator


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = ReferenceAssociator([{'category': c, 'feature': np.eye(3)[i], 'reference': c}
                                      for i, c in enumerate(('banker', 'customer', 'reflection'))])
        self.box = {'id': 1, 'box': [0, 0, 100, 200], 'score': .9, 'det_idx': 0}

    def step(self, t, feature=(1, 0, 0), box=None):
        return self.p.update(t, [box or self.box], [feature])[0]

    def seed(self):
        self.step(0); self.step(.1); return self.step(.2)

    def test_requires_repeated_evidence(self):
        self.assertIsNone(self.step(0)['person_id'])
        self.assertIsNone(self.step(.1)['person_id'])
        self.assertEqual(self.step(.2)['person_id'], 'P1')
        self.assertEqual(self.p.people['P1']['initialized_at'], .2)

    def test_role_never_changes_on_conflicting_appearance(self):
        self.seed(); row = self.step(.3, (0, 1, 0))
        self.assertEqual(self.p.people['P1']['role'], 'banker')
        self.assertIsNone(row['person_id'])
        self.assertFalse(row['association']['usable_for_actions'])
        self.assertEqual(self.step(.4)['person_id'], 'P1')

    def test_reflection_is_not_a_person(self):
        for t in (0, .1, .2, .3): self.step(t, (0, 0, 1))
        self.assertFalse(self.p.people)

    def test_reconnects_short_fragment_with_position_and_appearance(self):
        self.seed(); row = self.step(.4, box={**self.box, 'id': 2})
        self.assertEqual(row['person_id'], 'P1')
        self.assertEqual(row['association']['reason'], 'appearance_and_position_reconnection')
        self.assertEqual(len(self.p.people), 1)

    def test_long_gap_does_not_inherit_role(self):
        self.seed(); row = self.step(4)
        self.assertIsNone(row['person_id'])
        self.assertEqual(self.p.people['P1']['role'], 'banker')

    def test_reconnection_retires_old_tracker_binding(self):
        self.seed(); self.step(.4, box={**self.box, 'id': 2})
        self.assertNotIn(1, self.p.track_people)
        rows = self.p.update(.5, [{**self.box, 'box': [200, 0, 300, 200]}, {**self.box, 'id': 2}],
                             [(0, 1, 0), (1, 0, 0)])
        self.assertIsNone(rows[0]['person_id'])
        self.assertEqual(rows[1]['person_id'], 'P1')

    def test_jump_blocks_attribution(self):
        self.seed(); row = self.step(.3, box={**self.box, 'box': [400, 0, 500, 200]})
        self.assertEqual(row['association']['reason'], 'geometric_jump')
        self.assertIsNone(row['person_id'])

    def test_overlap_blocks_actions_without_clearing_role(self):
        self.seed()
        rows = self.p.update(.3, [self.box, {**self.box, 'id': 2}], [(1, 0, 0), (1, 0, 0)])
        self.assertFalse(rows[0]['association']['usable_for_actions'])
        self.assertEqual(rows[0]['person_id'], 'P1')
        self.assertEqual(self.p.people['P1']['role'], 'banker')
        self.assertIsNone(rows[1]['person_id'])


if __name__ == '__main__': unittest.main()
