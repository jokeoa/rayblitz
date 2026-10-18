"""Compare frozen previous output with static person roles on identical inputs."""
from collections import Counter

from common import ROOT, read_json, sha256, write_json
from reflection_filter import iou
from render import NAMES


def prediction(row, box, policy, people):
    matched = [t for t in row['tracks'] if t['det_idx'] == box['detection_id'] and iou(t['box'], box['box']) >= .5]
    if not matched:
        return {'role': 'unknown', 'assigned_role': 'unknown', 'status': 'not_tracked', 'track_id': None}
    if len(matched) > 1:
        return {'role': 'unknown', 'assigned_role': 'unknown', 'status': 'ambiguous', 'track_id': None}
    tr = matched[0]
    if policy == 'before':
        return {'role': tr['role'], 'assigned_role': tr['role'], 'status': 'matched',
                'track_id': tr['id'], 'reason': tr['role_reason']}
    pid = tr['person_id']
    role = people[pid]['role'] if pid is not None else 'unknown'
    candidate = tr['candidate_person_id']
    return {'role': role if tr['association']['usable_for_actions'] else 'unknown',
            'assigned_role': role, 'status': 'matched', 'track_id': tr['id'],
            'person_id': pid, 'candidate_person_id': candidate,
            'candidate_role': people[candidate]['role'] if candidate else 'unknown',
            'association': tr['association']}


def summarize(rows):
    direct = [r for r in rows if r['kind'] == 'person']
    reflected = [r for r in rows if r['kind'] == 'reflection']
    statuses = Counter('not_tracked' if r['prediction']['status'] == 'not_tracked' else
                       'ambiguous' if r['prediction']['status'] == 'ambiguous' else
                       'unknown' if r['prediction']['role'] == 'unknown' else
                       'correct' if r['prediction']['role'] == r['person_role'] else 'wrong_role'
                       for r in direct)
    actual = [r for r in direct if r['person_role'] == 'banker']
    predicted = [r for r in rows if r['prediction']['role'] == 'banker']
    tp = sum(r['kind'] == 'person' and r['person_role'] == 'banker' for r in predicted)
    return {'direct_boxes': len(direct), 'actionable_role_outcomes': dict(statuses),
            'banker': {'actual_boxes': len(actual), 'true_positive': tp, 'false_positive': len(predicted)-tp},
            'association_confidence': dict(Counter(r['prediction'].get('association', {}).get('confidence', 'not_separate_in_before') for r in direct)),
            'reflection_boxes': len(reflected),
            'reflections_assigned_service_roles': sum(r['prediction']['role'] in ('banker', 'customer') for r in reflected)}


def main():
    labels_path = ROOT / 'role_review_labels.json'
    labels, out = read_json(labels_path), ROOT / 'runs/static-roles'
    results, timelines = [], []
    for video in labels['videos']:
        vid = video['video']
        frames = [f for f in labels['frames'] if f['video'] == vid]
        if any(f['detections_sha256'] != sha256(ROOT / 'runs' / vid / 'detections.json') for f in frames):
            raise ValueError('Labels do not match detections')
        for method in NAMES:
            before = read_json(out / 'before' / vid / f'{method}.json')
            after = read_json(out / vid / f'{method}.json')
            if before['inputs'] != after['inputs'] or before['source_sha256'] != after['source_sha256']:
                raise ValueError('Before and after inputs differ')
            for policy, data in [('before', before), ('after', after)]:
                if any(f['source_sha256'] != data['source_sha256'] for f in frames):
                    raise ValueError('Source video mismatch')
                for frame in frames:
                    row = data['rows'][frame['frame']]
                    if row['frame'] != frame['frame'] or row['t'] != frame['t']:
                        raise ValueError('Timeline mismatch')
                    for box in frame['boxes']:
                        results.append({'video': vid, 'review_id': frame['review_id'], 't': frame['t'],
                                        'method': method, 'policy': policy, **box,
                                        'prediction': prediction(row, box, policy, data.get('people', {}))})
            banker = after['opening_banker_person_id']
            if banker is not None:
                track_id = after['people'][banker]['track_id']
                previous = [t for r in before['rows'] for t in r['tracks'] if t['id'] == track_id]
                current = [t for r in after['rows'] for t in r['tracks'] if t['id'] == track_id]
                levels = Counter(t['association']['confidence'] for t in current)
                timelines.append({'video': vid, 'method': method, 'banker_person_id': banker,
                                  'track_id': track_id, 'total_frames': len(after['rows']),
                                  'banker_track_frames': len(current),
                                  'before_unavailable_frames': sum(t['role'] != 'banker' for t in previous),
                                  'after_unavailable_frames': sum(not t['association']['usable_for_actions'] for t in current),
                                  'after_association_counts': dict(levels),
                                  'stored_role': after['people'][banker]['role'],
                                  'semantic_conflicts': after['people'][banker]['conflicting_observations']})
    summaries = []
    for method in NAMES:
        for policy in ('before', 'after'):
            rows = [r for r in results if r['method'] == method and r['policy'] == policy]
            summary = {'method': method, 'policy': policy, 'all_frames': summarize(rows),
                       'after_opening_frame': summarize([r for r in rows if r['t'] > 0]),
                       'by_video': {v['video']: summarize([r for r in rows if r['video'] == v['video'] and r['t'] > 0]) for v in labels['videos']}}
            summaries.append(summary)
            print(method, policy, summary['after_opening_frame'])
    write_json(out / 'evaluation.json', {
        'scope': '12 diagnostic human-reviewed frames / 39 boxes; development examples, not independent validation or action accuracy.',
        'primary_metric': 'Role usable for action attribution; uncertain/unresolved association is counted as unknown, even when stored role is known.',
        'comparison': 'Frozen previous anchored policy versus immutable person roles; identical model/track inputs. New role estimation uses whole-clip observations.',
        'labels_sha256': sha256(labels_path), 'summaries': summaries, 'outcomes': results, 'banker_timelines': timelines})


if __name__ == '__main__':
    main()
