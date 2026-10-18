"""Validate saved provenance, identity invariants, and complete encoded videos."""
import subprocess
import json

from common import ROOT, read_json, sha256, write_json
from render import NAMES


def main():
    out = ROOT / 'runs/static-roles'
    checks = []
    for vid in ['X-4', 'X-18', 'X-48']:
        count = len(read_json(ROOT / 'runs' / vid / 'detections.json')['rows'])
        for method in NAMES:
            before = read_json(out / 'before' / vid / f'{method}.json')
            after = read_json(out / vid / f'{method}.json')
            assert before['policy_source_sha256'] == sha256(out / 'before/source/anchored_role_policy.py')
            assert before['inputs'] == after['inputs']
            assert all(sha256(ROOT / path) == digest for path, digest in after['inputs'].items())
            assert all(sha256(ROOT / path) == digest for path, digest in after['code_sha256'].items())
            assert after['human_labels_used_for_inference'] is False
            assert len(after['rows']) == len(before['rows']) == count
            for row in after['rows']:
                linked = []
                for tr in row['tracks']:
                    assert 'role' not in tr and 'role_reason' not in tr
                    pid = tr['person_id']
                    assert pid is None or pid in after['people']
                    assert tr['candidate_person_id'] is None or tr['candidate_person_id'] in after['people']
                    assert tr['association']['usable_for_actions'] == (tr['association']['confidence'] == 'supported')
                    if pid is not None:
                        linked.append(pid)
                        assert after['people'][pid]['track_id'] == tr['id']
                assert len(linked) == len(set(linked)), 'Two boxes linked to one person in the same frame'
            movie = out / vid / f'{method}-comparison.mp4'
            stream = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,avg_frame_rate:format=duration', '-of', 'json', str(movie)]))
            assert int(stream['streams'][0]['nb_read_frames']) == count
            assert stream['streams'][0]['avg_frame_rate'] == '10/1'
            assert abs(float(stream['format']['duration']) - count / 10) < .02
            checks.append({'video': vid, 'method': method, 'frames': count,
                           'provenance': 'pass', 'person_role_separation': 'pass',
                           'unique_person_links': 'pass', 'full_video_frames': 'pass',
                           'video_sha256': sha256(movie)})
    write_json(out / 'validation.json', {'status': 'pass', 'checks': checks,
                                       'limitations': 'Structural and media validation; not identity accuracy or a clothing-change benchmark.'})
    print('PASS: 6 outputs, source hashes, immutable role schema, association invariants, full video frame counts')


if __name__ == '__main__':
    main()
