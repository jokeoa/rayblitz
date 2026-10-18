"""Regression tests for immutable roles and independent identity uncertainty."""
import unittest

from anchored_role_policy import anchored_role_timeline
from anchored_role_evaluate import prediction


class StaticRoleTests(unittest.TestCase):
    cfg = {'role_reset_gap_seconds': 1, 'role_min_votes': 2, 'overlap_fraction': .3,
           'min_step_iou': .1, 'max_normalized_step': .35, 'max_interval_seconds': 2.01}

    def run_case(self, samples):
        tracks, roles, physical = [], [], []
        for i, (t, people) in enumerate(samples):
            tracks.append({'frame': i, 't': t, 'tracks': [
                {'id': p[0], 'det_idx': j, 'overlap': p[3], 'box': p[4] if len(p) > 4 else [j*200, 0, j*200+100, 200]}
                for j, p in enumerate(people)]})
            roles.append({'frame': i, 't': t, 'people': [
                {'detection_id': j, 'role': p[1]} for j, p in enumerate(people) if p[1] is not None]})
            physical.append({'frame': i, 't': t, 'people': [
                {'detection_id': j, 'kind': p[2]} for j, p in enumerate(people) if p[2] is not None]})
        return anchored_role_timeline(tracks, roles, physical, self.cfg)

    def test_detector_rank_does_not_select_banker(self):
        rows, meta = self.run_case([(0, [(10, 'customer', 'direct', 0), (20, 'banker', 'direct', 0)])])
        banker = meta['people'][meta['opening_banker_person_id']]
        self.assertEqual(banker['track_id'], 20)
        self.assertEqual(banker['role'], 'banker')
        self.assertNotIn('role', rows[0]['tracks'][1])

    def test_both_roles_stay_fixed_despite_later_semantic_flips(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0), (20, 'customer', 'direct', 0)]),
                                    (.1, [(10, 'banker', 'direct', 0), (20, 'customer', 'direct', 0)]),
                                    (.2, [(10, 'customer', 'direct', 0), (20, 'banker', 'direct', 0)])])
        for row in rows:
            self.assertEqual([meta['people'][t['person_id']]['role'] for t in row['tracks']], ['banker', 'customer'])
        self.assertEqual(meta['people']['E1']['conflicting_observations'], 1)
        self.assertEqual(meta['people']['E2']['conflicting_observations'], 1)

    def test_overlap_only_changes_association_without_fresh_role_vote(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, 'customer', None, .5)]),
                                    (.2, [(10, None, None, 0)])])
        self.assertEqual(meta['people']['E1']['role'], 'banker')
        self.assertEqual([r['tracks'][0]['association']['confidence'] for r in rows], ['supported', 'uncertain', 'supported'])
        self.assertEqual([r['tracks'][0]['person_id'] for r in rows], ['E1'] * 3)
        self.assertFalse(rows[1]['tracks'][0]['association']['usable_for_actions'])

    def test_unknown_physical_observation_does_not_erase_established_person(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, None, 'uncertain', 0)])])
        self.assertEqual(rows[-1]['tracks'][0]['person_id'], 'E1')
        self.assertEqual(meta['people']['E1']['role'], 'banker')

    def test_gap_preserves_person_role_but_invalidates_link(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (2, [(10, 'banker', 'direct', 0)]),
                                    (2.1, [(10, 'banker', 'direct', 0)])])
        self.assertEqual(meta['people']['E1']['role'], 'banker')
        self.assertIsNone(rows[-1]['tracks'][0]['person_id'])
        self.assertEqual(rows[-1]['tracks'][0]['candidate_person_id'], 'E1')
        self.assertFalse(rows[-1]['tracks'][0]['association']['usable_for_actions'])

    def test_new_tracker_id_does_not_inherit_banker(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(20, 'banker', 'direct', 0)]),
                                    (.2, [(20, 'banker', 'direct', 0)])])
        self.assertNotEqual(rows[0]['tracks'][0]['person_id'], rows[-1]['tracks'][0]['person_id'])
        self.assertEqual(meta['people'][rows[-1]['tracks'][0]['person_id']]['role'], 'unknown')

    def test_geometric_jump_does_not_inherit_role(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, 'banker', 'direct', 0, [500, 0, 600, 200])])])
        self.assertIsNone(rows[-1]['tracks'][0]['person_id'])
        self.assertEqual(meta['people']['E1']['role'], 'banker')

    def test_reflection_cannot_seed_person_or_role(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'reflection', 0)]),
                                    (.1, [(10, 'banker', 'reflection', 0)])])
        self.assertEqual(meta['people'], {})
        self.assertTrue(all(r['tracks'][0]['person_id'] is None for r in rows))

    def test_reflection_conflict_does_not_erase_role_or_auto_recover(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, 'banker', 'reflection', 0)]),
                                    (.2, [(10, 'banker', 'direct', 0)])])
        self.assertEqual(meta['people']['E1']['role'], 'banker')
        self.assertIsNone(rows[-1]['tracks'][0]['person_id'])

    def test_multiple_opening_bankers_abstain(self):
        _, meta = self.run_case([(0, [(10, 'banker', 'direct', 0), (20, 'banker', 'direct', 0)])])
        self.assertIsNone(meta['opening_banker_person_id'])
        self.assertTrue(all(p['role'] == 'unknown' for p in meta['people'].values()))

    def test_unclassified_person_is_not_automatically_a_customer(self):
        _, meta = self.run_case([(0, [(10, 'banker', 'direct', 0), (20, 'other', 'direct', 0)]),
                                 (.1, [(10, 'banker', 'direct', 0), (20, 'other', 'direct', 0)])])
        self.assertEqual(meta['people']['E2']['role'], 'unknown')

    def test_future_roles_do_not_affect_association_prefix(self):
        samples = [(0, [(10, 'customer', 'direct', 0)]),
                   (.1, [(10, 'customer', 'direct', 0)])]
        full, meta = self.run_case(samples)
        prefix, prefix_meta = self.run_case(samples[:1])
        self.assertEqual(full[:1], prefix)
        self.assertEqual(meta['people']['E1']['role'], 'customer')
        self.assertEqual(prefix_meta['people']['E1']['role'], 'unknown')  # Whole-clip role estimation is offline.

    def test_duplicate_track_ids_invalidate_both_links(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, 'banker', 'direct', 0), (10, 'customer', 'direct', 0)])])
        self.assertTrue(all(t['person_id'] is None for t in rows[-1]['tracks']))
        self.assertEqual(meta['people']['E1']['role'], 'banker')

    def test_competing_person_geometry_flags_silent_swap(self):
        a, b = [0, 0, 100, 200], [30, 0, 130, 200]
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0, a), (20, 'customer', 'direct', 0, b)]),
                                    (.1, [(10, 'banker', 'direct', 0, b), (20, 'customer', 'direct', 0, a)])])
        for tr in rows[-1]['tracks']:
            self.assertIsNone(tr['person_id'])
            self.assertIn('competing_person_geometry', tr['association']['reasons'])
        self.assertEqual(meta['people']['E1']['role'], 'banker')

    def test_empty_input(self):
        rows, meta = anchored_role_timeline([], [], [], self.cfg)
        self.assertEqual(rows, [])
        self.assertEqual(meta['people'], {})

    def test_known_role_on_uncertain_box_is_not_scored_as_actionable(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (.1, [(10, None, None, .5)])])
        result = prediction(rows[-1], {'detection_id': 0, 'box': [0, 0, 100, 200]}, 'after', meta['people'])
        self.assertEqual(result['assigned_role'], 'banker')
        self.assertEqual(result['role'], 'unknown')

    def test_broken_link_does_not_score_candidate_role(self):
        rows, meta = self.run_case([(0, [(10, 'banker', 'direct', 0)]),
                                    (2, [(10, 'banker', 'direct', 0)])])
        result = prediction(rows[-1], {'detection_id': 0, 'box': [0, 0, 100, 200]}, 'after', meta['people'])
        self.assertEqual(result['candidate_role'], 'banker')
        self.assertEqual(result['assigned_role'], 'unknown')
        self.assertEqual(result['role'], 'unknown')


if __name__ == '__main__':
    unittest.main()
