import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import role_context


class RoleContextTests(unittest.TestCase):
    def tearDown(self): role_context.current.set(None)

    def setup_rows(self, ids):
        rows = []
        for i, (role, supported, box) in enumerate(ids):
            rows.append({'frame': i, 't': i, 'tracks': [] if box is None else [
                {'person_id': role, 'box': box, 'association': {'usable_for_actions': supported}}]})
        role_context.current.set({'fps': 1, 'info': {'width': 100}, 'rows': rows,
                                  'people': {'banker': {'role': 'banker'}, 'customer': {'role': 'customer'}}})
        return [{'t': i} for i in range(len(rows))]

    def test_missing_box_does_not_prove_leaving(self):
        rows = self.setup_rows([('banker', True, [0, 0, 10, 10]), ('banker', False, None), ('banker', False, None)])
        events = role_context.desk_events(rows, [0, 0, 20, 20], 100)
        self.assertEqual(events['leaves'], []); self.assertEqual(events['empty'], [])

    def test_customer_is_not_employee_evidence(self):
        self.setup_rows([('customer', True, [0, 0, 10, 10])])
        self.assertEqual(role_context.banker_boxes(0, 100), [])

    def test_supported_movement_away_is_evidence(self):
        rows = self.setup_rows([('banker', True, [0, 0, 10, 10]), ('banker', True, [50, 50, 60, 60]),
                                ('banker', True, [50, 50, 60, 60]), ('banker', True, [0, 0, 10, 10])])
        events = role_context.desk_events(rows, [0, 0, 20, 20], 100)
        self.assertEqual(events['leaves'], [1]); self.assertEqual(events['empty'], [[1, 3]])

    def test_nobody_detected_at_desk_is_evidence_of_leaving(self):
        rows = self.setup_rows([('banker', True, [0, 0, 10, 10]), ('banker', False, None),
                                ('banker', False, None), ('banker', False, None)])
        rows = [dict(r, objects=[{'label': 'person', 'box': [0, 0, 10, 10]}] if r['t'] == 0 else
                     [{'label': 'person', 'box': [80, 80, 90, 90]}]) for r in rows]
        events = role_context.desk_events(rows, [0, 0, 20, 20], 100)
        self.assertEqual(events['leaves'], [1]); self.assertEqual(events['empty'], [[1, 3]])

    def test_unidentified_person_at_desk_is_not_absence(self):
        rows = self.setup_rows([('banker', True, [0, 0, 10, 10]), ('banker', False, None), ('banker', False, None)])
        rows = [dict(r, objects=[{'label': 'person', 'box': [5, 5, 15, 15]}]) for r in rows]
        events = role_context.desk_events(rows, [0, 0, 20, 20], 100)
        self.assertEqual(events['leaves'], []); self.assertEqual(events['empty'], [])

    def test_uncertain_link_does_not_support_employee(self):
        self.setup_rows([('banker', False, [0, 0, 10, 10])])
        self.assertEqual(role_context.banker_boxes(0, 100), [])


if __name__ == '__main__': unittest.main()
