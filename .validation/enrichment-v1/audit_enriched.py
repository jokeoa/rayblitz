#!/usr/bin/env python3
"""Read-only structural/provenance audit; no model or network calls.

Optional source verification decodes local originals with PyAV/Pillow and hashes
the same documented resized RGB pixels. It does not inspect semantic content.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def jsonl(path):
    with Path(path).open() as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def close(a, b, tolerance=1e-7):
    return finite(a) and finite(b) and abs(a - b) <= tolerance


def finite_stat(value):
    value = float(value)
    return value if math.isfinite(value) else None


def bounds(duration):
    if duration <= 12:
        return [(0.0, duration)]
    starts = [float(x) for x in range(0, math.floor((duration - 12) / 8) * 8 + 1, 8)]
    if duration - 12 - starts[-1] > 1e-6:
        starts.append(duration - 12)
    return [(start, min(duration, start + 12)) for start in starts]


class Audit:
    def __init__(self):
        self.checks = Counter()
        self.errors = Counter()
        self.examples = []

    def check(self, condition, code, location="", details=None):
        self.checks[code] += 1
        if not condition:
            self.errors[code] += 1
            if len(self.examples) < 100:
                self.examples.append({"check": code, "location": str(location), "details": details})
        return bool(condition)

    def snapshot_file(self, root, name):
        paths = list(root.rglob(name))
        self.check(len(paths) == 1, "snapshot_unique_file", name, [str(p) for p in paths])
        if len(paths) != 1:
            raise ValueError(f"Need one snapshot file: {name}")
        return paths[0]


def verify_sources(args, run, manifest, detections, audit):
    import av
    import PIL
    from PIL import Image

    audit.check(av.__version__ == run["package_versions"]["av"], "source_decoder_version")
    audit.check(PIL.__version__ == run["package_versions"]["Pillow"], "source_resize_version")
    total = 0
    for video_id in run["video_ids"]:
        item = manifest[video_id]
        source = args.data_root / item["source_path"]
        audit.check(digest(source) == item["sha256"], "source_file_sha256", video_id)
        saved = detections.get(video_id, [])
        next_target, origin, index = 0.0, None, 0
        with av.open(str(source)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            for source_index, frame in enumerate(container.decode(stream)):
                timestamp_abs = float(frame.pts * frame.time_base)
                if origin is None:
                    origin = timestamp_abs
                timestamp = timestamp_abs - origin
                if timestamp + 1e-8 < next_target:
                    continue
                while next_target <= timestamp + 1e-8:
                    next_target += 1.0 / run["arguments"]["fps"]
                image = frame.to_image()
                rotation = item.get("rotation_degrees") or 0
                if rotation:
                    image = image.rotate(-rotation, expand=True)
                scale = min(1.0, run["arguments"]["max_edge"] / max(image.size))
                size = tuple(max(32, round(dimension * scale / 32) * 32) for dimension in image.size)
                image = image.resize(size, Image.Resampling.LANCZOS)
                rgb = np.asarray(image.convert("RGB"))
                if index < len(saved):
                    row = saved[index]
                    location = f"{video_id}/{index}"
                    audit.check(row["source_frame_index"] == source_index and row["source_pts"] == int(frame.pts)
                                and row["time_base"] == str(frame.time_base) and close(row["time_sec"], timestamp),
                                "original_frame_identity", location)
                    audit.check(row["sha256_rgb"] == hashlib.sha256(rgb.tobytes()).hexdigest(),
                                "original_resized_rgb_sha256", location)
                index += 1
        audit.check(index == len(saved), "original_sampled_frame_count", video_id, [index, len(saved)])
        total += index
        print(json.dumps({"stage": "source_rgb_verified", "video_id": video_id, "frames": index}), flush=True)
    return {"decoded_frames": total, "av": av.__version__, "Pillow": PIL.__version__}


def finish(report, audit, output):
    report.update(status="passed" if not audit.errors else "failed", checks=dict(audit.checks), failures=dict(audit.errors), failure_examples=audit.examples)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": sum(audit.checks.values()), "failures": dict(audit.errors),
                      "summary": report.get("summary"), "report": str(output)}, ensure_ascii=False))
    return 0 if not audit.errors else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--model-locks", type=Path, help="Copied lock JSON files; defaults to snapshot sibling model-locks")
    parser.add_argument("--metadata-only", action="store_true", help="Audit the ready index, model locks and frozen source before the run finishes")
    parser.add_argument("--manifest", type=Path, default=Path(".validation/dataset_manifest.jsonl"))
    parser.add_argument("--data-root", type=Path, default=Path(".validation/data"))
    parser.add_argument("--baseline", type=Path, default=Path(".validation/runs/refinement-v1/F1_L1"))
    parser.add_argument("--verify-source-rgb", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = Audit()
    report = {"schema_version": "enriched-artifact-audit-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "run": str(args.run.resolve()), "snapshot": str(args.snapshot.resolve()),
              "audit_script_sha256": digest(__file__), "source_rgb_verification_requested": args.verify_source_rgb,
              "scope": "metadata_only" if args.metadata_only else "full_artifacts",
              "limitations": ["Structural/provenance checks do not establish detection, tracking, retrieval or violation accuracy.",
                  "Window embedding vectors are not saved, so logged cosine scores cannot be independently recomputed here.",
                  "Only common prefix token IDs and prompt hashes are saved; full per-query tokenization is not replayed.",
                  "Logs and source snapshots document the run; they are not independent hardware attestation or API SLA measurement."]}
    try:
        run = json.loads((args.run / "run.json").read_text())
        index = json.loads((args.run / "rule_index.json").read_text())
        snapshot_paths = {name: audit.snapshot_file(args.snapshot, name) for name in
                          ("run_vlm.py", "enrichment.py", "embeddings.py", "perception.py", "catalog.py", "rules.json", "rule_catalog.json")}
        catalog = json.loads(snapshot_paths["rule_catalog.json"].read_text())
        rules = json.loads(snapshot_paths["rules.json"].read_text())
        expected_codes = [f"{letter}-{number:02d}" for letter, count in zip("ABCDEFGH", (11, 6, 6, 18, 5, 12, 3, 3))
                          for number in range(1, count + 1)]
        active = [row for row in rules["rules"] if row["support"] == "experimental_visual"]
        queries = {row["code"]: row["question"] for row in active}
        audit.check(len(queries) == 28 and run["query_count_per_window"] == 28, "all_28_visual_queries")
        audit.check(run["active_rules"] == list(queries) and run["queries"] ==
                    [{"id": key, "question": value} for key, value in queries.items()], "frozen_query_identity")
        audit.check([r["code"] for r in catalog["rules"]] == expected_codes, "catalog_all_64_ids")
        audit.check(index["rule_ids"] == expected_codes and index["dimension"] == 768, "index_all_64_ids_dimension")
        vectors = np.load(args.run / "rule_embeddings.npy", allow_pickle=False)
        audit.check(vectors.shape == (64, 768) and vectors.dtype == np.float32, "vector_shape_dtype")
        audit.check(bool(np.isfinite(vectors).all()), "vector_finite")
        norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
        audit.check(bool(np.all(np.abs(norms - 1) <= 2e-6)), "vector_unit_norm")
        audit.check(index["vector_sha256"] == digest(args.run / "rule_embeddings.npy"), "vector_file_sha256")
        catalog_hash = digest(snapshot_paths["rule_catalog.json"])
        audit.check(index["catalog_sha256"] == run["enrichment"]["catalog_sha256"] == catalog_hash, "catalog_sha256")
        audit.check(run["rules_sha256"] == digest(snapshot_paths["rules.json"]), "visual_rules_sha256")
        audit.check(run["runner_sha256"] == digest(snapshot_paths["run_vlm.py"]), "runner_sha256")
        for name, sha in run["enrichment"]["source_sha256"].items():
            audit.check(name in snapshot_paths and digest(snapshot_paths[name]) == sha, "module_sha256", name)
        documents = {row["code"]: row["embedding_text"] for row in catalog["rules"]}
        text_sha = hashlib.sha256(json.dumps(documents, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        audit.check(index["inputs"]["rule_texts_sha256"] == text_sha, "embedding_rule_texts_sha256")
        audit.check(index["inputs"]["rule_count"] == 64 and index["inputs"]["rule_ids"] == expected_codes,
                    "embedding_rule_inputs_all_64")
        audit.check(sum(len(batch["actual_token_counts"]) for batch in index["inputs"]["batches"]) == 64,
                    "embedding_text_batch_coverage")
        audit.check(index["embedding"] == run["enrichment"]["embedding"], "embedding_metadata_identity")
        for where, metadata in (("index", index["inputs"]), ("embedding", index["embedding"]),
                                ("enrichment", run["enrichment"])):
            audit.check(metadata["hard_gate"] is False, "no_hard_gate_metadata", where)
        audit.check(run["enrichment"]["indexed_rules"] == 64 and run["enrichment"]["retrieval_top_k_in_prompt"] == 5
                    and run["enrichment"]["context_track_limit"] == 16, "enrichment_fixed_context_limits")
        locks = {}
        lock_root = args.model_locks or args.snapshot.parent / "model-locks"
        for lock_path in lock_root.rglob("*.json"):
            lock = json.loads(lock_path.read_text())
            audit.check(lock["model_id"] not in locks, "unique_model_lock", lock["model_id"])
            locks[lock["model_id"]] = (lock, lock_path)
        model_id = run["model_lock"]["model_id"]
        detector = run["enrichment"]["perception"]
        embedder = run["enrichment"]["embedding"]
        for identity in (model_id, detector["model_id"], embedder["model_id"]):
            if audit.check(identity in locks, "model_lock_snapshot_present", identity):
                lock, path = locks[identity]
                audit.check(bool(re.fullmatch(r"[a-f0-9]{40}", lock["revision"])) and lock.get("remote_code") is False
                            and bool(lock.get("license")), "immutable_model_lock", identity)
                if identity == model_id:
                    audit.check(lock == run["model_lock"] and digest(path) == run["model_lock_sha256"], "vlm_lock_identity")
                elif identity == detector["model_id"]:
                    audit.check(lock["revision"] == detector["revision"] and digest(path) == detector["model_lock_sha256"],
                                "detector_lock_identity")
                else:
                    audit.check(lock == embedder["model_lock"] and lock["revision"] == embedder["revision"], "embedding_lock_identity")
        manifest = {row["video_id"]: row for row in jsonl(args.manifest) if row["video_id"] == row["canonical_video_id"]}
        audit.check(run["manifest_sha256"] == digest(args.manifest), "manifest_sha256")
        audit.check(len(run["video_ids"]) == 40 and set(run["video_ids"]) == set(manifest), "all_40_canonical_videos")
        audit.check(run["arguments"]["fps"] == 5 and run["arguments"]["refine"] is True
                    and run["architecture"] == "F1", "base_and_refinement_configuration")
        audit.check(run["timing_scope"] == "local_pipeline_only_not_API_SLA", "timing_scope")
        audit.check(run["localization"]["candidate_threshold"] == 0.9399133512433593,
                    "frozen_development_threshold")
        if args.metadata_only:
            report["summary"] = {"recorded_run_status": run["status"], "indexed_rules": 64, "visual_questions": len(queries),
                "embedding_shape": list(vectors.shape), "embedding_norm_min": finite_stat(norms.min()), "embedding_norm_max": finite_stat(norms.max())}
            return finish(report, audit, args.output)
        audit.check(run["status"] == "finished" and run["partial_diagnostic"] is False, "run_finished_not_smoke")
        inputs = list(jsonl(args.run / "inputs.jsonl"))
        scores = list(jsonl(args.run / "scores.jsonl"))
        retrievals = list(jsonl(args.run / "retrieval.jsonl"))
        predictions = list(jsonl(args.run / "predictions.jsonl"))
        timings = list(jsonl(args.run / "timings.jsonl"))
        baseline = {(row["video_id"], row["window_id"]): row for row in jsonl(args.baseline / "inputs.jsonl")
                    if "window_id" in row}
        base_inputs = {(row["video_id"], row["window_id"]): row for row in inputs if "window_id" in row}
        base_scores = {(row["video_id"], row["window_id"]): row for row in scores if "window_id" in row}
        retrieval = {(row["video_id"], row["window_id"]): row for row in retrievals}
        audit.check(len(base_inputs) == sum("window_id" in row for row in inputs), "unique_base_inputs")
        audit.check(len(base_scores) == sum("window_id" in row for row in scores), "unique_base_scores")
        audit.check(len(retrieval) == len(retrievals), "unique_retrieval_windows")
        expected_windows = {(video, i) for video in run["video_ids"] for i, _ in enumerate(bounds(manifest[video]["duration_sec"]))}
        audit.check(set(base_inputs) == set(base_scores) == set(retrieval) == expected_windows, "complete_window_query_coverage")
        audit.check(set(base_inputs) == set(baseline), "baseline_window_coverage")
        detections = defaultdict(list)
        total_detections, total_tracked = 0, 0
        valid_classes = {row["class_name"] for row in detector["class_prompts"]}
        for frame in jsonl(args.run / "detections.jsonl"):
            video = frame["video_id"]
            prior = detections[video][-1] if detections[video] else None
            detections[video].append(frame)
            location = f"{video}/{frame['source_frame_index']}"
            audit.check(video in manifest, "detection_known_video", location)
            audit.check(finite(frame["time_sec"]) and frame["time_sec"] >= 0
                        and (prior is None or (frame["time_sec"] > prior["time_sec"]
                        and frame["source_frame_index"] > prior["source_frame_index"] and frame["source_pts"] > prior["source_pts"])),
                        "detection_monotonic_real_pts", location)
            origin = detections[video][0]
            audit.check(close(frame["time_sec"], float(frame["source_pts"] * Fraction(frame["time_base"]))
                              - float(origin["source_pts"] * Fraction(origin["time_base"]))), "pts_time_consistency", location)
            audit.check(frame["timestamp_sec"] == frame["time_sec"] and frame["image_size"] == frame["input_size"],
                        "detection_metadata_consistency", location)
            audit.check(bool(re.fullmatch(r"[a-f0-9]{64}", frame["sha256_rgb"])), "rgb_hash_format", location)
            width, height = frame["input_size"]
            seen_ids = set()
            for detection in frame["detections"]:
                total_detections += 1
                box, identity, name = detection["bbox_xyxy"], detection["track_id"], detection["class_name"]
                audit.check(name in valid_classes and finite(detection["score"]) and 0 <= detection["score"] <= 1,
                            "detection_class_score", location)
                audit.check(len(box) == 4 and all(finite(x) for x in box)
                            and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height,
                            "box_inside_input_image", location)
                audit.check((identity is None and detection["tracking_status"] == "unconfirmed")
                            or (isinstance(identity, str) and re.fullmatch(re.escape(name) + r":\d+", identity)
                                and detection["tracking_status"] == "associated"), "track_class_local_id", location)
                if identity is not None:
                    audit.check(identity not in seen_ids, "one_observation_per_track_per_frame", location)
                    seen_ids.add(identity)
                    total_tracked += 1
        for video, rows in detections.items():
            source = {row["source_frame_index"]: row for row in rows}
            audit.check(len(source) == len(rows), "unique_detection_source_frames", video)
            union = {frame["source_frame_index"] for key, row in base_inputs.items() if key[0] == video for frame in row["frames"]}
            audit.check(union == set(source), "detector_same_all_base_frames", video)
        for row in inputs:
            video = row["video_id"]
            location = f"{video}/{row.get('window_id', row.get('candidate_id'))}"
            source = {frame["source_frame_index"]: frame for frame in detections[video]}
            for frame in row["frames"]:
                match = source.get(frame["source_frame_index"])
                audit.check(match is not None and frame["pts"] == match["source_pts"] and frame["time_base"] == match["time_base"]
                            and frame["sha256_rgb"] == match["sha256_rgb"] and frame["time_sec"] == match["time_sec"],
                            "vlm_detection_frame_identity", location)
            fingerprint = hashlib.sha256(json.dumps({"start": row["window_start_sec"], "end": row["window_end_sec"],
                         "size": row["input_size"], "frames": row["frames"]}, sort_keys=True).encode()).hexdigest()
            audit.check(row["input_sha256"] == fingerprint, "vlm_input_fingerprint", location)
            audit.check(row["processor_resize"] is False and row["processor_sampling"] is False,
                        "vlm_no_hidden_resampling", location)
            if "window_id" not in row:
                audit.check("auxiliary_context" not in row, "refinement_visual_only_context", location)
                continue
            key = (video, row["window_id"])
            previous = baseline.get(key)
            audit.check(previous is not None and row["input_sha256"] == previous["input_sha256"]
                        and row["frames"] == previous["frames"] and row["input_size"] == previous["input_size"],
                        "same_baseline_fullframe_inputs", location)
            values = base_scores[key]["queries"]
            audit.check(set(values) == set(queries) and all(values[code]["question"] == queries[code] for code in queries),
                        "all_queries_no_retrieval_gate", location)
            audit.check(len(row["actual_prompt_token_counts"]) == len(row["actual_visual_token_counts"]) == 28,
                        "actual_all_28_prompt_inputs", location)
            for i, code in enumerate(queries):
                audit.check(values[code]["prompt_tokens"] == row["actual_prompt_token_counts"][i]
                            and values[code]["visual_tokens"] == row["actual_visual_token_counts"][i], "query_token_metadata", location)
            retr = retrieval[key]
            audit.check(row["auxiliary_context"] == retr["context"] and hashlib.sha256(retr["context"].encode()).hexdigest()
                        == retr["context_sha256"], "retrieval_context_identity", location)
            ranked = retr["ranking"]
            audit.check(len(ranked) == 64 and {x["rule_id"] for x in ranked} == set(expected_codes)
                        and [x["rank"] for x in ranked] == list(range(1, 65)), "all_64_ranked_per_window", location)
            audit.check(all(finite(x["cosine_score"]) and abs(x["cosine_score"]) <= 1.00001 for x in ranked)
                        and ranked == sorted(ranked, key=lambda x: (-x["cosine_score"], x["rule_id"])), "cosine_score_order_bounds", location)
            start, end = retr["window_start_sec"], retr["window_end_sec"]
            audit.check((start, end) == bounds(manifest[video]["duration_sec"])[row["window_id"]]
                        and (start, end) == (row["window_start_sec"], row["window_end_sec"]), "retrieval_window_bounds", location)
            selected = []
            for target in (start + i for i in range(math.ceil(end - start))):
                match = next((frame for frame in detections[video] if frame["time_sec"] >= target - 1e-8), None)
                if match is not None and match["time_sec"] < end - 1e-8 and match["source_frame_index"] not in selected:
                    selected.append(match["source_frame_index"])
            audit.check([f["source_frame_index"] for f in retr["frames"]] == selected, "retrieval_exact_1fps_selection", location)
            for frame in retr["frames"]:
                match = source.get(frame["source_frame_index"])
                audit.check(match is not None and frame["pts"] == match["source_pts"] and frame["time_base"] == match["time_base"]
                            and frame["sha256_rgb"] == match["sha256_rgb"] and frame["time_sec"] == match["time_sec"],
                            "retrieval_source_frame_identity", location)
            processor = retr["processor"]
            audit.check(processor["input_rgb_sha256"] == [f["sha256_rgb"] for f in retr["frames"]]
                        and processor["actual_frame_counts"] == [len(retr["frames"])]
                        and processor["input_rgb_shapes"] == [[row["input_size"][1], row["input_size"][0], 3]] * len(retr["frames"]),
                        "retrieval_processor_frame_identity", location)
            audit.check(processor["processor_sampling"] is False and processor["truncation"] is False
                        and processor["audio_enabled"] is False and processor["add_timestamps"] is False
                        and retr["hard_gate"] is False, "retrieval_no_hidden_sampling_truncation_gate", location)
            context = json.loads(retr["context"].split("\n", 1)[1])
            audit.check([x["rule_id"] for x in context["retrieved_rules"]] == [x["rule_id"] for x in ranked[:5]],
                        "prompt_top_5_only_as_context", location)
            track_summary = retr["track_summary"]
            audit.check(context["observed_object_tracks"] == track_summary and len(track_summary["tracks"]) <= 16
                        and track_summary["omitted_from_prompt"] == track_summary["total_tracks"] - len(track_summary["tracks"]),
                        "prompt_track_limit_and_omissions", location)
            observed = defaultdict(list)
            for frame in detections[video]:
                if start <= frame["time_sec"] < end:
                    for det in frame["detections"]:
                        if det["track_id"] is not None:
                            observed[det["track_id"]].append((frame["time_sec"], det))
            reconstructed = []
            for identity, observations in observed.items():
                reconstructed.append({"track_id": identity, "class_name": observations[0][1]["class_name"],
                    "first_observation": {"time_sec": observations[0][0], "bbox_xyxy": observations[0][1]["bbox_xyxy"]},
                    "last_observation": {"time_sec": observations[-1][0], "bbox_xyxy": observations[-1][1]["bbox_xyxy"]},
                    "observations": len(observations), "maximum_detector_score": max(x[1]["score"] for x in observations)})
            reconstructed.sort(key=lambda x: (-x["observations"], -x["maximum_detector_score"], x["track_id"]))
            audit.check(track_summary["tracks"] == reconstructed[:16] and track_summary["total_tracks"] == len(reconstructed),
                        "track_context_only_actual_observations", location)
        prediction_map = {row["video_id"]: row for row in predictions}
        timing_map = {row["video_id"]: row for row in timings}
        audit.check(len(predictions) == len(prediction_map) == len(timings) == len(timing_map) == 40
                    and set(prediction_map) == set(timing_map) == set(run["video_ids"]), "all_video_result_rows")
        for video, prediction in prediction_map.items():
            audit.check(timing_map[video] == {k: v for k, v in prediction.items() if k not in ("events", "score")},
                        "timing_prediction_identity", video)
            audit.check(prediction["status"] == "done" and prediction["complete"] is True
                        and prediction.get("timed_out") is False, "completed_video_status", video)
            audit.check(finite(prediction["elapsed_sec"]) and 0 <= prediction["elapsed_sec"] < run["arguments"]["deadline_seconds"],
                        "local_pipeline_within_deadline", video)
            if "enrichment" not in prediction:
                audit.check(False, "enrichment_timing_present", video)
                continue
            timing = prediction["enrichment"]
            frame_rows = detections[video]
            audit.check(timing["detected_frames"] == len(frame_rows)
                        and timing["detections"] == sum(len(x["detections"]) for x in frame_rows)
                        and timing["retrieval_windows"] == sum(key[0] == video for key in retrieval),
                        "enrichment_logged_counts", video)
            audit.check(all(finite(timing[k]) and timing[k] >= 0 for k in
                            ("detection_tracking_seconds", "embedding_retrieval_seconds", "enrichment_seconds"))
                        and close(timing["enrichment_seconds"], timing["detection_tracking_seconds"] + timing["embedding_retrieval_seconds"], 0.01)
                        and timing["enrichment_seconds"] <= prediction["base_detection_elapsed_sec"]
                        and prediction["decode_seconds"] + timing["enrichment_seconds"] <= prediction["base_detection_elapsed_sec"] + 0.01
                        and prediction["base_detection_elapsed_sec"] + prediction["localization_stage_elapsed_sec"] <= prediction["elapsed_sec"] + 0.01,
                        "nested_stage_wall_times", video)
            video_scores = [row for row in scores if row["video_id"] == video]
            audit.check(prediction["num_requests"] == sum(len(x["queries"]) for x in video_scores), "request_count", video)
            audit.check(prediction["num_cached_tokens"] == sum(q["num_cached_tokens"] or 0 for x in video_scores for q in x["queries"].values()),
                        "cached_token_count", video)
        load_seconds = run["model_load_seconds"] + run["enrichment"]["model_and_index_load_seconds"]
        audit.check(finite(run["model_load_seconds"]) and run["model_load_seconds"] >= 0
                    and finite(run["enrichment"]["model_and_index_load_seconds"])
                    and run["enrichment"]["model_and_index_load_seconds"] >= 0, "model_load_timing_metadata")
        elapsed_run = (datetime.fromisoformat(run["finished_at_utc"]) - datetime.fromisoformat(run["created_at_utc"])).total_seconds()
        audit.check(elapsed_run + 0.1 >= load_seconds + sum(x["elapsed_sec"] for x in predictions), "run_walltime_contains_load_and_videos")
        if args.verify_source_rgb:
            report["source_verification"] = verify_sources(args, run, manifest, detections, audit)
        report["summary"] = {"videos": len(predictions), "base_windows": len(base_inputs), "base_queries": sum(len(x["queries"]) for x in base_scores.values()),
            "all_logged_queries": sum(len(x["queries"]) for x in scores), "retrieval_windows": len(retrieval),
            "detection_frames": sum(len(x) for x in detections.values()), "detections": total_detections, "tracked_observations": total_tracked,
            "embedding_shape": list(vectors.shape), "embedding_norm_min": finite_stat(norms.min()), "embedding_norm_max": finite_stat(norms.max()),
            "status_counts": dict(Counter(x["status"] for x in predictions))}
        report["artifact_sha256"] = {name: digest(args.run / name) for name in
                                    ("run.json", "rule_index.json", "rule_embeddings.npy", "inputs.jsonl", "scores.jsonl",
                                     "retrieval.jsonl", "detections.jsonl", "predictions.jsonl", "timings.jsonl")}
    except Exception as error:
        import traceback
        audit.check(False, "audit_exception", details={"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
    return finish(report, audit, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
