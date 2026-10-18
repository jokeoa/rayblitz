import unittest
from copy import deepcopy

from safe_side_labels import apply_labels, classify


PEOPLE = {'P1': {'role': 'banker'}}


def track(**kwargs):
    return {'id': 2, 'box': [0, 0, 10, 10], 'person_id': None, 'candidate_person_id': None,
            'reference_match': {'kind': 'unverified_person'},
            'association': {'confidence': 'unresolved', 'reason': 'not_initialized_or_not_banker', 'usable_for_actions': False}, **kwargs}


class LabelsTests(unittest.TestCase):
    def test_remaining_person_is_customer_after_selection(self):
        label = classify(track(), PEOPLE, 'P1')
        self.assertEqual(label['role'], 'customer')
        self.assertEqual(label['basis'], 'non_banker_default')

    def test_reflection_is_not_customer(self):
        label = classify(track(reference_match={'kind': 'possible_reflection'}), PEOPLE, 'P1')
        self.assertTrue(label['possible_reflection'])
        self.assertEqual(label['role'], 'unknown')

    def test_lost_banker_link_is_not_customer(self):
        self.assertEqual(classify(track(candidate_person_id='P1'), PEOPLE, 'P1')['role'], 'unknown')
        tr = track(); tr['association']['reason'] = 'different_identity_not_established'
        self.assertEqual(classify(tr, PEOPLE, 'P1')['role'], 'unknown')

    def test_initialization_does_not_label_future_banker_customer(self):
        self.assertEqual(classify(track(), {}, None)['role'], 'unknown')

    def test_previous_banker_keeps_role(self):
        self.assertEqual(classify(track(person_id='P1'), PEOPLE, 'P2')['role'], 'banker')

    def test_reflection_veto_is_separate_from_identity_and_input(self):
        tr = track(person_id='P1', candidate_person_id='P1')
        tr['association'].update(confidence='supported', usable_for_actions=True)
        banker = {'source_sha256': 'same', 'fps': 10, 'people': PEOPLE,
                  'rows': [{'frame': 20, 't': 2., 'active_banker_person_id': 'P1', 'tracks': [tr]}]}
        baseline = deepcopy(banker)
        baseline['rows'][0]['tracks'][0]['reference_match']['kind'] = 'possible_reflection'
        result = apply_labels(banker, baseline)
        labeled = result['rows'][0]['tracks'][0]
        self.assertFalse(labeled['association']['usable_for_actions'])
        self.assertEqual(labeled['association']['confidence'], 'supported')
        self.assertEqual(labeled['classification']['role'], 'banker')
        self.assertEqual(result['people'], PEOPLE)
        self.assertTrue(banker['rows'][0]['tracks'][0]['association']['usable_for_actions'])
        baseline['rows'][0]['tracks'][0]['box'] = [1, 2, 3, 4]
        with self.assertRaises(ValueError): apply_labels(banker, baseline)


if __name__ == '__main__': unittest.main()
