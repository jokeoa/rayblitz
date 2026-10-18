# Desk-object resolution experiment

Controlled development comparison on the supplied bank-office videos. This is an
isolated experiment; it does not change the service's production preprocessing.

## Compared inputs

All arms use OWLv2 base patch16 ensemble, revision
`cfd3195ba4ea9592eec887ded089f4c08eff231d`, FP32, the same 22 text queries,
candidate threshold 0.05 and class-specific NMS at IoU 0.5. The displayed and
diagnostic score threshold is frozen at 0.15, not calibrated probability.

1. `reduced`: the same decoded frames, resized by FFmpeg to width 336.
2. `native`: original 464×848 frames.
3. `tiles`: native full-frame predictions plus six overlapping 384×384 crops,
   with coordinates returned to the original frame and class-specific NMS.
4. `desk`: one native crop centered on the existing reviewed desk; its square
   side is 1.2 times the longest desk-box dimension, clipped to image bounds.

PNG is used in every arm to separate resolution from JPEG compression. This is
**not** a replay of the full production service (which samples at 2 fps and uses
VLM rules). All detector arms run at 10 fps. OWLv2 itself resizes its inputs;
`runtime.json` records the actual image processor settings. Crops allocate more
model pixels to objects but do not recover information absent from the source.

Twelve source-selected four-second episodes cover money, cards, stationery,
equipment, packaging, scissors and several bags. These are development examples,
not an independent test set. No violation labels or object ground-truth boxes
are passed into inference. An initial 18-class pilot and partial run are kept
in `pilot-18/`; after human source clarification the final vocabulary was frozen
for all arms. No predictions from different vocabularies are combined.

## Existing desk geometry

`desk_scope.py` consumes `../role-tracking/scene_references.json`, verifies the
source hash, frame size and reference image hash, and records the authority hash
in `runs/desk-scope.json`. It does not create a new plane or replace geometry.
The existing representation is a desk bounding box plus a side-divider line,
not a surface segmentation mask or a homography.

All four arms retain candidates whose bottom-center lies in that same desk box,
excluding the safe class. This is a spatial candidate gate, not proof of physical
contact: hands and held objects can project into the region. Only independently
visually reviewed resting objects enter the selected-reference evaluation.
X-18 has no reviewed desk reference and is explicitly excluded: 11 episodes,
440 frames in the desk comparison. Existing whole-scene caches are retained as
source evidence; tracking is rerun after desk filtering for all four arms.

## Tracking

BoxMOT 25.0.0 ByteTrack runs separately for each class with the same settings in
every arm: min confidence 0.05, high/new-track threshold 0.15, match threshold 0.8,
lost buffer 0.5 s. No person appearance encoder is used for small objects.

Both 10 fps and 2 fps consume the same cached detections; 2 fps uses every fifth
frame. The buffer is scaled in seconds for each rate. Output IDs are predictions
local to video/arm/class/rate; class changes create separate tracks. Every
exported track points to its supporting detection. A lower ID count can also be
an incorrect merge, and an ID does not prove physical identity after occlusion.

## Evidence and limits

- `human_labels.json` preserves the user's direct replies. In particular, the
  shown X-22 lock has **no key**; X-24 contains stamps and a notebook; X-46 contains
  money on the desk and packaging in the hand. Do not extend those labels to
  other timestamps or claim the user drew the boxes.
- `reference_objects.json` contains selected positive source references, with
  assistant-drawn boxes and separate class-identity provenance. It is not
  exhaustive, so unmatched predictions are not counted as false positives.
- Selected-reference hits use class-specific score-ordered one-to-one matching
  at IoU 0.5, with IoU 0.3 also saved because tiny boxes are sensitive to a few
  pixels. The user-confirmed class subset is counted separately.
- The lock negative, hand-held packaging, safe and bag handover are preserved
  in label history but excluded from the current table-only evaluation.
- Static-object track coverage uses assistant-reviewed fixed boxes. It is not
  IDF1, HOTA, handoff accuracy or post-occlusion identity preservation. Dense
  independently reviewed object identities are still needed for those metrics.
- Inference timings include processor, model and initial postprocessing, exclude
  video decode and final cross-crop NMS, and reuse the full native pass in the
  tiled arm's recorded total. They are not full-service latency. The GPU is shared
  with an existing VLM server; loading/warmup is recorded separately.

## Run

Use the project's existing GPU environment with torch, transformers,
torchvision, BoxMOT and Pillow. Model weights must already be cached; inference
uses `local_files_only=True`. FFmpeg is required. On the user's authorized Brev
machine this environment is `/home/ubuntu/role-tracking-prototype/.venv`.

```sh
python prepare.py --data /path/to/videos
python test_geometry.py
python run.py
python pixel_hashes.py
python validate.py
python desk_scope.py
python run_desk.py
python validate_desk.py
python report.py
```

`prepare.py` and `detect.py` reject overwriting an existing run. Preserve old
experiments before intentionally changing the configuration. `run.py` snapshots
source files and records explicit running/failed/complete status. It runs the
detector then the tracker. Evaluation reads labels only after inference.

For local report authoring, use `experiments/role-tracking/.venv/bin/python`
(Pillow and NumPy are already installed). From the repository root:

```sh
node app/node_modules/vite/bin/vite.js preview --config experiments/object-resolution/preview.config.mjs
```

Open `http://127.0.0.1:8766/`. The viewer synchronizes all arms, filters classes
and scores, shows source images and reference boxes, and exports local review
notes. Changing its score slider does not rerun tracking or alter saved metrics.

`validation.json` verifies input pixels, hashes, configurations, frame alignment,
box coordinates and each track's supporting detection. PNG byte hashes can differ
between FFmpeg encoders, so cross-machine visual identity is checked on decoded
RGB pixels. In this run the two machines decoded different pixels, so the viewer
uses the actual remote inference PNGs downloaded back to the local workspace.
`desk-validation.json` additionally checks equal spatial filtering, the source
geometry hash and detector support for every desk track. Structural validation
is distinct from model accuracy.

## Measured development result (2026-10-18)

Existing desk references were reused for 11 episodes / 440 frames. There are
14 selected resting objects, including 10 with user-confirmed class identities;
all boxes were drawn by the assistant. Threshold 0.15; class-correct IoU >= 0.5.

| Input | Selected hits | User-confirmed class subset | Median detector ms/frame |
|---|---:|---:|---:|
| reduced | 3/14 | 0/10 | 177 |
| native | 5/14 | 2/10 | 181 |
| tiles | 6/14 | 2/10 | 1280 |
| desk | 6/14 | 2/10 | 183 |

The desk crop matches the tiled arm on these references at about one seventh
of its recorded inference time. This does not establish equivalent general
accuracy: annotations are sparse development examples and there is no measured
precision. Five of six selected money bundles and the wrapper still fail
class-correct detection; nearby predictions commonly say card. Both stamps
are missed in every arm. Increasing resolution alone is insufficient here.

At 10 fps, the notebook has a matching track in 17/40 reduced frames and 40/40
native and desk frames. The stationary green bag has 8/40 reduced, 6/40 native
and 40/40 desk matches. These use fixed reference boxes at IoU >= 0.3 and have
one matched ID per successful sequence. The two stamps have no matching tracks.
The 2 fps comparison covers these same stationary objects; it cannot establish
reliable handovers or recovery after occlusion.

Validation passed: 960 canonical images, 480 baseline frames, 440 desk frames,
69,154 cached desk candidates and 14,060 detector-supported track observations.
These are integrity counts, not correctly recognized object counts. Four
geometry/matching tests passed. The viewer was checked in the browser.

The current approach is useful for a cheap, focused candidate stream. Reliable
money/wrapper/stamp classification still needs a separately evaluated solution
on these camera images; automatic class claims should remain unresolved when
unsupported. Production preprocessing and the existing GPU service were not changed.

## Person context, equipment and observation time

`context_resolution.py` consumes existing `role-tracking/runs/safe-side` outputs,
checking the video hash and coordinate size. It selects the latest role row at or
before each object timestamp, expires rows older than 1.1 role sampling periods,
and does not use a person identity before its initialization time. It does not
assign roles again or modify the role pipeline.

Clothing candidates at least 80% contained in a person box with detection score
at least 0.5 are excluded from the tabletop candidate stream. Unknown roles and
possible reflections remain explicitly uncertain; their boxes can explain a
clothing false positive but cannot prove an action or identity. Mere intersection
does not remove an object: the actual jacket on the X-40 desk at 15 s is retained.
Regression cases also cover worn clothing in X-24, X-14 and X-1.

`scene_objects.json` separately records the user's cash-counter class correction
and assistant-drawn scene boxes. Matching the same visible machine across clips
is an assistant review, not additional user annotation. The calibration is scoped
to source hashes and the selected four-second intervals; first, middle and last
frames were inspected. It corrects overlapping device proposals, never inserts a
synthetic detection. It works on the left (including X-24) and right (X-40, X-44,
X-46), while retaining the actual telephone elsewhere. It is not a learned
recognition improvement. The authoritative desk geometry is unchanged.

The viewer defaults to this context layer and provides the original model layer.
Raw detection metrics remain unchanged. Cached ByteTrack IDs are retained; only
their supported observations are filtered/relabelled. Observation time sums
sample support at each FPS and splits intervals at missing observations. It is
not continuous presence, contact time, or proof of absence during missing data.

At score 0.15 on the desk arm, 239 clothing observations are excluded and 226
equipment-class observations are corrected. These are decisions, not verified
true-positive counts. Validation covers all 69,154 candidate decisions, 440
frames and 13,488 remaining detector-supported track observations across arms
and rates. Eight unit/regression tests passed, including future-role leakage,
stale roles, actual tabletop clothing, spatial/time scoping and gaps in duration.

The review gallery has 11 canonical equipment frames plus 10 newly inferred
frames with person orientation changes. The latter are outside the original
benchmark and do not change its metrics. Their GPU-decoded PNGs and hashes are
saved in `runs/side-probe`; no local re-decode substitutes their inference pixels.

## Additional money diagnostics

`money_probe.py` ran 44 fixed frames (0, 10, 20, 30 in every eligible episode).
It adds cash/wrapper/counter query variants and compares the same desk crop with
96–160 px close-ups selected from model proposals, without reading reference
labels. Competing cash/card/document/wrapper proposals are resolved by score,
which is not a calibrated probability. Evaluation remains a post-baseline
development comparison on the same sparse references.

| Diagnostic | Selected hits / 14 | Selected cash hits / 6 | Wrapper / 1 |
|---|---:|---:|---:|
| Original desk queries | 6 | 1 | 0 |
| Revised queries, desk crop | 8 | 3 | 0 |
| Revised queries, desk + close-ups | 9 | 4 | 0 |

Close-ups incorrectly label the empty X-14 wrapper as cash. The X-46 money
proposal also competes with a food label. These variants are displayed separately
and are not automatically enabled in the primary layer.

`semantic_probe.py` additionally used the already running local Qwen3.5-9B-Q4_K_M
server on 12 proposals at frame 20 across the 11 episodes. Each request used a
96-source-pixel crop enlarged to 384 px, a cyan target outline, temperature 0 and
explicit cash/packaging/card/document/other/unknown choices. No reference labels
were supplied. This resizing adds no source detail. Raw prompts, responses,
inputs and latency are saved in `runs/semantic-probe`.

The VLM classified 3/6 selected cash bundles correctly and identified the empty
wrapper, but called the front X-14 cash bundle packaging, the left X-13 cash
bundle a document, and the X-46 bundle another object. It is not enabled as a
semantic override. Neither extra pixels nor a second language-model answer
solved the cash/wrapper distinction on these examples.

After the three bounded probes complete and their artifacts are retrieved:

```sh
python -m unittest discover -s experiments/object-resolution -p 'test_*.py' -v
python experiments/object-resolution/report.py
python experiments/object-resolution/validate_context.py
```

The report requires all three completed probe outputs and verified role sources;
there is no silent fallback to missing or stale evidence.
