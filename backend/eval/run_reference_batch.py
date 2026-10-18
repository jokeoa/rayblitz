"""Run the complete local action pipeline with causal reference-initialized roles."""
import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, role_context
from app.pipeline import run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


async def main(root):
    out = root / 'runs/remaining-videos'
    selection = json.loads((out / 'selection.json').read_text())
    code = {str(p.relative_to(config.ROOT)): digest(p) for p in (config.ROOT / 'app').rglob('*.py')}
    config_snapshot = {k: getattr(config, k) for k in ('SAMPLE_FPS', 'FRAME_WIDTH', 'WINDOW_SEC', 'STRIDE_SEC', 'SCORE_NORM', 'VLM_CONCURRENCY', 'COMPOSITE_RULES')}
    save(out / 'action_run.json', {'status': 'running', 'started_at': time.time(), 'code_sha256': code,
                                  'config': config_snapshot, 'thresholds_sha256': digest(config.THRESHOLDS_PATH),
                                  'selection_sha256': digest(out / 'selection.json'), 'deadline': None,
                                  'note': 'Offline complete scan, no time-budget window skipping; thresholds not recalibrated for role overlays.'})
    summaries = []
    tracking_code = {name: digest(root / name) for name in ('reference_track.py', 'reference_policy.py')}
    for item in selection['videos']:
        video = item['id']; directory = out / video; tracks_path = directory / 'person_tracks.json'
        source = root / 'data' / f'{video}.mov'
        # The producer publishes one complete video at a time. Ignore an older
        # attempt until its current-code replacement is fully written.
        waiting = time.monotonic()
        while True:
            try:
                tracks = json.loads(tracks_path.read_text())
                if tracks['code_sha256'] == tracking_code: break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if time.monotonic() - waiting > 1800:
                raise TimeoutError(f'{video}: current tracking output was not published')
            await asyncio.sleep(2)
        assert digest(source) == item['sha256'] == tracks['source_sha256']
        assert all(row['frame'] == i for i, row in enumerate(tracks['rows']))
        target = directory / 'action_result.json'
        if target.exists():
            previous = json.loads(target.read_text())
            if previous['tracks_sha256'] != digest(tracks_path) or previous['code_sha256'] != code:
                raise ValueError(f'{video}: previous action result has different inputs/code')
            if previous['status'] == 'done':
                summaries.append(previous); continue
        work = directory / 'actions'; work.mkdir(exist_ok=True)
        started = time.perf_counter()
        token = role_context.current.set(tracks)
        meta = {'video': video, 'source_sha256': item['sha256'], 'tracks_sha256': digest(tracks_path), 'code_sha256': code}
        try:
            result = await run(source, work, progress=lambda p: print(f'{video} windows {p:.0%}', flush=True))
            probs = json.loads((work / 'raw_probs.json').read_text())
            n = len(list((work / 'frames').glob('*.jpg')))
            size, step = round(config.WINDOW_SEC * config.SAMPLE_FPS), round(config.STRIDE_SEC * config.SAMPLE_FPS)
            expected = max(1, math.ceil(max(0, n - size) / step) + 1)
            if len(probs) != expected: raise ValueError(f'Incomplete action scan: {len(probs)} / {expected}')
            known = sum(any(tr['association']['usable_for_actions'] and tracks['people'].get(tr['person_id'], {}).get('role') == 'banker' for tr in r['tracks']) for r in tracks['rows'])
            result = {**meta, **result, 'status': 'done', 'seconds': time.perf_counter() - started,
                      'windows_completed': len(probs), 'windows_expected': expected,
                      'banker_supported_frame_share': known / len(tracks['rows']),
                      'requires_review': True,
                      'interpretation': 'Automatic findings; no independent target-video identity/action validation. No finding is not proof of compliance.'}
        except Exception as exc:
            result = {**meta, 'status': 'error', 'seconds': time.perf_counter() - started,
                      'error': str(exc), 'traceback': traceback.format_exc()}
        finally:
            role_context.current.reset(token)
        save(target, result)
        summaries.append({k: v for k, v in result.items() if k not in ('code_sha256', 'violations')})
        save(out / 'action_progress.json', summaries)
        print(video, result['status'], round(result['seconds'], 1), result.get('verdict'), flush=True)
    save(out / 'action_completion.json', {'videos': len(summaries), 'done': sum(x['status'] == 'done' for x in summaries),
                                          'errors': [x['video'] for x in summaries if x['status'] != 'done']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', type=Path, required=True)
    asyncio.run(main(parser.parse_args().experiment))
