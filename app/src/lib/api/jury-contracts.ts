import { z } from "zod";
import {
	AnalysisFailureSchema,
	JobIdSchema,
	TimestampSchema,
	ViolationDetailsSchema,
} from "./contracts.ts";

// Required by section 10 of the case. This is a current external consumer,
// not a legacy UI format. The UI uses contracts.ts and never gets base64 frames.
export const JuryEvidenceFrameSchema = z.strictObject({
	timestamp_sec: TimestampSchema,
	image_base64: z.base64().min(4).meta({
		contentMediaType: "image/jpeg",
		description:
			"JPEG bytes in standard base64, without a data URL prefix. Server must verify JPEG decoding.",
	}),
});
export const JuryViolationSchema = ViolationDetailsSchema.extend({
	evidence_frames: z.array(JuryEvidenceFrameSchema).min(1).max(3),
});
export const JuryProcessingJobSchema = z.strictObject({
	job_id: JobIdSchema,
	status: z.literal("processing"),
});
export const JuryFailedJobSchema = z.strictObject({
	job_id: JobIdSchema,
	status: z.literal("failed"),
	error: AnalysisFailureSchema,
});
export const JuryNoViolationJobSchema = z.strictObject({
	job_id: JobIdSchema,
	status: z.literal("done"),
	verdict: z.literal("no_violation"),
	violations: z.array(JuryViolationSchema).max(0),
});
export const JuryViolationJobSchema = z.strictObject({
	job_id: JobIdSchema,
	status: z.literal("done"),
	verdict: z.literal("violation"),
	violations: z.array(JuryViolationSchema).min(1),
});
export const JuryJobResponseSchema = z.discriminatedUnion("status", [
	JuryProcessingJobSchema,
	z.discriminatedUnion("verdict", [
		JuryNoViolationJobSchema,
		JuryViolationJobSchema,
	]),
	JuryFailedJobSchema,
]);
export type JuryJobResponse = z.infer<typeof JuryJobResponseSchema>;
