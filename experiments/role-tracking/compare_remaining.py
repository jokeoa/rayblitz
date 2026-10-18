"""Post-inference comparison with the existing, incomplete event protocol."""
from common import ROOT, read_json, sha256, write_json

OUT = ROOT / 'runs/remaining-videos'


def compare():
    protocol_path = OUT / 'evaluation_protocol.json'
    if not protocol_path.exists(): return None
    protocol = read_json(protocol_path)
    details = []
    selected = {x['id'] for x in read_json(OUT / 'selection.json')['videos']}
    for video, annotation in protocol['videos'].items():
        if video not in selected or annotation['status'] not in ('confirmed', 'corrected'): continue
        path = OUT / video / 'action_result.json'
        if not path.exists(): continue
        result = read_json(path)
        if result['status'] != 'done': continue
        events = []
        for expected in annotation['events']:
            candidates = [p for p in result['violations'] if p['rule']['code'] == expected['code']]
            error = min((abs(p['timecode_sec'] - expected['t']) for p in candidates), default=None) if expected['t'] is not None else None
            events.append({**expected, 'type_found': bool(candidates), 'nearest_time_error_seconds': error,
                           'type_and_time_within_2s': error is not None and error <= 2})
        details.append({'video': video, 'annotation_status': annotation['status'], 'expected': events,
                        'predicted': [{'code': p['rule']['code'], 't': p['timecode_sec']} for p in result['violations']]})
    expected = [e for d in details for e in d['expected']]
    value = {'source': protocol['source'], 'source_sha256': sha256(protocol_path),
             'scope': 'Incomplete existing event protocol; development set, not independent test. Hypotheses excluded. Missing annotations are not negatives.',
             'videos_compared': len(details), 'events_expected': len(expected),
             'type_found': sum(e['type_found'] for e in expected),
             'type_and_time_within_2s': sum(e['type_and_time_within_2s'] for e in expected),
             'details': details}
    write_json(OUT / 'protocol_comparison.json', value)
    return value


if __name__ == '__main__': print(compare())
