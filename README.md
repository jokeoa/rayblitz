# RayBlitz

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?logo=tailwindcss&logoColor=white)
![Local Inference](https://img.shields.io/badge/AI_Inference-Local-475569)

RayBlitz analyzes bank cashier videos for visible signs of possible cash-handling violations. Built for the ForteBank Datathon, it connects detected events to timestamps, evidence frames, and regulatory references so reviewers can inspect the footage and record their findings.

The project includes a video analysis API, local inference pipeline, and web interface. Automated findings support human review; they do not establish that a violation occurred.

## How it works

1. A reviewer uploads a `.mov` recording.
2. The backend saves the video, prepares browser playback, and queues analysis.
3. Person tracking and object detection provide context for the actions visible in the recording.
4. A local vision-language model evaluates video windows against the rule catalog.
5. The service returns possible violations with timestamps, supporting frames, descriptions, and catalog references.
6. The reviewer examines the evidence and saves notes separately from the automated verdict.

Video analysis runs on locally hosted models. The pipeline does not use audio analysis or face recognition.

## Components

| Component | Implementation |
| --- | --- |
| Review interface | React, TanStack Start, Tailwind CSS, shadcn/ui |
| API | Python and FastAPI |
| Video processing | FFmpeg |
| Vision-language inference | Qwen3.5-9B through llama.cpp |
| Person detection and tracking | RT-DETRv2, BoT-SORT, OSNet ReID |
| Object detection | OWLv2 |
| Storage | Filesystem-backed jobs and results; SQLite sessions |

The interface provides video playback, an event timeline, evidence frames, person and object observations, analysis history, and reviewer notes. Uploaded recordings and review data persist on the server.

## Run the demo

The mock mode lets you explore the interface without loading the analysis models. It requires Node.js 22.18 or later.

From the repository root:

```bash
cd app
npm ci
npm run dev:mock
```

Open [localhost:3000](http://localhost:3000) and sign in with `fb-demo-key`.

The repository includes sample recordings for the demo. Mock results are predefined and do not describe the uploaded video.

For a presentation build:

```bash
npm run present:mock
```

## Connect the analysis service

The full pipeline requires a CUDA-capable GPU, Python 3.11 or 3.12, FFmpeg, model weights, and the runtime reference assets.

With the backend running, start the frontend from its directory:

```bash
ANALYSIS_API_URL=http://127.0.0.1:8000/api/v1 npm run dev
```

Sign in with the backend’s configured API key. The frontend stores the key on the server and uses an opaque HttpOnly cookie for browser sessions.

Deployment details are documented in [Production on Brev](docs/production.md).

## API

All `/api/v1` requests require an `X-API-Key` header. Uploads accept one `.mov` file up to 100 MiB.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/analyze` | Submit a recording and receive a job ID |
| GET | `/api/v1/jobs` | List saved jobs |
| GET | `/api/v1/jobs/{job_id}` | Retrieve status and results |
| GET | `/api/v1/jobs/{job_id}/violations` | Retrieve paginated findings |
| GET | `/api/v1/jobs/{job_id}/video` | Play the prepared video |
| GET | `/api/v1/jobs/{job_id}/observations` | Retrieve person and object observations |
| GET / PUT | `/api/v1/jobs/{job_id}/review` | Read or save reviewer notes and review status |
| GET | `/api/v1/health` | Check API and model-service availability |

Jobs return `processing`, `done`, or `failed`. Completed analyses use the verdicts `violation` and `no_violation`.

## Limitations

Detection depends on camera placement, visibility, and scene calibration. For uncalibrated recordings, tabletop detection is unavailable and the result reports that limitation. Small objects, including money, cards, packaging, and stamps, may remain uncertain.

The default active-job limit is 295 seconds, excluding queue waiting and preview preparation. Long recordings may receive incomplete coverage or fail on timeout.

The current combined pipeline has no newly established accuracy or F1 result. Historical measurements of earlier configurations should not be treated as validation of this version.

## Development checks

From the frontend directory:

```bash
npm test
npm run typecheck
npm run build
```

From the repository root, using a Python environment with the backend dependencies:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests
PYTHONPATH=backend python -m unittest discover -s backend/tests/vision
```

Vision tests also require detector dependencies, OpenCV, and FFmpeg.
