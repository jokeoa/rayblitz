# Production on Brev

Public URL: <https://cashguard.goigaming.tech>.

The application runs on `flaky-lime-lemur` in `/home/ubuntu/cashguard-live`.
The review frontend listens on `127.0.0.1:3000`, the analysis API on
`127.0.0.1:8000`, and the existing GPU model service on `127.0.0.1:8081`.
Cloudflare Tunnel publishes only the frontend. Browser sessions are opaque,
HttpOnly, Secure on HTTPS, and stored in SQLite; the analysis key remains on
the server. Sessions survive frontend restarts and expire after eight hours.

## Services and storage

- `cashguard-api.service`: FastAPI, durable job queue, one GPU job at a time.
- `cashguard-web.service`: TanStack Start on Node 24.22.0 with srvx 1.0.5.
- `cashguard-tunnel.service`: official cloudflared 2026.10.1, tunnel
  `45b92447-84d3-47cf-90d1-f13e09271113`.
- `cashguard-remaining-llama`: existing Docker model service, Qwen3.5-9B.

`runs/jobs/<id>` contains the original upload, browser-playable MP4,
`result.json`, `people.json`, `objects.json`, `vision.json`, and reviewer
`review.json`. Writes are atomic. Original videos and results are retained;
there is no browser-local history cap. Interrupted jobs are recovered on API
startup. Preview generation is independently limited to two workers, so queued
videos become playable before GPU analysis starts.

`secrets/service.env`, `secrets/tunnel-token`, and `secrets/sessions.sqlite`
are private files. Never copy them into the frontend bundle or commit them.
The local reviewer key is `output/deployment/access-key.txt` (gitignored,
mode 0600). Reviewer notes and the “reviewed” flag are saved separately from
model conclusions; they never rewrite the automated verdict.

The “Показывать рамки” switch above the player hides all person, object and
geometry overlays at once. It is also available in fullscreen. Visibility and
detector/context mode are remembered in this browser across clips and reloads.

## Analysis behavior

Person detection uses RT-DETR and BoT-SORT with OSNet ReID at 10 fps. The first
two seconds of a video are decoded at native frame rate for role initialization.
Reviewed geometry is bound to source SHA-256, image dimensions, and reference
image hashes. The banker role stays attached to the person; uncertain per-frame
associations and possible reflections cannot support action attribution.
A stable, distinct person on the safe side is required for banker handoff.
Three recordings use explicitly reviewed first-frame role seeds.

OWLv2 analyzes native-resolution desk crops at 2 fps. Person context excludes
clothing contained within a person, without excluding clothing left on the desk.
Reviewed equipment corrections apply only to the exact video, box and interval.
Object intervals contain observed samples and do not bridge missing detections.
Full-frame context and desk crops are also supplied to the action analyzer.

Money, cards, packaging and stamps remain uncertain candidates. No new accuracy
or F1 claim is made for this combined deployment. For new, uncalibrated camera
views, tabletop detection is explicitly unavailable until scene calibration;
the UI reports this limitation. The inference deadline remains 295 seconds per
active job, excluding queue waiting; long recordings may have incomplete
coverage, reported in the overview limitations, or a timeout failure.

## Dataset

All 42 MOV filenames from `/Users/jokeoa/Downloads/open/` were imported and
verified by SHA-256 (40 unique file contents; duplicate contents under distinct filenames remain
separate review entries). `source-manifest.json` and `import-receipts.json` on
the server link original names, checksums and job IDs. All 42 previews were
verified ready. Jobs continue on the server independently of this chat.

## Operations

```sh
ssh -T -o ForwardAgent=no -o ControlPath=none flaky-lime-lemur
systemctl status cashguard-api cashguard-web cashguard-tunnel
journalctl -u cashguard-api -n 100 --no-pager
```

`backend/deploy/install_production.sh` installs the API and frontend systemd
units for this host. It preserves an existing key file. Build the frontend with
`npm ci && npm run build` in `app`, deploy `dist`, `package.json` and the lockfile,
and run `npm ci --omit=dev --ignore-scripts` on the server. Static paths in srvx
are relative to the server entry directory (`--static ../client`).

The existing GPU environment is
`/home/ubuntu/role-tracking-prototype/.venv` with torch 2.14.1+cu130,
transformers 5.20.1, boxmot 25.0.0 and the cached model weights. The production
vision package is `backend/app/vision`; runtime calibration assets live in
`backend/references`. Preserve that directory when deploying. Its reference
frames are private dataset material, not public web assets.

To resume an interrupted import, source `secrets/service.env` and run
`backend/deploy/import_videos.py` with the GPU environment's Python. It checks
both the import source and existing job's source hash before skipping a video.

`backend/deploy/check_public.py` checks the public HTTPS site, authenticated
history, observations, byte-range playback and logout. It writes a verification
report without credentials. Run it with `API_KEY` loaded from the private env.

## Verification

- 23 frontend tests; TypeScript and production build.
- 10 API/storage tests, including auth, persistent reviews, recovery and ranges.
- 46 API responses validated against the merged frontend contracts; OpenAPI check.
- 38 production vision policy tests (`backend/tests/vision`), including native
  first-window decoding, causal role lookup, reflections, handoff and equipment.
- Real GPU jobs and public HTTPS smoke check; all 42 previews available.

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests
# Requires detector dependencies, OpenCV and ffmpeg:
PYTHONPATH=backend python -m unittest discover -s backend/tests/vision
cd app
npm test
npm run typecheck
npm run build
```
