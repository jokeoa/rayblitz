"""Read-only smoke checks, apart from creating and closing a reviewer session."""
import json
import os
from collections import Counter
from pathlib import Path

import httpx

base = 'https://cashguard.goigaming.tech'
report = {'url': base}
with httpx.Client(base_url=base, timeout=45) as client:
    assert client.get('/login').status_code == 200
    for path in ['/api/review/jobs', '/api/review/jobs/75ea149b/video',
                 '/api/review/jobs/75ea149b/observations', '/api/review/jobs/75ea149b/review']:
        assert client.get(path).status_code == 401, path
    login = client.post('/api/review/session', headers={'Origin': base},
                        json={'api_key': os.environ['API_KEY']})
    assert login.status_code == 200, login.text
    cookie = login.headers['set-cookie'].lower()
    assert all(flag in cookie for flag in ['httponly', 'secure', 'samesite=strict'])
    history = client.get('/api/review/jobs')
    history.raise_for_status()
    items = history.json()['items']
    assert len(items) == 42
    assert all(item['playbackReady'] for item in items)
    report['videos'] = len(items)
    report['states'] = dict(Counter(item['status'] for item in items))
    observations = client.get('/api/review/jobs/75ea149b/observations')
    observations.raise_for_status()
    evidence = observations.json()
    assert evidence['people']['rows'] and evidence['objects']['rows']
    video = client.get('/api/review/jobs/75ea149b/video', headers={'Range': 'bytes=0-1023'})
    assert video.status_code == 206 and len(video.content) == 1024
    assert video.headers['content-range'].startswith('bytes 0-1023/')
    assert client.get('/api/review/jobs/75ea149b/review').json() == {'reviewed': False, 'notes': ''}
    result = client.get('/api/review/jobs/75ea149b')
    result.raise_for_status()
    assert result.json()['status'] == 'done'
    report['https'] = 'verified'
    report['authentication'] = 'protected endpoints; secure HttpOnly SameSite session'
    report['video_range'] = 206
    report['person_samples'] = len(evidence['people']['rows'])
    report['object_samples'] = len(evidence['objects']['rows'])
    assert client.delete('/api/review/session', headers={'Origin': base}).status_code == 204
    assert client.get('/api/review/jobs').status_code == 401
Path('/home/ubuntu/cashguard-live/public-verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
