import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import * as examples from "./contract-examples.ts";
import {
	AnalyzeAcceptedSchema,
	ApiErrorResponseSchema,
	CompletedReviewSchema,
	JobResponseSchema,
	JobViewSchema,
	PaginationQuerySchema,
	ViolationsPageSchema,
} from "./contracts.ts";
import {
	HealthResponseSchema,
	HealthyHealthSchema,
	UnhealthyHealthSchema,
} from "./health-contracts.ts";
import { JuryJobResponseSchema } from "./jury-contracts.ts";

test("health distinguishes readiness, GPU failure and an unobservable GPU behind a failed backend", () => {
	for (const example of [
		examples.healthyExample,
		examples.gpuUnavailableExample,
		examples.backendUnavailableExample,
	]) {
		assert.deepEqual(HealthResponseSchema.parse(example), example);
	}
	assert.equal(
		HealthyHealthSchema.safeParse(examples.healthyExample).success,
		true,
	);
	assert.equal(
		HealthyHealthSchema.safeParse(examples.gpuUnavailableExample).success,
		false,
	);
	assert.equal(
		UnhealthyHealthSchema.safeParse(examples.healthyExample).success,
		false,
	);
	assert.equal(
		UnhealthyHealthSchema.safeParse(examples.gpuUnavailableExample).success,
		true,
	);
	assert.equal(
		UnhealthyHealthSchema.safeParse(examples.backendUnavailableExample).success,
		true,
	);
	assert.equal(
		HealthResponseSchema.safeParse({
			...examples.backendUnavailableExample,
			services: {
				backend: examples.backendUnavailableExample.services.backend,
				gpu_server: examples.healthyExample.services.gpu_server,
			},
		}).success,
		true,
	);
});

test("health rejects contradictory aggregates and missing or invalid check times", () => {
	for (const payload of [
		{ ...examples.gpuUnavailableExample, status: "ok" },
		{ ...examples.healthyExample, status: "degraded" },
		{ ...examples.healthyExample, status: "unavailable" },
		{ ...examples.backendUnavailableExample, status: "degraded" },
		{ ...examples.healthyExample, checked_at: "2026-10-17" },
		{ ...examples.healthyExample, checked_at: undefined },
		{
			...examples.healthyExample,
			services: { backend: examples.healthyExample.services.backend },
		},
		{
			...examples.healthyExample,
			services: {
				...examples.healthyExample.services,
				gpu_server: { status: "ok", message: " " },
			},
		},
	])
		assert.equal(HealthResponseSchema.safeParse(payload).success, false);
});

const {
	processingExample,
	noViolationExample,
	violationExample,
	failedExample,
	violationsPageExample,
	secondPageExample,
} = examples;

test("all UI/jury states and event page examples validate", () => {
	assert.deepEqual(
		AnalyzeAcceptedSchema.parse(examples.acceptedExample),
		examples.acceptedExample,
	);
	assert.deepEqual(
		ApiErrorResponseSchema.parse(examples.unauthorizedExample),
		examples.unauthorizedExample,
	);
	for (const example of [
		processingExample,
		noViolationExample,
		violationExample,
		failedExample,
	]) {
		assert.deepEqual(JobResponseSchema.parse(example), example);
	}
	for (const example of [
		examples.juryProcessingExample,
		examples.juryNoViolationExample,
		examples.juryViolationExample,
		examples.juryFailedExample,
	]) {
		assert.deepEqual(JuryJobResponseSchema.parse(example), example);
	}
	for (const example of [
		violationsPageExample,
		secondPageExample,
		examples.emptyPageExample,
	]) {
		assert.deepEqual(ViolationsPageSchema.parse(example), example);
	}
});

test("overview is mandatory for both completed verdicts and absent before completion", () => {
	const { overview: _, ...withoutOverview } = violationExample;
	for (const payload of [
		withoutOverview,
		{ ...noViolationExample, overview: null },
		{ ...violationExample, overview: { summary: " ", limitations: [] } },
		{ ...violationExample, overview: { summary: "Review", limitations: [""] } },
		{ ...violationExample, violations_count: 0 },
		{ ...noViolationExample, violations_count: 1 },
		{ ...violationExample, verdict: "insufficient_data" },
		{ ...processingExample, overview: violationExample.overview },
		{ ...failedExample, verdict: "no_violation" },
		{
			...violationExample,
			violations: examples.juryViolationExample.violations,
		},
	])
		assert.equal(JobResponseSchema.safeParse(payload).success, false);
});

test("backend-defined stage IDs and labels are accepted without a client taxonomy", () => {
	assert.equal(
		JobResponseSchema.safeParse({
			...processingExample,
			progress: {
				percent: 12.5,
				stages: [
					{
						id: "new_backend_step",
						label: "Новый этап",
						description: "Описание от бэка",
						status: "running",
						percent: 12.5,
					},
				],
			},
		}).success,
		true,
	);
	assert.equal(
		JobResponseSchema.safeParse({
			...processingExample,
			progress: {
				percent: 0,
				stages: processingExample.progress.stages.map((stage) => ({
					...stage,
					status: "pending",
					percent: 0,
				})),
			},
		}).success,
		true,
	);
});

test("progress cannot contradict the job or ordered stage state", () => {
	const stages = processingExample.progress.stages;
	for (const payload of [
		{
			...processingExample,
			progress: { ...processingExample.progress, percent: 100 },
		},
		{
			...processingExample,
			progress: { ...processingExample.progress, percent: -1 },
		},
		{
			...processingExample,
			progress: { ...processingExample.progress, percent: Number.NaN },
		},
		{ ...processingExample, progress: { percent: 20, stages: [] } },
		{
			...processingExample,
			progress: {
				percent: 20,
				stages: [stages[1], { ...stages[1], id: "another" }],
			},
		},
		{
			...processingExample,
			progress: {
				percent: 20,
				stages: [stages[0], { ...stages[1], id: stages[0].id }],
			},
		},
		{
			...processingExample,
			progress: { percent: 20, stages: [...stages].reverse() },
		},
		{
			...processingExample,
			progress: { percent: 20, stages: [{ ...stages[1], percent: 100 }] },
		},
		{
			...processingExample,
			progress: { percent: 20, stages: [{ ...stages[2], percent: 10 }] },
		},
		{ ...processingExample, progress: { percent: 20, stages: [stages[2]] } },
		{ ...processingExample, progress: failedExample.progress },
		{
			...processingExample,
			progress: { ...violationExample.progress, percent: 99 },
		},
		{
			...violationExample,
			progress: { ...processingExample.progress, percent: 100 },
		},
		{
			...violationExample,
			progress: { ...violationExample.progress, percent: 99 },
		},
		{ ...failedExample, progress: processingExample.progress },
	])
		assert.equal(JobResponseSchema.safeParse(payload).success, false);
});

test("pagination handles defaults, exact/partial final pages, empty and beyond-end results", () => {
	assert.deepEqual(PaginationQuerySchema.parse({}), { page: 1, page_size: 20 });
	for (const query of [
		{ page: 0 },
		{ page: 1.5 },
		{ page_size: 0 },
		{ page_size: 101 },
		{ page: "1" },
		{ cursor: "x" },
	]) {
		assert.equal(PaginationQuerySchema.safeParse(query).success, false);
	}
	const items = [...violationsPageExample.items, ...secondPageExample.items];
	assert.equal(
		ViolationsPageSchema.safeParse({
			...violationsPageExample,
			page_size: 20,
			items,
		}).success,
		true,
	);
	assert.equal(
		ViolationsPageSchema.safeParse({ ...secondPageExample, page: 3, items: [] })
			.success,
		true,
	);
	for (const page of [
		{ ...violationsPageExample, items: [] },
		{ ...violationsPageExample, page_size: 20 },
		{ ...violationsPageExample, total: 0 },
		{ ...violationsPageExample, page: 3 },
		{ ...violationsPageExample, page_size: 2, items: [items[0], items[0]] },
		{ ...violationsPageExample, page_size: 2, items: [...items].reverse() },
	])
		assert.equal(ViolationsPageSchema.safeParse(page).success, false);
	const tied = [
		{ ...items[0], timecode_sec: 10 },
		{ ...items[1], timecode_sec: 10 },
	];
	assert.equal(
		ViolationsPageSchema.safeParse({
			...violationsPageExample,
			page_size: 2,
			items: tied,
		}).success,
		true,
	);
	assert.equal(
		ViolationsPageSchema.safeParse({
			...violationsPageExample,
			page_size: 2,
			items: tied.reverse(),
		}).success,
		false,
	);
});

test("pages must belong to the displayed overview and agree on total events", () => {
	for (const page of [violationsPageExample, secondPageExample]) {
		assert.equal(
			CompletedReviewSchema.safeParse({ job: violationExample, page }).success,
			true,
		);
	}
	assert.equal(
		CompletedReviewSchema.safeParse({
			job: noViolationExample,
			page: examples.emptyPageExample,
		}).success,
		true,
	);
	for (const page of [
		{ ...violationsPageExample, job_id: "other_job" },
		{ ...violationsPageExample, total: 3 },
	]) {
		assert.equal(
			CompletedReviewSchema.safeParse({ job: violationExample, page }).success,
			false,
		);
	}
});

test("UI events include timecodes and rules but reject inline JPEG payloads", () => {
	const event = violationsPageExample.items[0];
	const frame = event.evidence_frames[0];
	for (const invalidEvent of [
		{ ...event, timecode_sec: -1 },
		{ ...event, timecode_sec: "44.2" },
		{ ...event, description: " " },
		{ ...event, evidence_frames: [] },
		{ ...event, evidence_frames: [frame, frame] },
		{ ...event, evidence_frames: [{ ...frame, image_base64: "/9j/" }] },
		{ ...event, rule: { ...event.rule, sources: [] } },
		{
			...event,
			rule: {
				...event.rule,
				sources: [{ ...event.rule.sources[0], url: "javascript:alert(1)" }],
			},
		},
	])
		assert.equal(
			ViolationsPageSchema.safeParse({
				...violationsPageExample,
				items: [invalidEvent],
			}).success,
			false,
		);
});

test("mandatory jury result preserves complete JPEG/base64 evidence across all UI pages", () => {
	assert.equal(JobViewSchema.parse(undefined), "jury");
	assert.deepEqual(Object.keys(examples.juryViolationExample).sort(), [
		"job_id",
		"status",
		"verdict",
		"violations",
	]);
	const pagedEvents = [
		...violationsPageExample.items,
		...secondPageExample.items,
	];
	assert.equal(
		examples.juryViolationExample.violations.length,
		violationExample.violations_count,
	);
	pagedEvents.forEach((event, index) => {
		const juryEvent = examples.juryViolationExample.violations[index];
		assert.equal(juryEvent.timecode_sec, event.timecode_sec);
		assert.equal(juryEvent.description, event.description);
		assert.equal(juryEvent.type, event.type);
		const jpeg = Buffer.from(
			juryEvent.evidence_frames[0].image_base64,
			"base64",
		);
		assert.equal(jpeg.subarray(0, 2).toString("hex"), "ffd8");
		assert.equal(jpeg.subarray(-2).toString("hex"), "ffd9");
	});
	const event = examples.juryViolationExample.violations[0];
	for (const invalidEvent of [
		{ ...event, evidence_frames: [] },
		{ ...event, evidence_frames: Array(4).fill(event.evidence_frames[0]) },
		{
			...event,
			evidence_frames: [{ timestamp_sec: 44.2, image_base64: "invalid!" }],
		},
	])
		assert.equal(
			JuryJobResponseSchema.safeParse({
				...examples.juryViolationExample,
				violations: [invalidEvent],
			}).success,
			false,
		);
	assert.equal(
		JuryJobResponseSchema.safeParse({
			...examples.juryNoViolationExample,
			violations: [event],
		}).success,
		false,
	);
});

test("OpenAPI references resolve, pagination is documented and obsolete rules endpoint is removed", async () => {
	const document = JSON.parse(
		await readFile(
			new URL("../../../../docs/openapi.json", import.meta.url),
			"utf8",
		),
	);
	assert.equal(document.paths["/jobs/{job_id}/rules"], undefined);
	assert.deepEqual(
		document.paths["/jobs/{job_id}/violations"].get.parameters.map(
			(parameter: { name: string }) => parameter.name,
		),
		["page", "page_size"],
	);
	function visit(value: unknown): void {
		if (!value || typeof value !== "object") return;
		for (const [key, child] of Object.entries(value)) {
			if (key === "$ref") {
				assert.equal(typeof child, "string");
				assert.match(child, /^#\//);
				let target: unknown = document;
				for (const segment of child.slice(2).split("/")) {
					assert.ok(target && typeof target === "object");
					target = (target as Record<string, unknown>)[
						segment.replaceAll("~1", "/").replaceAll("~0", "~")
					];
				}
				assert.ok(target, `Missing reference: ${child}`);
			} else visit(child);
		}
	}
	visit(document);
});
