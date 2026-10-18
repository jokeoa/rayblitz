# Role and identity tracking experiment

Experiments for the bank-office videos in `open.zip`. The original tracker comparison is isolated. The later 37-video batch runs the backend action pipeline with explicit per-video role context; the safe-side comparison evaluates role initialization separately.

## Comparison

- Source-selected clips: X-4, X-18, X-27, X-38. The archive contains 42 MOV files and 40 unique byte hashes; X-47 duplicates X-4, X-48 duplicates X-5.
- One RT-DETRv2 R50 detector pass, original frame resolution, canonical FFmpeg sampling at 10 fps. Both tracker arms consume the exact same cached detections.
- BoxMOT 25.0.0 ByteTrack versus BoT-SORT with OSNet x0.25 MSMT17 appearance embeddings. Fixed camera: camera-motion compensation is disabled. High/new-track threshold 0.5, low threshold 0.1, lost-track buffer 3 seconds in both arms. Other algorithm-specific defaults remain unchanged. This compares two complete tracker configurations; it does not isolate the causal effect of ReID alone.
- One shared Qwen3.5-9B role observation every 5 seconds. These predictions are independent of tracker IDs and reused by both arms. Two consistent observations establish a role; contradictory observations or an absence over 1 second clear it. New observations from heavily overlapping boxes are withheld. Roles are observable service roles, not verified employment status.
- `unknown` is a legitimate result. Historical roles can still transfer incorrectly if a tracker swaps identities without a gap: this is a known limitation to inspect, not a solved failure mode.
- No face identification, manual scene polygons, audio, or event/violation labels are inputs to either pipeline.

## Run

Python 3.12, NVIDIA GPU, FFmpeg, and `uv` are required for inference.

```sh
python extract.py /path/to/open.zip
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
mkdir -p weights runs
.venv/bin/python prepare.py
.venv/bin/python test_role_policy.py
.venv/bin/python run.py
.venv/bin/python capture_metadata.py
.venv/bin/python report.py
```

On the supplied Brev instance the experiment lives in `/home/ubuntu/role-tracking-prototype`; `setup_remote.sh` installs its isolated environment. Model downloads happen on that instance. `runs/pip-freeze.txt`, `runs/environment.json`, `runs/model-snapshots.json`, `runs/run.json`, source hashes and each stage's log preserve provenance. Transformers returned null for the models' private `_commit_hash`; the separate snapshot manifest records the actual cached revisions. The first run includes cold model downloads and initialization.

Individual stages can be run with `.venv/bin/python detect.py`, `track.py`, `roles.py`, `render.py`, and `audit.py`. Detection, tracking and role generation also accept `--videos X-18`. Render and audit expect all four configured clips. Delete or move the corresponding role cache before intentionally changing the role sampling/model configuration; do not mix incompatible caches.

Use `run.py --from-stage track` (or `roles`, `render`, `audit`) to resume after fixing a stage. Earlier run manifests and overwritten stage logs are retained. `report.py` builds a local HTML viewer with synchronized comparison videos, timestamp navigation, and playback speed controls.

From the repository root, serve the viewer with the project's existing Vite dependency:

```sh
node app/node_modules/vite/bin/vite.js preview --config experiments/role-tracking/preview.config.mjs
```

Open `http://127.0.0.1:8765/index.html`. This server binds only to loopback and supports video range requests; Python's basic `http.server` does not provide reliable timestamp seeking here.

## Inspect

- `runs/<video>/<video>-comparison.mp4`: synchronized side-by-side overlays with ID, role, and box-overlap warning. Audio omitted.
- `runs/<video>/detections.json`: immutable common detector input, source SHA-256 and sampling metadata.
- `runs/<video>/{bytetrack,botsort_reid}.json`: raw tracks and tracker update timings.
- `runs/<video>/role_observations.json`: automatic observations, visible reasons, raw model answers and parse failures.
- `runs/<video>/*_roles.json`: causal role timeline and reset reasons.
- `runs/audit/`: full-size before/after snapshots, contact sheets, and candidate discontinuities. The fixed source-selected audit moments are in `audit_cases.json`.
- `runs/summary.json`: unique predicted ID counts, role coverage and timings. None of these is identity or role accuracy.

Box overlap is only a candidate occlusion signal. Reflections, adjacent silhouettes, false detections and true physical occlusion must be distinguished by inspecting the source. A lower ID count may mean fewer fragments or more incorrect merges.

## Reliability evaluation

The existing event annotations do not contain person IDs or roles. This exploratory run cannot report defensible IDF1/HOTA or role accuracy from those labels. First review the fixed episodes and classify actual failures into missed/false detections, fragmentation, ID switches, wrong reattachment, and role errors. Record uncertain cases explicitly.

For a subsequent independent benchmark, annotate persistent person IDs, boxes, observable roles, visibility/occlusion and reflection/ignore regions. A human reviewer should confirm the identities before/after each interruption and role labels. Split by recording setup/session before choosing thresholds; reserve new setups for evaluation. Report detection recall, IDF1/HOTA on sufficiently dense annotations, role precision at coverage, post-occlusion identity preservation, role recovery delay, and the resulting action-attribution errors. Report confidence intervals over episodes, not correlated neighboring frames.

## Reflection filter comparison

`reflection_observe.py` uses the already pinned Qwen model to classify detector
proposals as direct people, reflections, or uncertain, with a visible direct
counterpart required for reflections. It samples every two seconds. It reads no
manual zones, person roles, or evaluation labels. `reflection_filter.py` accepts
only intervals bracketed by two matching reflection/counterpart observations on
continuous provisional ByteTrack tracks. Any direct-person observation protects
that provisional ID throughout the clip. Overlaps, gaps, abrupt motion, missing
partners and uncertainty preserve the original detection.

This is an **offline** filter, using future observations and a clip-wide veto.
It is not a streaming solution or a guarantee that no real person is removed.
Both final trackers are rerun on exactly the same filtered detections, with
source detection indices preserved for replaying the unchanged role observations.
The provisional ByteTrack dependency is not an isolated tracker ablation.

```sh
.venv/bin/python reflection_run.py
```

If the full observation pass was already run separately, use
`reflection_run.py --skip-observe`. An incomplete observation cache is rejected.
Before rerunning the complete pipeline, move its existing `runs/reflections/run.json`
manifest so prior provenance is preserved. The original `runs/<video>/` results
are never overwritten by this pipeline.

Outputs are in `runs/reflections/`: eight before/after MP4s, raw model responses,
per-frame removal reasons, filtered detections, rerun tracks, `evaluation.json`,
`validation.json`, and an HTML report. The same local Vite preview serves
`http://127.0.0.1:8765/reflections/index.html`.

`reflection_review.py` generates six human-review targets. The user's explicit
labels are saved in `reflection_human_labels.json`; other diagnostic candidate
box reviews are in `reflection_assistant_labels.json`. **Only the evaluator reads
these labels.** These are 24 selected-frame diagnostics, not exhaustive person
ground truth or held-out accuracy. Report retained real candidate boxes and
post-tracker coverage separately from reflected boxes removed. A partial box and
a full box can describe the same physical person; these are not unique-person
counts. The original source detector's missed people cannot be measured from
candidate-only annotations.

The additional user-requested X-48 and X-11 replication uses the same frozen
model weights, prompts, thresholds and sampling. X-48 is byte-identical to X-5,
which was not in the first four-clip comparison. Run it with:

```sh
.venv/bin/python reflection_extra_run.py
```

The run snapshots its source and records every stage in
`runs/reflections-extra/run.json`. It produces a separate pair of before/after
videos for each clip. Reflection observation, filtering, rendering and validation
accept `--videos` and `--output-root` for explicit selection; inference still
reads its original detection cache from `runs/<video>/`. The fixed audit moments
in `runs/reflections-extra/audit_times.json` were chosen from source footage
before viewing predictions. Additional qualitative diagnoses selected after
inference must be identified separately from that fixed audit.

## Human role review form

The first review batch contains 12 source frames from X-4, X-18 and X-48.
Generate the frames, then package the standalone HTML document:

```sh
.venv/bin/python role_review.py
python3 build_role_review.py
```

Open `runs/first-entrant-review/batch-1/index.html` directly in a browser, or use
the existing preview server at
`http://127.0.0.1:8765/first-entrant-review/batch-1/index.html`.
All images and UI code are embedded; the document needs no network requests.
Define persistent participant IDs per video, then map each frame-local detection
to a person, reflection, duplicate, non-person or uncertain observation. Timeline
notes and the first-entrant hypothesis are recorded separately. Drafts stay in
browser storage; export JSON to share or resume answers, or copy the text summary.
The JSON includes source hashes, frame times, boxes and explicit unreviewed states.
An empty form contains no inferred human labels. These selected diagnostic frames
are not an independent accuracy benchmark.

## Static person roles and independent frame association

`anchored_role_policy.py` now estimates one immutable service role per scene-local
person. `person_association.py` separately links tracker boxes to those people.
The output registry `people[person_id].role` is the only stored role; individual
boxes contain `person_id`, `candidate_person_id` and `association`, never a mutable
role. Entity IDs use E1, E2, etc. and are separate from human annotation IDs P1,
P2, etc. IDs are local to each clip.

Association confidence is an explainable category (`supported`, `uncertain`,
`unresolved`), not a calibrated probability. Only supported links can attribute
actions. Overlap makes the current link uncertain without erasing the person's
role or waiting for new role-model votes. A gap, jump, non-unique link, competing
person geometry or explicit reflection conflict breaks the link and preserves
the role in the registry. New tracker IDs do not inherit old roles. Independent
identity evidence or human confirmation is needed to reconnect a broken link;
this experiment does not implement appearance-based reattachment.

Roles use observations from the **whole clip**, so role estimation is offline.
The unique directly observed opening banker is retained despite later semantic
conflicts. A customer requires at least two supported customer observations;
other people are not declared customers by exclusion. Initial classification can
still be wrong or unresolved. Reflection observations are also fallible and can
create spurious provisional person records or break valid links. Silent swaps
with indistinguishable geometry may remain undetected.

The previous implementation and its actual output are frozen in
`runs/static-roles/before/` as experimental evidence. They are not a compatibility
path and are not executed by the current runner. The runner verifies identical
source hashes, observation hashes, track hashes and the shared input config
before comparing. It never reads `role_review_labels.json`; only the evaluator
does. The upstream reflection filter remains offline.

From this experiment directory, replay the cached observations and render all
three complete videos for both tracker arms:

```sh
.venv/bin/python test_anchored_role_policy.py
.venv/bin/python anchored_role_run.py --videos X-4 X-18 --tracks-root runs/reflections
.venv/bin/python anchored_role_run.py --videos X-48 --tracks-root runs/reflections-extra
.venv/bin/python anchored_role_evaluate.py
.venv/bin/python anchored_role_report.py
.venv/bin/python static_role_validate.py
```

Open `http://127.0.0.1:8765/static-roles/index.html`. It contains six complete
before/after MP4s, 24 paired review images, separate role/link columns, per-person
model evidence, the evaluation and structural/media validation. The previous
annotation form and its saved answers are unchanged.

Compared with the immediately preceding anchored policy, each tracker changes
correct / wrong / unknown actionable roles from **8 / 0 / 11** to **9 / 0 / 10**
on 19 reviewed direct-person boxes after the opening frame. Banker identification
changes from 8/9 to 9/9, with zero false banker assignments in either version.
Customer roles remain unresolved in these reviewed examples. Over the complete
cached timelines, banker attribution is blocked on 98 -> 1 frames in X-4,
86 -> 19 in X-18, and 0 -> 0 in X-48 (10 fps). These are selected development
examples, not independent identity accuracy, action accuracy or a clothing-change
benchmark. The production backend is not changed by this isolated experiment.

### Appearance changes

The role layer does not read clothes, colors or appearance embeddings. Movement,
turning or removing a jacket must not change a person's stored role, but the
upstream tracker can still lose or switch the ID. The existing BoT-SORT arm
already uses OSNet embeddings; adding ReID alone is not evidence of robustness
to changed clothes.

A subsequent experiment should combine motion/time constraints with a bounded
gallery of trusted appearance samples, updating that gallery only when identity
association is reliable. After a long disappearance or a new appearance with no
reliable link, preserve the old person's role but do not transfer it automatically.
Compare ordinary re-identification with a clothes-changing model on separately
labeled episodes: turning/lighting changes, removing a jacket while visible,
returning in different clothes, and a different person wearing similar clothes.
Measure wrong role transfers, identity switches, unresolved coverage and recovery
delay. Body/shape evidence may help but must be validated at this resolution;
face identification is outside this experiment.

Primary research: [Deep SORT](https://arxiv.org/abs/1703.07402) combines motion and
appearance evidence; [CAL](https://openaccess.thecvf.com/content/CVPR2022/html/Gu_Clothes-Changing_Person_Re-Identification_With_RGB_Modality_Only_CVPR_2022_paper.html)
studies clothes-irrelevant features. These motivate candidate experiments, not
measured claims about this system.

## Libraries

- [BoxMOT](https://github.com/mikel-brostrom/boxmot)
- [RT-DETRv2 R50](https://huggingface.co/PekingU/rtdetr_v2_r50vd)
- [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)

Only the pinned installed package's actual API is used; published documentation can describe a different package revision.

## Reference transfer to the remaining 37 recordings

The user authorized automatic transfer of their corrected annotations to the
other videos. `runs/remaining-videos/selection.json` excludes X-4, X-18, X-48
by source hash, also excluding exact copies X-47 and X-5. The remaining 37
unique source hashes are verified on the supplied Brev environment.

`reference_track.py` runs BoT-SORT with the existing OSNet model at 10 fps.
`reference_policy.py` uses the corrected direct-person and reflection crops as
appearance references. A role is assigned once after three consecutive accepted
matches; it is not reclassified later. Roles belong to the per-video person
registry. Per-frame links have separate support, ambiguity reasons and appearance
similarity. Similarities are not calibrated probabilities. Short fragments may
reconnect only with matching appearance, overlapping position, a time bound,
a unique candidate and no simultaneously active old track. Overlap, conflicting
appearance, reflection evidence, long gaps and geometric jumps block attribution.
The bounded appearance gallery updates only on supported associations.

These are automatic role predictions for new videos, **not human labels** or
verified cross-video identities. Different people, clothing changes and camera
views can remain unknown or match incorrectly. No target-video identity accuracy
is claimed. Reflection matching is an appearance veto, not a guaranteed physical
reflection detector. The prior Qwen reflection filter is not run in this batch;
all original detector proposals remain available for inspection.

The main backend consumes these tracks through `app/role_context.py` and
`eval/run_reference_batch.py`. Rule-window images include supported role IDs;
uncertain boxes remain unknown. Employee hand-object checks use supported banker
boxes. Desk departure evidence requires a visible supported banker moving away;
a missing person detection never proves departure. The action pipeline retains
its existing Qwen rule scan, object checks, thresholds and evidence extraction.
Input overlays change the model input, so historical threshold accuracy does not
establish this run's accuracy. The offline batch has no scan deadline and checks
that every expected action window completed.

Run on Brev, from the experiment directory, after copying the selected sources:

```sh
.venv/bin/python detect.py --output-root runs/remaining-videos --videos <selected IDs>
.venv/bin/python test_reference_policy.py
.venv/bin/python reference_track.py
# Start the backend's local llama.cpp server and install its dependencies.
PYTHONPATH=/path/to/backend .venv/bin/python /path/to/backend/eval/run_reference_batch.py --experiment "$PWD"
.venv/bin/python remaining_report.py --render
```

The report is `runs/remaining-videos/index.html`, served locally at
`http://127.0.0.1:8765/remaining-videos/index.html`. Each video has complete
`tracked.mp4`, `person_tracks.json`, `action_result.json`, window-level raw
model scores and evidence frames. `media_validation.json` records full output
frame counts, durations and hashes. No findings is not evidence of compliance,
particularly where roles remain unresolved. Original three-video reports are
historical experiments and are not overwritten by this batch.

## Safe-side geometry experiment (37 target videos)

The active path uses a frozen, source-bound **desk + safe** reference. Automatic
object proposals cannot replace the safe with a pedestal. See
[SAFE_REFERENCE.md](SAFE_REFERENCE.md) for the decision, reference images,
provenance, geometry, limitations, data contract and repeatable commands.

Every native source frame in `[0, 2)` participates in initial assignment, which
becomes available at second 2 without an additional wait. Afterwards the chosen
banker persists until an unambiguous different candidate is supported on the
safe side for one second. A lost track does not change the selection. Person
roles remain immutable; the current serving banker and frame association are
separate fields. The remaining tracking timeline stays at 10 FPS.

`initial_window.json` records native timestamps, detector observations and votes.
`person_tracks.json` records the frozen reference, person registry, associations
and banker transition log. `safe_side_report.py` renders and validates all 37
videos. The old automatic OWLv2 localization and calibrated 3-second run are
historical comparisons only, not active fallback paths.

The full action batch in `runs/remaining-videos` uses appearance-reference roles;
the geometric comparison does not by itself measure action-detection improvement.

### Extension boundary: geometric landmarks

The current scene object pool is `geometry.objects` and contains exactly
`desk` and `safe`. Object localization/calibration produces this pool;
`geometry_axis()` consumes it to derive the safe-facing direction;
`SafeSideAssociator` initializes a role and independently validates identity
links. This boundary is the architectural extension point for additional
landmarks if explicitly requested later. No additional object classes,
landmark weights, workstation scoring or generic object tracker are enabled.
The current banker decision continues to use only safe position relative to
the desk and the observed person's position.


### Customer labels, reflections, and a missing safe

The safe-side pipeline writes immutable banker results to `banker_tracks.json`,
then `safe_side_labels.py` writes `person_tracks.json`. Remaining observations
are labeled customers by exclusion after banker initialization. Unresolved banker
links stay unknown. Original `possible_reflection` flags are retained independently
and veto action attribution without erasing the banker's role.

For a registered desk with `objects.safe=null`, `scene_anchor_search.py` searches
all native opening frames for a safe, then nearby safe-like storage. A proxy is
explicitly a hypothesis; ambiguous candidates on opposite desk sides do not
orient the scene. An existing safe reference never invokes this search.
See [SAFE_REFERENCE.md](SAFE_REFERENCE.md) for conditions and limitations.

All 37 current clips have safe references, so proxy detection quality on an actual
safe-free scene remains unmeasured. The 37 scenario/regression tests pass. Replayed
labels preserve every banker choice, with 2377 possible-reflection observations
and 14,985 default-customer observations. The reflection action veto reduces
supported active-banker coverage from 82.9% to 75.4%; neither is role accuracy.
