"""Run BoT-SORT and human-reference appearance transfer over the selected videos."""
import time
from pathlib import Path

import numpy as np
import torch
from boxmot import BotSort
from boxmot.reid.core import ReID

from common import ROOT, config, read_json, sampled_frames, sha256, write_json
from reference_policy import POLICY, ReferenceAssociator, unit

OUT = ROOT / 'runs/remaining-videos'


def reference_gallery(model):
    labels = read_json(ROOT / 'role_review_labels.json')
    gallery = []
    by_video = {}
    for frame in labels['frames']:
        by_video.setdefault(frame['video'], {})[frame['frame']] = frame
    for video, targets in by_video.items():
        source = ROOT / 'data' / f'{video}.mov'
        assert all(x['source_sha256'] == sha256(source) for x in targets.values())
        for index, t, image in sampled_frames(source, config()['fps']):
            if index not in targets: continue
            row = targets[index]
            boxes = [b for b in row['boxes'] if b['kind'] in ('person', 'reflection')]
            features = model.get_features(np.asarray([b['box'] for b in boxes], dtype=np.float32), image)
            for b, feature in zip(boxes, features):
                gallery.append({'feature': unit(feature), 'category': b['person_role'] if b['kind'] == 'person' else 'reflection',
                                'reference': {'video': video, 'review_id': row['review_id'], 'frame': index,
                                              'detection_id': b['detection_id'], 'person_id': b['person_id'],
                                              'source_sha256': row['source_sha256']}})
    np.savez_compressed(OUT / 'reference_features.npz', features=np.asarray([x['feature'] for x in gallery]))
    write_json(OUT / 'references.json', [{'category': x['category'], **x['reference']} for x in gallery])
    return gallery


def main():
    cfg = config()
    torch.manual_seed(cfg['seed'])
    torch.set_num_threads(4)
    model = ReID(weights=ROOT / 'weights' / cfg['reid'], device='cuda:0', half=False).model
    gallery = reference_gallery(model)
    selection = read_json(OUT / 'selection.json')
    code_hashes = {p: sha256(ROOT / p) for p in ('reference_track.py', 'reference_policy.py')}
    for item in selection['videos']:
        video = item['id']; path = ROOT / 'data' / f'{video}.mov'; directory = OUT / video
        assert sha256(path) == item['sha256']
        dets = read_json(directory / 'detections.json')
        assert dets['source_sha256'] == item['sha256']
        tracker = BotSort(track_high_thresh=cfg['high_score'], track_low_thresh=cfg['detector_score'],
                          new_track_thresh=cfg['new_track_score'], track_buffer=round(cfg['lost_seconds'] * 30),
                          frame_rate=cfg['fps'], match_thresh=.8, use_cmc=False, use_embeddings=True,
                          reid_model=model, det_thresh=cfg['detector_score'])
        policy = ReferenceAssociator(gallery)
        started = time.perf_counter(); rows = []
        for index, t, image in sampled_frames(path, cfg['fps']):
            raw = np.asarray(dets['rows'][index]['people'], dtype=np.float32).reshape(-1, 6)
            result = tracker.update(raw, image)
            tracks = [{'id': int(r[4]), 'box': [float(v) for v in r[:4]], 'score': float(r[5]), 'det_idx': int(r[7])} for r in result]
            features = model.get_features(np.asarray([x['box'] for x in tracks], dtype=np.float32), image) if tracks else []
            rows.append({'frame': index, 't': t, 'tracks': policy.update(t, tracks, features)})
        if len(rows) != len(dets['rows']): raise ValueError('Incomplete video decode')
        result = {'video': video, 'source_sha256': item['sha256'], 'fps': cfg['fps'], 'info': dets['info'],
                  'policy': POLICY, 'people': policy.people, 'rows': rows,
                  'reference_labels_sha256': sha256(ROOT / 'role_review_labels.json'),
                  'detections_sha256': sha256(directory / 'detections.json'),
                  'reid_weights_sha256': sha256(ROOT / 'weights' / cfg['reid']),
                  'code_sha256': code_hashes,
                  'seconds': time.perf_counter() - started,
                  'role_accuracy': None, 'evaluation_note': 'No human role ground truth for the 37 target videos. Scores are similarities, not probabilities.'}
        write_json(directory / 'person_tracks.json', result)
        print(video, len(rows), {p: v['role'] for p, v in policy.people.items()}, round(result['seconds'], 1), flush=True)
    (OUT / 'tracking.completed').touch()


if __name__ == '__main__': main()
