import unittest
from common import greedy_matches, original_box, tiles
from desk_scope import in_desk_region


class GeometryTests(unittest.TestCase):
    def test_desk_gate_keeps_tall_objects_by_base_but_is_not_contact_evidence(self):
        desk = {"box": [10, 20, 100, 80]}
        self.assertTrue(in_desk_region({"class": "laptop", "box": [20, 5, 70, 40]}, desk))
        self.assertFalse(in_desk_region({"class": "cash", "box": [20, 5, 70, 15]}, desk))
        self.assertFalse(in_desk_region({"class": "safe", "box": [20, 30, 70, 60]}, desk))
        self.assertFalse(in_desk_region({"class": "bag", "box": [110, 30, 140, 60]}, desk))

    def test_tiles_cover_frame_without_duplicate_windows(self):
        boxes = tiles(464, 848, 384, .2)
        self.assertEqual(len(boxes), 6)
        self.assertEqual(len(boxes), len(set(boxes)))
        for y in range(848):
            for x in range(464):
                self.assertTrue(any(a <= x < c and b <= y < d for a, b, c, d in boxes))

    def test_native_coordinate_round_trip(self):
        self.assertEqual(original_box([10, 20, 30, 40], (100, 200, 300, 600), (100, 200)),
                         [120, 240, 160, 280])
        self.assertEqual(original_box([-10, -20, 400, 900], (0, 0, 464, 848), (464, 848)),
                         [0, 0, 400, 848])

    def test_duplicate_prediction_cannot_claim_same_ground_truth(self):
        gt = [{"class": "cash", "box": [10, 10, 20, 20]}]
        predictions = [{"class": "cash", "box": [10, 10, 20, 20], "score": s} for s in [.3, .7]]
        self.assertEqual(greedy_matches(predictions, gt), [(1, 0)])
        predictions[1]["class"] = "card"
        self.assertEqual(greedy_matches(predictions, gt), [(0, 0)])


if __name__ == "__main__":
    unittest.main()
