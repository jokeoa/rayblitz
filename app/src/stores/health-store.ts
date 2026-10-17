import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { HealthResponse } from "@/lib/api/health-contracts";
import { DEV_TOOLS } from "@/lib/app-mode";

type ServiceStatus = "ok" | "error" | "unknown";

/** One completed poll. `reachable: false` means our own server did not answer. */
export type HealthSample = {
	at: number;
	reachable: boolean;
	overall: HealthResponse["status"] | "unknown";
	backend: ServiceStatus;
	gpu: ServiceStatus;
	latencyMs: number | null;
};

const MAX_SAMPLES = 60;

type HealthState = {
	samples: HealthSample[];
	record: (sample: HealthSample) => void;
};

/**
 * Client-side history of the 10 s health polls. The contract returns statuses
 * only, so latency and availability are measured here from the real requests.
 */
export const useHealthStore = create<HealthState>()(
	devtools(
		(set) => ({
			samples: [],
			record: (sample) =>
				set((state) => ({
					samples: [...state.samples, sample].slice(-MAX_SAMPLES),
				})),
		}),
		{ name: "health", enabled: DEV_TOOLS },
	),
);
