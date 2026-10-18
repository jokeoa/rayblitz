"""Reuse identical detector/BoT-SORT tracks; change only role initialization."""
import argparse
import time
import shutil
from pathlib import Path

import numpy as np
import torch
from boxmot.reid.core import ReID

from common import ROOT, config, read_json, sampled_frames, sha256, write_json
from safe_side_policy import POLICY, SafeSideAssociator
from scene_references import reference_geometry
from initial_window import OpeningDetector
from safe_side_labels import label_video
from scene_anchor_search import search_missing_anchor

BASE = ROOT / 'runs/remaining-videos'
OUT = ROOT / 'runs/safe-side'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, default=OUT)
    parser.add_argument('--backend', type=Path, default=ROOT.parents[1] / 'backend')
    args = parser.parse_args()
    out = args.output_root
    cfg = config(); torch.set_num_threads(4); torch.manual_seed(cfg['seed'])
    model = ReID(weights=ROOT / 'weights' / cfg['reid'], device='cuda:0', half=False).model
    detector = OpeningDetector()
    code = {name: sha256(ROOT / name) for name in ('safe_side_track.py', 'safe_side_policy.py', 'reference_policy.py', 'scene_references.py', 'scene_anchor_search.py', 'safe_side_labels.py', 'initial_window.py', 'common.py')}
    snapshot = out / 'source_snapshot'; snapshot.mkdir(parents=True, exist_ok=True)
    for name in code: shutil.copy2(ROOT / name, snapshot / name)
    summaries = []
    for item in read_json(BASE / 'selection.json')['videos']:
        video = item['id']; old = read_json(BASE / video / 'person_tracks.json')
        assert sha256(ROOT / 'data' / f'{video}.mov') == old['source_sha256']
        geometry = reference_geometry(video, old['source_sha256'], old['info']['width'], old['info']['height'])
        geometry = search_missing_anchor(geometry, ROOT / 'data' / f'{video}.mov', args.backend)
        if 'anchor_search' in geometry:
            geometry['anchor_search']['detector_code_sha256'] = sha256(args.backend / 'app/detector.py')
        started = time.perf_counter()
        seed, opening = detector.initialize(ROOT / 'data' / f'{video}.mov', old, geometry, model)
        write_json(out / video / 'initial_window.json', opening)
        policy = SafeSideAssociator(geometry, old['info']['width'], old['info']['height'], seed)
        rows = []
        for i, t, image in sampled_frames(ROOT / 'data' / f'{video}.mov', old['fps']):
            tracks = [{k: tr[k] for k in ('id', 'box', 'score', 'det_idx')} for tr in old['rows'][i]['tracks']]
            features = model.get_features(np.asarray([tr['box'] for tr in tracks], dtype=np.float32), image) if tracks else []
            rows.append({'frame': i, 't': t, 'tracks': policy.update(t, tracks, features), 'active_banker_person_id': policy.active_person_id})
        assert len(rows) == len(old['rows'])
        result = {k: old[k] for k in ('video', 'source_sha256', 'fps', 'info', 'reid_weights_sha256')}
        result.update(people=policy.people, rows=rows, policy=POLICY, geometry=geometry, axis=policy.axis,
                      initial_window={k:v for k,v in opening.items() if k != 'rows'},
                      banker_transitions=policy.transitions, role_accuracy=None, code_sha256=code, baseline_tracks_sha256=sha256(BASE / video / 'person_tracks.json'),
                      seconds=time.perf_counter()-started,
                      evaluation_note='Banker identity stage. Observation labels and reflection veto are applied by safe_side_labels.py.')
        write_json(out / video / 'banker_tracks.json', result)
        labeled = label_video(out, video)
        coverage = sum(any(tr['is_active_banker'] and tr['association']['usable_for_actions'] for tr in r['tracks']) for r in labeled['rows'])/len(rows)
        summaries.append({'video': video, 'coverage': coverage, 'people': policy.people})
        print(video, round(coverage, 3), policy.people, flush=True)
    write_json(out / 'tracking_summary.json', summaries)


if __name__ == '__main__': main()
