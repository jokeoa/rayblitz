"""Render complete tracked videos and a reviewable report for the 37-video batch."""
import argparse
import base64
import json
import subprocess
from collections import Counter

import cv2
import numpy as np

from common import ROOT, read_json, sampled_frames, sha256, video_info, write_json
from compare_remaining import compare

OUT = ROOT / 'runs/remaining-videos'
COLORS = {'banker': (138, 177, 29), 'customer': (66, 175, 224), 'unknown': (183, 179, 170), 'reflection': (188, 120, 173)}


def render(video, data):
    info = data['info']; width, height = info['width'], info['height']
    target = OUT / video / 'tracked.mp4'
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                             '-s', f'{width}x{height+64}', '-r', str(data['fps']), '-i', '-', '-an',
                             '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                             '-movflags', '+faststart', str(target)], stdin=subprocess.PIPE)
    count = 0
    for index, t, image in sampled_frames(ROOT / 'data' / f'{video}.mov', data['fps']):
        row = data['rows'][index]
        canvas = np.zeros((height + 64, width, 3), np.uint8)
        canvas[:height] = image
        for tr in row['tracks']:
            pid = tr['person_id']; association = tr['association']
            role = data['people'].get(pid, {}).get('role', 'unknown')
            kind = tr['reference_match']['kind']
            color = COLORS['reflection' if kind == 'possible_reflection' else role]
            box = [round(v) for v in tr['box']]
            x0, y0, x1, y1 = box
            cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2)
            label = f'{pid or "T" + str(tr["id"])} {role}'
            if kind == 'possible_reflection': label = f'T{tr["id"]} possible reflection'
            elif association['confidence'] != 'supported': label += ' ?'
            label_y = max(14, y0 - 4)
            cv2.putText(canvas, label, (max(0, x0), label_y), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(canvas, label, (max(0, x0), label_y), cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1, cv2.LINE_AA)
        cv2.putText(canvas, f'{video}  {t:.1f}s  |  Automatic role transfer', (10, height + 23), cv2.FONT_HERSHEY_SIMPLEX, .48, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.putText(canvas, '? = uncertain link; roles remain fixed', (10, height + 47), cv2.FONT_HERSHEY_SIMPLEX, .43, (185, 190, 195), 1, cv2.LINE_AA)
        if index == min(20, len(data['rows']) - 1): cv2.imwrite(str(target.with_name('preview.jpg')), canvas)
        proc.stdin.write(canvas.tobytes()); count += 1
    proc.stdin.close()
    if proc.wait() != 0 or count != len(data['rows']): raise RuntimeError(f'Incomplete render {video}')
    meta = video_info(target)
    if abs(meta['duration'] - count / data['fps']) > .11: raise ValueError(f'Output duration mismatch {video}')
    return {'video': video, 'frames': count, 'duration': meta['duration'], 'sha256': sha256(target)}


def build():
    selection = read_json(OUT / 'selection.json'); summaries = []
    for item in selection['videos']:
        video = item['id']; directory = OUT / video
        path = directory / 'person_tracks.json'
        if not path.exists():
            summaries.append({'video': video, 'status': 'tracking_pending'}); continue
        data = read_json(path)
        counts = Counter(p['role'] for p in data['people'].values())
        links = Counter(tr['association']['confidence'] for r in data['rows'] for tr in r['tracks'])
        bankers = sum(any(t['association']['usable_for_actions'] and data['people'].get(t['person_id'], {}).get('role') == 'banker' for t in r['tracks']) for r in data['rows'])
        action_path = directory / 'action_result.json'
        action = read_json(action_path) if action_path.exists() else {'status': 'pending'}
        events = []
        for i, event in enumerate(action.get('violations', [])):
            images = []
            for j, frame in enumerate(event['evidence_frames']):
                name = f'event-{i}-{j}.jpg'
                (directory / name).write_bytes(base64.b64decode(frame['image_base64']))
                images.append({'time': frame['timestamp_sec'], 'path': f'{video}/{name}'})
            events.append({k: v for k, v in event.items() if k != 'evidence_frames'} | {'images': images})
        summaries.append({'video': video, 'status': action['status'], 'frames': len(data['rows']), 'duration': len(data['rows']) / data['fps'],
                          'people': data['people'], 'counts': dict(counts), 'links': dict(links),
                          'banker_coverage': bankers / len(data['rows']), 'events': events,
                          'windows': [action.get('windows_completed'), action.get('windows_expected')],
                          'action_seconds': action.get('seconds'), 'error': action.get('error'),
                          'rendered': (directory / 'tracked.mp4').exists()})
    comparison = compare()
    payload = {'selection': selection, 'videos': summaries, 'protocol_comparison': comparison,
               'accuracy': None, 'scope': '37 target recordings; human reference labels used for inference, not evaluation'}
    write_json(OUT / 'summary.json', payload)
    html = (ROOT / 'remaining_report.html').read_text()
    (OUT / 'index.html').write_text(html.replace('__DATA__', json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')))
    complete = [v for v in summaries if v['status'] == 'done']
    (OUT / 'README.md').write_text('# Результаты прогона остальных видео\n\n' +
        f'Готово: {len(complete)}/37. Исключены X-4, X-18, X-48 и их точные копии X-47, X-5.\n\n' +
        'Роли перенесены автоматически из пользовательских эталонов; независимой оценки точности нет.\n\n' +
        '| Видео | Покрытие банкира | Кандидаты событий | Окна |\n|---|---:|---:|---:|\n' +
        '\n'.join(f'| {v["video"]} | {v.get("banker_coverage",0):.0%} | {len(v.get("events",[]))} | {v.get("windows",[])} |' for v in summaries) + '\n\nОткройте index.html для полного просмотра.\n')
    print('report', len(complete), '/37 action results', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--render', action='store_true'); args = p.parse_args()
    if args.render:
        validation = []
        for item in read_json(OUT / 'selection.json')['videos']:
            data = read_json(OUT / item['id'] / 'person_tracks.json')
            validation.append(render(item['id'], data))
            print('rendered', item['id'], flush=True)
        write_json(OUT / 'media_validation.json', validation)
    build()
