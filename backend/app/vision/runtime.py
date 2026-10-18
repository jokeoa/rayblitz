"""Native-resolution RT-DETR + BoT-SORT/ReID and tabletop OWLv2 observations."""
from collections import deque
from functools import lru_cache
import io
import math
import threading
import time

import numpy as np
from PIL import Image

from app import config as settings, detector
from app.video import probe, frame_jpeg
from .anchors import resolve_anchor
from .common import ROOT, config, read_json, sampled_frames, sha256, write_json
from .initial_window import OpeningDetector, native_frames
from .object_context import PersonContext, resolve, observation_intervals
from .reference_policy import ReferenceAssociator, reference_match, unit
from .safe_side_policy import SafeSideAssociator, POLICY
from .reflection_filter import iou
from .scene import geometry_for, equipment_for, human_opening

LOCK = threading.Lock()
OBJECT_FPS = 2


@lru_cache
def models():
    import torch
    from boxmot.reid.core import ReID
    torch.set_num_threads(4)
    torch.manual_seed(42)
    opening = OpeningDetector()
    reid = ReID(weights=settings.REID_WEIGHTS, device='cuda:0', half=False).model
    features = np.load(ROOT / 'reference_features.npz')['features']
    references = read_json(ROOT / 'references.json')
    gallery = [{'feature': unit(f), 'category': r['category'], 'reference': r}
               for f, r in zip(features, references)]
    return opening, reid, gallery


def label_tracks(tracks, people, active, gallery, features):
    for tr, feature in zip(tracks, features):
        match = reference_match(unit(feature), gallery)
        tr['reference_match'] = match
        reflection = match['kind'] == 'possible_reflection'
        pid = tr['person_id']
        if pid:
            role, basis = people[pid]['role'], 'person_registry'
        elif tr['candidate_person_id'] or tr['association']['reason'] == 'different_identity_not_established':
            role, basis = 'unknown', 'banker_association_unresolved'
        elif active:
            role, basis = 'customer', 'non_banker_default'
        else:
            role, basis = 'unknown', 'banker_not_initialized'
        if reflection:
            tr['association']['usable_for_actions'] = False
            if not pid:
                role, basis = 'unknown', 'possible_reflection'
        tr['classification'] = {'role': role, 'basis': basis, 'possible_reflection': reflection,
                                'human_confirmed': bool(pid and people[pid].get('human_confirmed_in_this_video'))}
    return tracks


def install_human_seeds(policy, opening, tracks, features):
    """Use only the explicitly reviewed first frame, never later annotations."""
    for box in opening['boxes']:
        if box['kind'] != 'person':
            continue
        matches = sorted([(iou(box['box'], t['box']), i) for i, t in enumerate(tracks)], reverse=True)
        if not matches or matches[0][0] < .5:
            continue
        i = matches[0][1]
        tr, f, pid = tracks[i], unit(features[i]), box['person_id']
        if tr['id'] in policy.track_people or pid in policy.people:
            continue
        policy.people[pid] = {'person_id': pid, 'role': box['person_role'], 'initialized_at': 0.,
                             'role_basis': 'human_opening_frame', 'human_confirmed_in_this_video': True}
        policy.states[pid] = {'last': 0., 'box': tr['box'], 'track_id': tr['id'],
                             'initial': f, 'gallery': deque([f], maxlen=8)}
        policy.track_people[tr['id']] = pid


def run_people(video, info, geometry, digest, progress):
    from boxmot import BotSort
    opening, reid, gallery = models()
    cfg = config()
    fps = cfg['fps']
    tracker = BotSort(track_high_thresh=cfg['high_score'], track_low_thresh=cfg['detector_score'],
        new_track_thresh=cfg['new_track_score'], track_buffer=round(cfg['lost_seconds']*30),
        frame_rate=fps, match_thresh=.8, use_cmc=False, use_embeddings=True,
        reid_model=reid, det_thresh=cfg['detector_score'])
    source = sampled_frames(video, fps)
    raw_rows, feature_rows, opening_images = [], [], []
    total = max(1, math.ceil(info['duration']*fps))
    try:
        batch = []
        for entry in source:
            batch.append(entry)
            if len(batch) < 8 and entry[0]+1 < total:
                continue
            _track_batch(batch, opening, tracker, reid, raw_rows, feature_rows, opening_images)
            progress(min(.85, len(raw_rows)/total*.85))
            batch = []
        if batch:
            _track_batch(batch, opening, tracker, reid, raw_rows, feature_rows, opening_images)
    finally:
        source.close()
    manual = human_opening(digest)
    baseline = {'rows': raw_rows, 'info': info}
    evidence = None
    if manual:
        policy = ReferenceAssociator(gallery)
        if raw_rows:
            install_human_seeds(policy, manual, raw_rows[0]['tracks'], feature_rows[0])
    else:
        if geometry['objects']['desk'] and not geometry['objects']['safe']:
            native = [Image.fromarray(im[:, :, ::-1]) for _, _, im in native_frames(video, 2.)]
            geometry = resolve_anchor(geometry, native, detector._owl_candidates)
        seed, evidence = opening.initialize(video, baseline, geometry, reid) if geometry['objects']['desk'] else (None, None)
        policy = SafeSideAssociator(geometry, info['width'], info['height'], seed)
    rows = []
    for row, features in zip(raw_rows, feature_rows):
        tracks = policy.update(row['t'], row['tracks'], features)
        active = (next((p for p, v in policy.people.items() if v['role'] == 'banker'), None)
                  if manual else policy.active_person_id)
        rows.append({**row, 'tracks': label_tracks(tracks, policy.people, active, gallery, features),
                     'active_banker_person_id': active})
    progress(1.)
    if evidence:
        evidence = {k: v for k, v in evidence.items() if k != 'rows'}
    return {'source_sha256': digest, 'info': info, 'fps': fps, 'rows': rows, 'people': policy.people,
            'geometry': geometry, 'initial_window': evidence,
            'banker_transitions': getattr(policy, 'transitions', []),
            'policy': POLICY, 'role_accuracy': None}


def _track_batch(batch, opening, tracker, reid, rows, feature_rows, opening_images):
    detections = opening.infer([e[2] for e in batch])
    for (i, t, image), found in zip(batch, detections):
        raw = np.asarray([d['box']+[d['score'], 0] for d in found], np.float32).reshape(-1, 6)
        result = tracker.update(raw, image)
        tracks = [{'id': int(r[4]), 'box': r[:4].tolist(), 'score': float(r[5]), 'det_idx': int(r[7])} for r in result]
        features = reid.get_features(np.asarray([tr['box'] for tr in tracks], np.float32), image) if tracks else []
        rows.append({'frame': i, 't': t, 'tracks': tracks})
        feature_rows.append(features)


def run_objects(video, people, progress, directory):
    import torch
    from torchvision.ops import batched_nms
    from boxmot import ByteTrack
    cfg = read_json(ROOT / 'objects.json')
    classes = cfg['classes']
    desk = people['geometry']['objects']['desk']
    if desk is None:
        return {'fps': OBJECT_FPS, 'rows': [], 'intervals': [], 'classes': classes,
                'limitation': 'Область стола не откалибрована; предметы на столе не определялись.'}
    w, h = people['info']['width'], people['info']['height']
    x0, y0, x1, y1 = desk['box']
    cx, cy, side = (x0+x1)/2, (y0+y1)/2, max(x1-x0, y1-y0)*1.2
    crop = [max(0, math.floor(cx-side/2)), max(0, math.floor(cy-side/2)), min(w, math.ceil(cx+side/2)), min(h, math.ceil(cy+side/2))]
    proc, model, device = detector._owl()
    prompts = [c['prompt'] for c in classes]
    trackers = {c['id']: ByteTrack(min_conf=.05, track_thresh=.15, match_thresh=.8, track_buffer=15, frame_rate=OBJECT_FPS) for c in classes}
    context, anchors = PersonContext(people), equipment_for(people['source_sha256'])
    rows = []
    crop_dir = directory / 'desk_frames'
    crop_dir.mkdir(exist_ok=True)
    total = max(1, math.ceil(people['info']['duration']*OBJECT_FPS))
    for i, t, bgr in sampled_frames(video, OBJECT_FPS):
        image = Image.fromarray(bgr[:, :, ::-1]).crop(crop)
        image.save(crop_dir / f'{i:05d}.jpg', quality=92)
        inputs = proc(text=[prompts], images=image, return_tensors='pt').to(device)
        with torch.inference_mode():
            result = model(**inputs)
        output = proc.post_process_grounded_object_detection(result, threshold=.05,
            target_sizes=torch.tensor([[image.height, image.width]], device=device), text_labels=[prompts])[0]
        raw = []
        for box, score, label in zip(output['boxes'].tolist(), output['scores'].tolist(), output['text_labels']):
            n = prompts.index(label)
            box = [max(0, min(w if j%2 == 0 else h, v+crop[j%2])) for j, v in enumerate(box)]
            if box[2] <= box[0] or box[3] <= box[1] or classes[n]['id'] == 'safe':
                continue
            if not x0 <= (box[0]+box[2])/2 <= x1 or not y0 <= box[3] <= y1:
                continue
            raw.append({'box': box, 'score': score, 'class': classes[n]['id'], 'class_index': n})
        if raw:
            keep = batched_nms(torch.tensor([p['box'] for p in raw]), torch.tensor([p['score'] for p in raw]),
                               torch.tensor([p['class_index'] for p in raw]), .5).tolist()
            raw = [raw[n] for n in keep]
        kept, excluded = resolve(raw, context.at(t), anchors, t)
        current = []
        for cls, tracker in trackers.items():
            candidates = [p for p in kept if p['class'] == cls]
            dets = np.asarray([p['box']+[p['score'], 0] for p in candidates], np.float32).reshape(-1, 6)
            for track in tracker.update(dets, bgr):
                source = candidates[int(track[7])]
                current.append({**source, 'id': f'{cls}-{int(track[4])}', 'box': track[:4].tolist(),
                                'semantic_status': 'uncertain' if cls in {'cash', 'packaging', 'card', 'stamp'} else 'candidate'})
        rows.append({'frame': i, 't': t, 'tracks': current, 'raw': raw, 'excluded': excluded})
        progress(min(1., (i+1)/total))
    intervals = observation_intervals(rows, OBJECT_FPS)
    for item in intervals:
        item['intervals'] = [[a, min(b, people['info']['duration'])] for a,b in item['intervals']]
        item['observed_seconds'] = round(sum(b-a for a,b in item['intervals']), 3)
    return {'fps': OBJECT_FPS, 'rows': rows, 'classes': classes, 'intervals': intervals, 'crop': crop,
            'limitation': 'Рамки — кандидаты. Деньги, карточки и упаковка различаются ненадёжно. Интервалы показывают только наблюдаемые отсчёты; принадлежность зоне не доказывает контакт со столом.'}


def analyze(video, directory, progress):
    with LOCK:
        tick = time.monotonic()
        info, digest = probe(video), sha256(video)
        geometry = geometry_for(digest, info)
        people = run_people(video, info, geometry, digest, lambda p: progress(p*.65))
        write_json(directory / 'people.json', people)
        objects = run_objects(video, people, lambda p: progress(.65+p*.35), directory)
        write_json(directory / 'objects.json', objects)
        write_json(directory / 'vision.json', {'seconds': time.monotonic()-tick, 'source_sha256': digest})
        return people, objects
