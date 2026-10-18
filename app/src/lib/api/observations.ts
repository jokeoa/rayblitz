import { z } from "zod";
import { apiJson } from "./client";

export const HistorySchema = z.object({
	items: z.array(
		z.object({
			jobId: z.string(),
			fileName: z.string(),
			sizeBytes: z.number(),
			createdAt: z.number(),
			startedAt: z.number().nullable(),
			queued: z.boolean(),
			playbackReady: z.boolean(),
			status: z.enum(["processing", "done", "failed"]),
			percent: z.number(),
			verdict: z.enum(["violation", "no_violation"]).optional(),
			violationsCount: z.number().optional(),
			errorCode: z.string().optional(),
		}),
	),
});

const Box = z.tuple([z.number(), z.number(), z.number(), z.number()]);
const ObjectTrack = z.object({
	id: z.string().optional(),
	class: z.string(),
	box: Box,
	score: z.number(),
	semantic_status: z.string().optional(),
	resolution: z.object({ reason: z.string() }).passthrough().optional(),
});
const PersonTrack = z.object({
	id: z.number(),
	box: Box,
	person_id: z.string().nullable(),
	classification: z.object({
		role: z.string(),
		basis: z.string(),
		possible_reflection: z.boolean(),
	}),
	association: z.object({
		confidence: z.string(),
		usable_for_actions: z.boolean(),
	}),
});
const GeometryObject = z.object({
	box: Box,
	side_divider: z.array(z.tuple([z.number(), z.number()])).optional(),
});
export const ObservationsSchema = z.object({
	people: z
		.object({
			fps: z.number(),
			info: z.object({
				width: z.number(),
				height: z.number(),
				duration: z.number(),
			}),
			geometry: z.object({
				basis: z.string(),
				objects: z.object({
					desk: GeometryObject.nullable(),
					safe: GeometryObject.nullable(),
				}),
			}),
			rows: z.array(
				z.object({
					t: z.number(),
					tracks: z.array(PersonTrack),
					active_banker_person_id: z.string().nullable(),
				}),
			),
			people: z.record(
				z.string(),
				z.object({
					role: z.string(),
					initialized_at: z.number(),
					role_basis: z.string(),
				}),
			),
		})
		.nullable(),
	objects: z
		.object({
			fps: z.number(),
			limitation: z.string(),
			classes: z.array(z.object({ id: z.string(), name: z.string() })),
			rows: z.array(
				z.object({
					t: z.number(),
					tracks: z.array(ObjectTrack),
					raw: z.array(ObjectTrack),
					excluded: z.array(ObjectTrack),
				}),
			),
			intervals: z.array(
				z.object({
					id: z.union([z.string(), z.number()]),
					class: z.string(),
					observed_seconds: z.number(),
					intervals: z.array(z.tuple([z.number(), z.number()])),
				}),
			),
		})
		.nullable(),
});
export type Observations = z.infer<typeof ObservationsSchema>;
export const getHistory = (signal?: AbortSignal) =>
	apiJson("/api/review/jobs", HistorySchema, { signal });
export const getObservations = (jobId: string, signal?: AbortSignal) =>
	apiJson(
		`/api/review/jobs/${encodeURIComponent(jobId)}/observations`,
		ObservationsSchema,
		{ signal },
	);
