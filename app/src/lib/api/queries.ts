import { queryOptions } from "@tanstack/react-query";
import { isApiError } from "./client";
import { POLL_INTERVAL_MS } from "./contracts.ts";
import { HEALTH_POLL_INTERVAL_MS } from "./health-contracts.ts";
import { getAllViolations, getHealth, getJob } from "./review";

const STOP_STATUSES = new Set([401, 404]);

/** Health plus the round-trip time of the request that produced it. */
export const healthQuery = () =>
	queryOptions({
		queryKey: ["health"],
		queryFn: async ({ signal }) => {
			const startedAt = performance.now();
			const health = await getHealth(signal);
			return { health, latencyMs: Math.round(performance.now() - startedAt) };
		},
		refetchInterval: HEALTH_POLL_INTERVAL_MS,
		retry: false,
		staleTime: 0,
	});

/**
 * Polls every 2 s while the job is processing. It stops on a terminal status,
 * or on 401/404. Queue waiting does not stop polling.
 * Transient errors keep the last good state and the interval keeps running.
 */
export const jobQuery = (jobId: string, _createdAt: number | null) =>
	queryOptions({
		queryKey: ["job", jobId],
		queryFn: ({ signal }) => getJob(jobId, signal),
		refetchInterval: (query) => {
			const { data, error } = query.state;
			if (isApiError(error) && STOP_STATUSES.has(error.status)) return false;
			if (data && data.status !== "processing") return false;

			return POLL_INTERVAL_MS;
		},
		retry: (count, error) =>
			!(isApiError(error) && STOP_STATUSES.has(error.status)) && count < 2,
	});

export const violationsQuery = (jobId: string) =>
	queryOptions({
		queryKey: ["violations", jobId],
		queryFn: ({ signal }) => getAllViolations(jobId, signal),
		// The completed result is immutable.
		staleTime: Number.POSITIVE_INFINITY,
	});
