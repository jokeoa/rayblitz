import asyncio
import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app import config, jobs, overview, payloads, rules
from app.main import app

records = []


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = patch.object(config, "RUNS_DIR", Path(self.temp.name))
        self.config.start()
        jobs._jobs.clear()
        self.client = TestClient(app)
        self.client.headers["X-API-Key"] = config.API_KEY
        jpeg = (Path(__file__).resolve().parents[2] / "app/mock/frames/frame-1.jpg").read_bytes()
        self.violation = dict(type="Событие", timecode_sec=2.0, description="Видимый признак.",
                              rule=rules.citation(rules.rule_ids()[0]), confidence=.9, support=1,
                              evidence_frames=[dict(timestamp_sec=2.0, image_base64=base64.b64encode(jpeg).decode())])
        self.job = dict(job_id="abcdef01", status="done", stage=1, progress=1, queued=False,
                        overview={"summary": "Обнаружен признак нарушения.", "limitations": []},
                        verdict="violation", violations=[self.violation])
        jobs._jobs[self.job["job_id"]] = self.job
        self.path = "/api/v1/jobs/abcdef01"

    def tearDown(self):
        self.client.close()
        self.config.stop()
        self.temp.cleanup()

    def record(self, response, schema, status=200):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        records.append({"schema": schema, "body": response.json()})
        return response.json()

    def test_job_states_and_storage(self):
        for state in ("processing", "failed", "done"):
            self.job["status"] = state
            self.job["progress"] = .4
            self.job["error"] = {"code": "ANALYSIS_FAILED", "message": "Ошибка анализа."}
            for stage in (0, 1):
                self.job["stage"] = stage
                for view, schema in (("ui", "JobResponseSchema"), ("jury", "JuryJobResponseSchema")):
                    self.record(self.client.get(f"{self.path}?view={view}"), schema)
        self.job.update(status="processing", stage=0, queued=True, progress=0)
        self.record(self.client.get(f"{self.path}?view=ui"), "JobResponseSchema")
        self.job.update(status="done", queued=False, verdict="no_violation", violations=[])
        directory = jobs.job_dir("abcdef01")
        directory.mkdir(parents=True)
        (directory / "result.json").write_text(json.dumps(self.job))
        jobs._jobs.clear()
        self.record(self.client.get(f"{self.path}?view=ui"), "JobResponseSchema")
        self.record(self.client.get(self.path), "JuryJobResponseSchema")

    def test_pages_frames_and_errors(self):
        self.job["violations"] = [copy.deepcopy(self.violation) for _ in range(3)]
        first = self.record(self.client.get(self.path + "/violations?page_size=2"), "ViolationsPageSchema")
        second = self.record(self.client.get(self.path + "/violations?page_size=2&page=2"), "ViolationsPageSchema")
        self.assertTrue(first["items"][-1]["id"] < second["items"][0]["id"])
        self.record(self.client.get(self.path + "/violations?page=9"), "ViolationsPageSchema")
        frame = self.client.get(self.path + "/violations/v000000/frames/f0")
        self.assertEqual(frame.headers["content-type"], "image/jpeg")
        self.assertEqual(frame.content, base64.b64decode(self.violation["evidence_frames"][0]["image_base64"]))
        for suffix, status in (("?view=bad", 400), ("?view=ui&view=jury", 400),
                               ("/violations?page=0", 400), ("/violations?page_size=101", 400),
                               ("/violations?page=1&page=2", 400), ("/violations?page=1.2", 400),
                               ("/violations?unknown=1", 400), ("/violations/v000000/frames/f9", 404)):
            self.record(self.client.get(self.path + suffix), "ApiErrorResponseSchema", status)
        self.job["status"] = "processing"
        self.record(self.client.get(self.path + "/violations"), "ApiErrorResponseSchema", 409)
        self.record(self.client.get("/api/v1/jobs/ffffffff"), "ApiErrorResponseSchema", 404)
        self.record(self.client.get(self.path, headers={"X-API-Key": "wrong"}), "ApiErrorResponseSchema", 401)

    def test_upload(self):
        with patch("app.main.probe", return_value={"duration": 5}), patch.object(jobs, "create", return_value="abcdef01"):
            self.record(self.client.post("/api/v1/analyze", files={"file": ("video.mov", b"video")}), "AnalyzeAcceptedSchema", 202)
        for file, status in ((("video.txt", b"x"), 415), (("video.mov", b""), 422)):
            self.record(self.client.post("/api/v1/analyze", files={"file": file}), "ApiErrorResponseSchema", status)
        with patch("app.main.MAX_BYTES", 2):
            self.record(self.client.post("/api/v1/analyze", files={"file": ("video.mov", b"123")}), "ApiErrorResponseSchema", 413)
        with patch("app.main.probe", side_effect=ValueError):
            self.record(self.client.post("/api/v1/analyze", files={"file": ("video.mov", b"x")}), "ApiErrorResponseSchema", 422)
        self.record(self.client.post("/api/v1/analyze"), "ApiErrorResponseSchema", 415)

    def test_real_video_upload_and_auth(self):
        sample = Path(__file__).resolve().parents[2] / "app/mock/samples/kassa-clean.mov"
        with sample.open("rb") as video, patch.object(jobs, "create", return_value="abcdef01"):
            self.record(self.client.post("/api/v1/analyze", files={"file": ("sample.mov", video)}),
                        "AnalyzeAcceptedSchema", 202)
        self.record(self.client.post("/api/v1/analyze", files={"file": ("bad.mov", b"not a video")}),
                    "ApiErrorResponseSchema", 422)
        self.record(self.client.post("/api/v1/analyze", files=[("file", ("a.mov", b"x")), ("file", ("b.mov", b"y"))]),
                    "ApiErrorResponseSchema", 400)
        self.record(self.client.post("/api/v1/analyze", content=b"not multipart", headers={"X-API-Key": "wrong"}),
                    "ApiErrorResponseSchema", 401)

    def test_overview_generation(self):
        async def run():
            for text in ("Обнаружено событие.", " "):
                response = httpx.Response(200, request=httpx.Request("POST", "http://model/chat/completions"),
                                         json={"choices": [{"message": {"content": text}}]})
                with patch("app.overview.httpx.AsyncClient.post", AsyncMock(return_value=response)) as post:
                    if text.strip():
                        result = await overview.generate(self.job)
                        self.assertEqual(result["summary"], text)
                        request = post.call_args.kwargs["json"]
                        self.assertNotIn("image_base64", request["messages"][1]["content"])
                    else:
                        with self.assertRaises(ValueError):
                            await overview.generate(self.job)
        asyncio.run(run())

    def test_health(self):
        for healthy in (True, False):
            mock = AsyncMock(return_value=httpx.Response(200, request=httpx.Request("GET", "http://model/health")))
            if not healthy:
                mock.side_effect = httpx.ConnectError("offline")
            with patch("app.main.httpx.AsyncClient.get", mock):
                self.record(self.client.get("/api/v1/health"), "HealthResponseSchema", 200 if healthy else 503)
        self.record(self.client.get("/api/v1/health", headers={"X-API-Key": "wrong"}), "ApiErrorResponseSchema", 401)

    def test_job_execution(self):
        async def run():
            for failure in (None, "pipeline", "overview", "timeout"):
                jobs._sem = None
                result = {"verdict": "violation", "violations": [self.violation]}
                analysis = AsyncMock(return_value=result)
                if failure in {"pipeline", "timeout"}:
                    analysis.side_effect = TimeoutError() if failure == "timeout" else RuntimeError("secret")
                summary = AsyncMock(return_value=self.job["overview"])
                if failure == "overview":
                    summary.side_effect = ValueError("secret")
                with patch.object(jobs.pipeline, "run", analysis), patch.object(overview, "generate", summary):
                    id_ = jobs.create("video.mov", b"x")
                    await asyncio.gather(*jobs._tasks)
                job = jobs.get(id_)
                self.assertEqual(job["status"], "failed" if failure else "done")
                if failure:
                    self.assertNotIn("secret", json.dumps(payloads.job_response(job, "ui")))
                stored = jobs.job_dir(id_) / "result.json"
                self.assertEqual(json.loads(stored.read_text())["status"], job["status"])
                records.append({"schema": "JobResponseSchema", "body": payloads.job_response(job, "ui")})
        asyncio.run(run())


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if os.environ.get("CONTRACT_OUTPUT"):
        Path(os.environ["CONTRACT_OUTPUT"]).write_text(json.dumps(records))
    raise SystemExit(not result.result.wasSuccessful())
