"""Observation labels over immutable banker identities; replayable without inference."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from common import ROOT, read_json, sha256, write_json

BASE = ROOT / 'runs/remaining-videos'


def classify(track, people, active_banker):
    reflection = track['reference_match']['kind'] == 'possible_reflection'
    pid = track['person_id']
    candidate = track['candidate_person_id']
    if pid:
        role, basis = people[pid]['role'], 'person_registry'
    elif candidate or track['association']['reason'] == 'different_identity_not_established':
        role, basis = 'unknown', 'banker_association_unresolved'
    elif active_banker is None:
        role, basis = 'unknown', 'banker_not_initialized'
    else:
        role, basis = 'customer', 'non_banker_default'
    # The reflection flag is an observation property, never a new person/role.
    if reflection and not pid:
        role, basis = 'unknown', 'possible_reflection'
    return {'role': role, 'basis': basis, 'possible_reflection': reflection,
            'human_confirmed': False}


def apply_labels(banker, baseline):
    if banker['source_sha256'] != baseline['source_sha256'] or banker['fps'] != baseline['fps'] or len(banker['rows']) != len(baseline['rows']):
        raise ValueError('Label input does not match banker tracking')
    result = deepcopy(banker)
    counts = Counter()
    for row, source in zip(result['rows'], baseline['rows']):
        if (row['frame'], row['t']) != (source['frame'], source['t']) or len(row['tracks']) != len(source['tracks']):
            raise ValueError('Frame alignment changed')
        for track, original in zip(row['tracks'], source['tracks']):
            if (track['id'], track['box']) != (original['id'], original['box']):
                raise ValueError('Detection alignment changed')
            track['reference_match'] = deepcopy(original['reference_match'])
            label = classify(track, result['people'], row['active_banker_person_id'])
            track['classification'] = label
            if label['possible_reflection']:
                track['association']['usable_for_actions'] = False
            counts['possible_reflection' if label['possible_reflection'] else label['role']] += 1
    result['label_counts'] = dict(counts)
    result['label_code_sha256'] = sha256(Path(__file__))
    result['evaluation_note'] = ('Geometry banker hypothesis; remaining observations are customers by exclusion after banker initialization. '
                                 'Unresolved banker links and possible reflections are not customers. Default customer labels do not establish a person identity or authorize action attribution.')
    return result


def label_video(out, video):
    path = out / video / 'banker_tracks.json'
    baseline_path = BASE / video / 'person_tracks.json'
    banker = read_json(path)
    if banker['baseline_tracks_sha256'] != sha256(baseline_path):
        raise ValueError('Baseline tracking changed')
    result = apply_labels(banker, read_json(baseline_path))
    result['banker_tracks_sha256'] = sha256(path)
    write_json(out / video / 'person_tracks.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, default=ROOT / 'runs/safe-side')
    args = parser.parse_args()
    totals = Counter()
    for item in read_json(BASE / 'selection.json')['videos']:
        totals.update(label_video(args.output_root, item['id'])['label_counts'])
    print(dict(totals))
