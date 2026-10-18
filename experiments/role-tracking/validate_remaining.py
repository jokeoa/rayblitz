"""Structural/provenance validation; deliberately does not claim accuracy."""
import subprocess
from collections import Counter

from common import ROOT, read_json, sha256, write_json

OUT = ROOT / 'runs/remaining-videos'


def main():
    selection = read_json(OUT / 'selection.json')
    excluded = {x['sha256'] for x in selection['excluded']}
    assert len(selection['videos']) == 37
    assert len({v['sha256'] for v in selection['videos']}) == 37
    assert not ({v['sha256'] for v in selection['videos']} & excluded)
    results = []
    for item in selection['videos']:
        video = item['id']; directory = OUT / video
        tracks = read_json(directory / 'person_tracks.json')
        action = read_json(directory / 'action_result.json')
        assert sha256(ROOT / 'data' / f'{video}.mov') == item['sha256'] == tracks['source_sha256'] == action['source_sha256']
        assert tracks['reference_labels_sha256'] == selection['reference_labels_sha256']
        assert tracks['detections_sha256'] == sha256(directory / 'detections.json')
        assert action['tracks_sha256'] == sha256(directory / 'person_tracks.json')
        assert len(tracks['rows']) == len(read_json(directory / 'detections.json')['rows'])
        for name, expected in tracks['code_sha256'].items(): assert sha256(ROOT / name) == expected
        links = Counter()
        for i, row in enumerate(tracks['rows']):
            assert row['frame'] == i
            pids = []
            for tr in row['tracks']:
                assert 'role' not in tr
                pid = tr['person_id']
                if pid is not None:
                    assert pid in tracks['people']
                    assert tracks['people'][pid]['initialized_at'] <= row['t']
                    pids.append(pid)
                assert tr['association']['usable_for_actions'] == (pid is not None and tr['association']['confidence'] == 'supported')
                links[tr['association']['confidence']] += 1
            assert len(pids) == len(set(pids))
        assert action['status'] == 'done', (video, action.get('error'))
        assert action['windows_completed'] == action['windows_expected']
        rendered_frames = int(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                 '-show_entries', 'stream=nb_frames', '-of', 'csv=p=0', str(directory / 'tracked.mp4')]).strip())
        assert rendered_frames == len(tracks['rows'])
        results.append({'video': video, 'frames': rendered_frames, 'windows': action['windows_completed'],
                        'people_with_assigned_role': len(tracks['people']), 'links': dict(links),
                        'action_candidates': len(action['violations'])})
    write_json(OUT / 'validation.json', {'passed': True, 'videos': results,
                                        'checks': ['37 unique non-excluded source hashes', 'role/track provenance',
                                                   'immutable person roles and causal assignment', 'unique person links',
                                                   'every action window completed', 'all output video frames present'],
                                        'not_measured': ['identity accuracy', 'role accuracy', 'action accuracy', 'clothing-change robustness']})
    print('VALIDATED: all 37 videos, all frames and action windows; accuracy not measured')


if __name__ == '__main__': main()
