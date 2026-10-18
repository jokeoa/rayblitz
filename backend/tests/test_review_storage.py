import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import config, jobs
from app.main import app


class ReviewStorage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = patch.object(config, 'RUNS_DIR', Path(self.temp.name))
        self.config.start()
        jobs._jobs.clear()
        self.directory = jobs.job_dir('abcdef01')
        self.directory.mkdir(parents=True)
        self.job = {'job_id': 'abcdef01', 'filename': 'clip.mov', 'size_bytes': 12,
                    'created': 1, 'queued': True, 'status': 'processing', 'stage': 0, 'progress': 0}
        jobs._jobs['abcdef01'] = self.job
        jobs.save(self.job)
        self.client = TestClient(app, headers={'X-API-Key': config.API_KEY})

    def tearDown(self):
        self.client.close()
        jobs._jobs.clear()
        self.config.stop()
        self.temp.cleanup()

    def test_durable_history_playback_and_range(self):
        jobs._jobs.clear()
        item = self.client.get('/api/v1/jobs').json()['items'][0]
        self.assertEqual(item['fileName'], 'clip.mov')
        self.assertFalse(item['playbackReady'])
        self.assertEqual(self.client.get('/api/v1/jobs/abcdef01/video').status_code, 409)
        (self.directory / 'playback.mp4').write_bytes(b'0123456789')
        self.assertTrue(self.client.get('/api/v1/jobs').json()['items'][0]['playbackReady'])
        response = self.client.get('/api/v1/jobs/abcdef01/video', headers={'Range': 'bytes=2-4'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b'234')
        self.assertEqual(response.headers['content-range'], 'bytes 2-4/10')

    def test_notes_persist_separately_and_require_auth(self):
        path = '/api/v1/jobs/abcdef01/review'
        note = {'reviewed': True, 'notes': 'Проверено вручную: отражение.'}
        self.assertEqual(self.client.put(path, json=note).status_code, 200)
        jobs._jobs.clear()
        self.assertEqual(self.client.get(path).json(), note)
        saved = json.loads((self.directory / 'result.json').read_text())
        self.assertNotIn('notes', saved)
        for suffix in ('', '/video', '/observations', '/review'):
            self.assertEqual(self.client.get('/api/v1/jobs/abcdef01' + suffix,
                                            headers={'X-API-Key': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.put(path, json=note, headers={'X-API-Key': 'wrong'}).status_code, 401)

    def test_recover_only_unfinished_jobs(self):
        jobs._jobs.clear()
        with patch.object(jobs, 'schedule') as schedule:
            jobs.recover()
            schedule.assert_called_once_with('abcdef01')
        self.job.update(status='done', verdict='no_violation', violations=[])
        jobs.save(self.job)
        with patch.object(jobs, 'schedule') as schedule:
            jobs.recover()
            schedule.assert_not_called()


if __name__ == '__main__':
    unittest.main()
