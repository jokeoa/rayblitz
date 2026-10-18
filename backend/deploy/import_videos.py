"""Idempotently submit a verified manifest to the local production API."""
import hashlib
import json
import os
from pathlib import Path

import httpx

root = Path('/home/ubuntu/cashguard-live')
manifest = json.loads((root / 'source-manifest.json').read_text())
receipts = []
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',
                  headers={'X-API-Key': os.environ['API_KEY']}, timeout=120) as client:
    response = client.get('/jobs')
    response.raise_for_status()
    existing = {item['fileName']: item for item in response.json()['items']}
    for source in manifest:
        video = root / 'imports' / source['filename']
        with video.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == source['sha256']
        if source['filename'] in existing:
            job_id = existing[source['filename']]['jobId']
            with (root / 'runs/jobs' / job_id / 'input.mov').open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == source['sha256']
        else:
            with video.open('rb') as stream:
                response = client.post('/analyze', files={'file': (video.name, stream, 'video/quicktime')})
            response.raise_for_status()
            job_id = response.json()['job_id']
        receipts.append({'filename': source['filename'], 'sha256': source['sha256'], 'job_id': job_id})
        (root / 'import-receipts.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2))
        print(f'{len(receipts)}/{len(manifest)} {source["filename"]} {job_id}', flush=True)
    response = client.get('/jobs')
    response.raise_for_status()
    assert {item['filename'] for item in receipts} <= {item['fileName'] for item in response.json()['items']}
print('All videos are registered in the production queue.', flush=True)
