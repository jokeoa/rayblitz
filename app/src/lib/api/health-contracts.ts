import { z } from "zod";
import { TextSchema } from "./contracts.ts";

export const HEALTH_POLL_INTERVAL_MS = 10_000;
export const HEALTH_PROBE_TIMEOUT_MS = 2_000;
export const HEALTH_REQUEST_TIMEOUT_MS = 3_000;

export const ServiceHealthSchema = z.strictObject({
	status: z.enum(["ok", "error", "unknown"]),
	message: TextSchema.describe("Short, safe explanation suitable for the UI."),
});

const checkedAt = z.iso
	.datetime()
	.describe(
		"UTC timestamp when this check completed. Never reuse a stale successful check.",
	);
const healthyService = ServiceHealthSchema.extend({ status: z.literal("ok") });

export const HealthyHealthSchema = z.strictObject({
	status: z.literal("ok"),
	checked_at: checkedAt,
	services: z.strictObject({
		backend: healthyService,
		gpu_server: healthyService,
	}),
});

export const DegradedHealthSchema = z.strictObject({
	status: z.literal("degraded"),
	checked_at: checkedAt,
	services: z.strictObject({
		backend: healthyService,
		gpu_server: ServiceHealthSchema.extend({
			status: z.enum(["error", "unknown"]),
		}),
	}),
});

export const UnavailableHealthSchema = z.strictObject({
	status: z.literal("unavailable"),
	checked_at: checkedAt,
	services: z.strictObject({
		backend: ServiceHealthSchema.extend({ status: z.literal("error") }),
		gpu_server: ServiceHealthSchema,
	}),
});

export const UnhealthyHealthSchema = z.discriminatedUnion("status", [
	DegradedHealthSchema,
	UnavailableHealthSchema,
]);

export const HealthResponseSchema = z.discriminatedUnion("status", [
	HealthyHealthSchema,
	DegradedHealthSchema,
	UnavailableHealthSchema,
]);

export type ServiceHealth = z.infer<typeof ServiceHealthSchema>;
export type HealthResponse = z.infer<typeof HealthResponseSchema>;
