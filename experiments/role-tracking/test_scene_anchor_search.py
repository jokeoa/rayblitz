import unittest
from copy import deepcopy
from PIL import Image

from scene_anchor_search import resolve_anchor, SAFE_QUERIES, PROXY_QUERIES

GEO = {'objects': {'desk': {'box': [100, 100, 300, 200], 'side_divider': [[100, 150], [300, 150]]}, 'safe': None}, 'available_at': 2.}
BOX = [300, 20, 400, 80]


class AnchorTests(unittest.TestCase):
    def setUp(self): self.images = [Image.new('RGB', (464, 848)) for _ in range(10)]

    def test_frozen_safe_never_calls_detector(self):
        geometry = deepcopy(GEO); geometry['objects']['safe'] = {'box': BOX}
        def fail(*args): self.fail('Frozen safe must not trigger search')
        self.assertEqual(resolve_anchor(geometry, [], fail), geometry)

    def test_detected_safe_precedes_proxy(self):
        calls = []
        def detect(images, queries):
            calls.append(queries); return [[(.8, BOX)]] * len(images)
        result = resolve_anchor(GEO, self.images, detect)
        self.assertEqual(calls, [SAFE_QUERIES])
        self.assertEqual(result['objects']['safe']['kind'], 'safe')

    def test_missing_safe_uses_stable_storage_proxy(self):
        calls = []
        def detect(images, queries):
            calls.append(queries)
            return [[]] * len(images) if queries == SAFE_QUERIES else [[(.7, BOX)]] * len(images)
        result = resolve_anchor(GEO, self.images, detect)
        self.assertEqual(calls, [SAFE_QUERIES, PROXY_QUERIES])
        self.assertEqual(result['objects']['safe']['kind'], 'safe_like_storage')
        self.assertTrue(result['objects']['safe']['hypothesis'])
        self.assertIsNone(GEO['objects']['safe'])

    def test_opposite_sides_are_ambiguous(self):
        def detect(images, queries): return [[(.8, BOX), (.8, [300, 220, 400, 280])]] * len(images)
        result = resolve_anchor(GEO, self.images, detect)
        self.assertIsNone(result['objects']['safe'])
        self.assertEqual(result['anchor_search']['attempts'][0]['reason'], 'ambiguous_desk_side')

    def test_single_frame_candidate_is_not_enough(self):
        def detect(images, queries): return [[(.8, BOX)]] + [[]] * (len(images)-1)
        self.assertIsNone(resolve_anchor(GEO, self.images, detect)['objects']['safe'])

    def test_distant_object_or_divider_object_cannot_orient_desk(self):
        for box in ([300, 700, 400, 800], [300, 120, 400, 180]):
            def detect(images, queries): return [[(.8, box)]] * len(images)
            self.assertIsNone(resolve_anchor(GEO, self.images, detect)['objects']['safe'])

    def test_partial_detector_output_is_rejected(self):
        with self.assertRaises(ValueError): resolve_anchor(GEO, self.images, lambda images, queries: [])


if __name__ == '__main__': unittest.main()
