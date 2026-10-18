"""Render complete before/after videos and an interactive local report."""
import json
import subprocess

import cv2
import numpy as np

from common import ROOT, read_json, sampled_frames
from reflection_render import titled_panel
from render import COLORS, NAMES, label


def static_panel(image, row, people, method):
    h, w = image.shape[:2]
    out = np.full((h + 96, w, 3), 24, dtype=np.uint8)
    out[72:72+h] = image
    label(out, 'AFTER | ' + method, 8, 26, (245, 245, 245), .6)
    label(out, f"t={row['t']:.1f}s | static role / separate link", 8, 53, (200, 200, 200), .43)
    for tr in row['tracks']:
        pid, association = tr['person_id'], tr['association']
        role = people[pid]['role'] if pid is not None else 'unknown'
        color = COLORS[role]
        x0, y0, x1, y1 = map(round, tr['box'])
        cv2.rectangle(out, (x0, y0+72), (x1, y1+72), color, 2)
        title = f"{pid} {role} | ID {tr['id']}" if pid else f"ID {tr['id']} | unlinked"
        label(out, title, x0, y0+68, color, .4)
        link_color = (170, 220, 170) if association['usable_for_actions'] else (30, 190, 255)
        link_text = 'link: ' + association['confidence']
        if not association['usable_for_actions']:
            link_text += ' | HOLD'
        label(out, link_text, x0, y1+72, link_color, .37)
    label(out, 'E = scene person; HOLD = no action attribution', 5, h+90, (210, 210, 210), .38)
    return out


def main():
    out = ROOT / 'runs/static-roles'
    (out / 'frames').mkdir(exist_ok=True)
    labels = read_json(ROOT / 'role_review_labels.json')
    evaluation = read_json(out / 'evaluation.json')
    images, registries = {}, {}
    for vid in ['X-4', 'X-18', 'X-48']:
        selected = {f['frame']: f for f in labels['frames'] if f['video'] == vid}
        data, writers = {}, {}
        info = read_json(ROOT / 'runs' / vid / 'detections.json')['info']
        for method in NAMES:
            before = read_json(out / 'before' / vid / f'{method}.json')
            after = read_json(out / vid / f'{method}.json')
            data[method] = (before, after)
            registries[vid + ':' + method] = list(after['people'].values())
            path = out / vid / f'{method}-comparison.mp4'
            writers[method] = subprocess.Popen([
                'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                '-s', f"{info['width']*2}x{info['height']+96}", '-r', '10', '-i', '-',
                '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)], stdin=subprocess.PIPE)
        try:
            for idx, _, image in sampled_frames(ROOT / 'data' / f'{vid}.mov', 10):
                for method, (before, after) in data.items():
                    name = 'ByteTrack' if method == 'bytetrack' else 'BoT-SORT + ReID'
                    left = titled_panel(image, before['rows'][idx], method, 'BEFORE | ' + name)
                    right = static_panel(image, after['rows'][idx], after['people'], name)
                    combined = np.concatenate([left, right], axis=1)
                    writers[method].stdin.write(combined.tobytes())
                    if idx in selected:
                        f = selected[idx]
                        path = f"frames/{f['review_id']}-{method}.jpg"
                        if not cv2.imwrite(str(out / path), combined):
                            raise RuntimeError('Could not write comparison frame')
                        images[f['review_id'] + ':' + method] = path
        finally:
            for proc in writers.values():
                proc.stdin.close()
        for proc in writers.values():
            if proc.wait() != 0:
                raise RuntimeError('Video render failed')
        print(vid, 'rendered complete comparison videos for both trackers', flush=True)
    data = {'frames': [{k: f[k] for k in ['review_id', 'video', 't']} for f in labels['frames']],
            'images': images, 'summaries': evaluation['summaries'], 'outcomes': evaluation['outcomes'],
            'timelines': evaluation['banker_timelines'], 'registries': registries}
    html = (ROOT / 'static_role_report.html').read_text()
    (out / 'index.html').write_text(html.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')))
    print(out / 'index.html', flush=True)


if __name__ == '__main__':
    main()
