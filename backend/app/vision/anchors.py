"""Search a missing safe, then safe-like storage; never replace a frozen safe."""
from copy import deepcopy
from math import hypot

from .reflection_filter import iou
from .safe_side_policy import geometry_axis

SAFE_QUERIES = ['a grey metal safe', 'a bank safe with a lock', 'a small security safe']
PROXY_QUERIES = ['a small metal storage cabinet', 'an office pedestal cabinet with drawers', 'a low lockable storage cabinet']


def consensus(per_frame, geometry, width, height):
    """A stable nearby object on one unambiguous side of the reviewed desk."""
    if not per_frame:
        return None, 'no_frames'
    desk = geometry['objects']['desk']['box']
    scale = hypot(desk[2]-desk[0], desk[3]-desk[1])
    center = ((desk[0]+desk[2])/2, (desk[1]+desk[3])/2)
    choices = []
    for frame in per_frame:
        for score, raw_box in frame:
            if score < .15:
                continue
            box = [max(0., min(v, width if k % 2 == 0 else height)) for k, v in enumerate(raw_box)]
            x0, y0, x1, y1 = box
            if x1 <= x0 or y1 <= y0 or (x1-x0)*(y1-y0) < .002*width*height:
                continue
            if hypot((x0+x1)/2-center[0], (y0+y1)/2-center[1]) > 1.4*scale:
                continue
            candidate = {**geometry, 'objects': {**geometry['objects'], 'safe': {'box': box}}}
            axis = geometry_axis(candidate)
            if axis is None:
                continue
            scores = [max((s for s, b in rows if s >= .15 and iou(box, b) >= .5), default=0.) for rows in per_frame]
            support = sum(s > 0 for s in scores) / len(scores)
            if support >= .7:
                choices.append({'box': box, 'support': support, 'score': sum(scores)/len(scores), 'unit': axis['unit']})
    if not choices:
        return None, 'no_stable_nearby_candidate'
    # Objects on both sides do not tell us which side belongs to the banker.
    first = choices[0]['unit']
    if any(first[0]*c['unit'][0]+first[1]*c['unit'][1] < 0 for c in choices):
        return None, 'ambiguous_desk_side'
    return max(choices, key=lambda c: (c['support'], c['score'])), 'stable_candidate'


def resolve_anchor(geometry, images, detect):
    """detect(images, text_queries) uses the existing project object detector."""
    if geometry['objects']['safe'] is not None:
        return deepcopy(geometry)
    if not images:
        raise ValueError('Opening frames are required for anchor search')
    result = deepcopy(geometry)
    result['anchor_search'] = {'frames': len(images), 'attempts': [], 'status': 'unresolved'}
    width, height = images[0].size
    for kind, queries in [('safe', SAFE_QUERIES), ('safe_like_storage', PROXY_QUERIES)]:
        detections = detect(images, queries)
        if len(detections) != len(images):
            raise ValueError('Anchor detector did not process every opening frame')
        selected, reason = consensus(detections, geometry, width, height)
        result['anchor_search']['attempts'].append({'kind': kind, 'queries': queries, 'candidates': detections, 'reason': reason})
        if selected is not None:
            result['objects']['safe'] = {**selected, 'kind': kind, 'source': 'opening_window_detector_consensus',
                                         'reference_id': None, 'hypothesis': True}
            result['basis'] = 'detected_safe_hypothesis' if kind == 'safe' else 'safe_like_anchor_hypothesis'
            result['anchor_search']['status'] = 'selected'
            break
        if reason == 'ambiguous_desk_side':
            break
    result['available_at'] = 2.
    return result

