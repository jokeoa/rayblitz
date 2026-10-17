import assert from "node:assert/strict";
import { test } from "node:test";
import type { Violation } from "./api/contracts.ts";
import {
	buildLanes,
	markerTargets,
	rulerTicks,
	segmentOf,
} from "./timeline.ts";

const rule = {
	text: "Правило",
	sources: [
		{
			document_title: "Источник",
			section: null,
			url: "https://example.invalid/x",
		},
	],
};

function violation(id: string, type: string, times: number[]): Violation {
	return {
		id,
		type,
		timecode_sec: times[0],
		description: "Описание",
		rule,
		evidence_frames: times.map((timestamp_sec, index) => ({
			frame_id: `f${index}`,
			timestamp_sec,
		})),
	};
}

test("an event spans from its earliest to its latest evidence frame", () => {
	const segment = segmentOf(violation("a", "T", [12, 10, 14]));
	assert.equal(segment.start, 10);
	assert.equal(segment.end, 14);
});

test("lanes follow violation types in order of first appearance", () => {
	const lanes = buildLanes(
		[
			violation("a", "B", [30]),
			violation("b", "A", [5]),
			violation("c", "B", [60]),
		],
		1,
	);
	assert.deepEqual(
		lanes.map((lane) => lane.type),
		["A", "B"],
	);
});

test("overlapping events of one type stack into rows, distant ones share a row", () => {
	const [lane] = buildLanes(
		[
			violation("a", "T", [10, 15]),
			violation("b", "T", [12, 18]),
			violation("c", "T", [40]),
		],
		1,
	);
	assert.equal(lane.rows.length, 2);
	assert.deepEqual(
		lane.rows[0].map((segment) => segment.violation.id),
		["a", "c"],
	);
	assert.deepEqual(
		lane.rows[1].map((segment) => segment.violation.id),
		["b"],
	);
});

test("point events closer than the minimum span do not share a row", () => {
	const [lane] = buildLanes(
		[violation("a", "T", [10]), violation("b", "T", [10.5])],
		2,
	);
	assert.equal(lane.rows.length, 2);
});

test("ruler keeps the label count within the budget", () => {
	assert.deepEqual(rulerTicks(0), []);
	assert.ok(rulerTicks(90, 10).length <= 10);
	assert.ok(rulerTicks(90, 3).length <= 3);
	assert.equal(rulerTicks(90, 10)[0], 0);
});

const layout = {
	duration: 100,
	trackWidth: 1000,
	minWidth: 14,
	swell: 0.3,
	barge: 4,
	shrink: 0.05,
};

test("the chosen marker swells and the rest shrink", () => {
	const lanes = buildLanes(
		[violation("a", "A", [10]), violation("b", "B", [50])],
		0,
	);
	const targets = markerTargets(lanes, "a", layout);
	assert.equal(targets.get("a")?.scale, 1.3);
	assert.equal(targets.get("b")?.scale, 0.95);
	assert.equal(targets.get("a")?.far, 0);
	assert.equal(targets.get("b")?.far, 1);
});

test("markers rest in place when nothing is chosen", () => {
	const lanes = buildLanes([violation("a", "A", [10])], 0);
	for (const id of [null, "missing"])
		assert.deepEqual(markerTargets(lanes, id, layout).get("a"), {
			x: 0,
			scale: 1,
			far: 0,
		});
});

test("only same-row neighbours the swell would overlap step aside", () => {
	const lanes = buildLanes(
		[
			violation("left", "A", [9.5]),
			violation("mid", "A", [10]),
			violation("right", "A", [10.5]),
			violation("far", "A", [60]),
			violation("other", "B", [10]),
		],
		0,
	);
	const targets = markerTargets(lanes, "mid", layout);
	assert.ok((targets.get("left")?.x ?? 0) < 0);
	assert.ok((targets.get("right")?.x ?? 0) > 0);
	assert.equal(targets.get("far")?.x, 0);
	assert.equal(targets.get("other")?.x, 0);
});
