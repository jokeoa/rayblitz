import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import type { HealthResponse } from "@/lib/api/health-contracts";
import { healthQuery } from "@/lib/api/queries";
import { useHealthStore } from "@/stores/health-store";

export type HealthKind = "checking" | HealthResponse["status"] | "unknown";

export type HealthView = {
	kind: HealthKind;
	health: HealthResponse | null;
	latencyMs: number | null;
	/** Analysis may only start when both services are confirmed ready. */
	canAnalyze: boolean;
	isFetching: boolean;
	refetch: () => void;
};

/**
 * `unknown` is the local "status unknown" state from the contract: our own
 * server did not answer, so a previous green result is never shown as current.
 */
export function useHealth(): HealthView {
	const query = useQuery(healthQuery());
	const kind: HealthKind = query.isError
		? "unknown"
		: query.data
			? query.data.health.status
			: "checking";
	return {
		kind,
		health: query.isError ? null : (query.data?.health ?? null),
		latencyMs: query.isError ? null : (query.data?.latencyMs ?? null),
		canAnalyze: kind === "ok",
		isFetching: query.isFetching,
		refetch: () => void query.refetch(),
	};
}

/** Mounted once in the app shell: turns every poll into one stored sample. */
export function useHealthRecorder() {
	const query = useQuery(healthQuery());
	const record = useHealthStore((state) => state.record);
	const lastSeen = useRef({ data: 0, error: 0 });

	useEffect(() => {
		if (query.dataUpdatedAt && query.dataUpdatedAt !== lastSeen.current.data) {
			lastSeen.current.data = query.dataUpdatedAt;
			if (query.data) {
				const { health, latencyMs } = query.data;
				record({
					at: query.dataUpdatedAt,
					reachable: true,
					overall: health.status,
					backend: health.services.backend.status,
					gpu: health.services.gpu_server.status,
					latencyMs,
				});
			}
		}
		if (
			query.errorUpdatedAt &&
			query.errorUpdatedAt !== lastSeen.current.error
		) {
			lastSeen.current.error = query.errorUpdatedAt;
			record({
				at: query.errorUpdatedAt,
				reachable: false,
				overall: "unknown",
				backend: "unknown",
				gpu: "unknown",
				latencyMs: null,
			});
		}
	}, [query.dataUpdatedAt, query.errorUpdatedAt, query.data, record]);
}
