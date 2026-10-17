import { z } from "zod";

/** Control surface of the mock analyzer. Developer tooling only, not part of the product contract. */
export const DevScenarioSchema = z.strictObject({
	health: z.enum(["ok", "gpu_error", "gpu_unknown", "backend_error", "slow"]),
	outcome: z.enum(["auto", "violation", "no_violation", "failed"]),
});
export type DevScenario = z.infer<typeof DevScenarioSchema>;
