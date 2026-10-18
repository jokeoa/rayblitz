"""Every native source frame in [0, 2): no temporal subsampling for initialization."""
from collections import Counter
import json
import subprocess

import cv2
import numpy as np

from common import config
from reflection_filter import iou
from safe_side_policy import POLICY, SafeSideAssociator


def native_frames(path, seconds):
    meta = json.loads(subprocess.check_output([
        'ffprobe','-v','error','-select_streams','v:0','-read_intervals',f'0%+{seconds+.5}',
        '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
    timestamps = [float(f['best_effort_timestamp_time']) for f in meta['frames']]
    if not timestamps: raise ValueError('No source frames')
    origin = timestamps[0]
    times = [t-origin for t in timestamps if 0 <= t-origin < seconds-1e-7]
    if any(b<=a for a,b in zip(times,times[1:])): raise ValueError('Non-monotonic frame timestamps')
    cap = cv2.VideoCapture(str(path))
    try:
        for i,t in enumerate(times):
            ok, image = cap.read()
            if not ok: raise ValueError(f'Native decode stopped at {i}/{len(times)}')
            yield i,t,image
    finally: cap.release()


def mapped_track(box, t, baseline_rows):
    # All selected baseline observations are strictly inside the opening window.
    row = min(baseline_rows, key=lambda r:abs(r['t']-t))
    if abs(row['t']-t) > .11: return None
    matches = sorted([(iou(box,tr['box']), tr) for tr in row['tracks']], key=lambda x:x[0], reverse=True)
    if not matches or matches[0][0] < .5: return None
    if len(matches)>1 and matches[0][0]-matches[1][0] < .1: return None
    return matches[0][1]['id']


def opening_consensus(rows):
    counts = Counter(r['track_id'] for r in rows if r['track_id'] is not None)
    ranked = counts.most_common()
    winner = ranked[0][0] if ranked and ranked[0][1]/len(rows) >= POLICY['initial_support'] else None
    return winner, {str(k):v for k,v in counts.items()}


class OpeningDetector:
    def __init__(self):
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
        self.cfg = config()
        self.processor = AutoImageProcessor.from_pretrained(self.cfg['detector'], revision=self.cfg['detector_revision'])
        self.model = AutoModelForObjectDetection.from_pretrained(self.cfg['detector'], revision=self.cfg['detector_revision']).to('cuda').eval()
        self.person_class = next(int(k) for k,v in self.model.config.id2label.items() if v=='person')

    def infer(self, images):
        import torch
        from PIL import Image
        from torchvision.ops import nms
        pil = [Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)) for im in images]
        inputs = self.processor(images=pil,return_tensors='pt').to('cuda')
        with torch.inference_mode(): outputs = self.model(**inputs)
        sizes = torch.tensor([[im.height,im.width] for im in pil],device='cuda')
        predictions = self.processor.post_process_object_detection(outputs,target_sizes=sizes,threshold=self.cfg['detector_score'])
        result = []
        for image,pred in zip(images,predictions):
            mask = pred['labels']==self.person_class
            boxes,scores = pred['boxes'][mask],pred['scores'][mask]
            tracks = []
            for j in nms(boxes,scores,self.cfg['nms_iou']).tolist():
                b = boxes[j].cpu().tolist()
                b[0],b[2] = max(0,b[0]),min(image.shape[1],b[2])
                b[1],b[3] = max(0,b[1]),min(image.shape[0],b[3])
                if b[2]>b[0] and b[3]>b[1]: tracks.append({'id':j,'box':b,'score':float(scores[j])})
            result.append(tracks)
        return result

    def initialize(self, path, baseline, geometry, reid):
        frames = list(native_frames(path,POLICY['initial_window_seconds']))
        selector = SafeSideAssociator(geometry,baseline['info']['width'],baseline['info']['height'])
        baseline_rows = [r for r in baseline['rows'] if r['t'] < POLICY['initial_window_seconds']]
        rows, observations = [], []
        for start in range(0,len(frames),8):
            batch = frames[start:start+8]
            detections = self.infer([f[2] for f in batch])
            for (index,t,image),tracks in zip(batch,detections):
                candidate = selector.candidate(tracks)
                track_id = mapped_track(tracks[candidate]['box'],t,baseline_rows) if candidate is not None else None
                rows.append({'native_frame':index,'t':t,'detections':tracks,'candidate_index':candidate,'track_id':track_id})
                observations.append((track_id,tracks[candidate] if candidate is not None else None,image))
        winner, counts = opening_consensus(rows)
        seed = None
        if winner is not None:
            accepted = [(tr,image) for tid,tr,image in observations if tid==winner]
            indices = np.linspace(0,len(accepted)-1,min(POLICY['gallery_size'],len(accepted)),dtype=int)
            features = [reid.get_features(np.asarray([accepted[i][0]['box']],dtype=np.float32),accepted[i][1])[0].tolist() for i in indices]
            seed = {'track':{**accepted[-1][0],'id':winner},'features':features}
        evidence = {'interval':[0.,POLICY['initial_window_seconds']], 'interval_end_exclusive':True,
                    'native_frames':len(frames),'analyzed_frames':len(rows),'all_native_frames_analyzed':len(frames)==len(rows),
                    'detector_revision':self.cfg['detector_revision'],'native_timestamps':[r['t'] for r in rows],
                    'votes':counts,'minimum_support':POLICY['initial_support'],'selected_track_id':winner,
                    'assignment_available_at':POLICY['initial_window_seconds'],'rows':rows}
        return seed,evidence
