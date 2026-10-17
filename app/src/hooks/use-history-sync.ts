import { useQueries } from "@tanstack/react-query";
import { useEffect } from "react";
import { isApiError } from "@/lib/api/client";
import { jobQuery } from "@/lib/api/queries";
import { useHistoryStore } from "@/stores/history-store";

/**
 * Keeps the history list truthful: every job that is still processing is
 * polled (2 s, one request at a time per job) and its progress and terminal
 * state are written back, even while the user is on another page.
 */
export function useHistorySync() {
	const entries = useHistoryStore((state) => state.entries);
	const update = useHistoryStore((state) => state.update);
	const active = entries.filter((entry) => entry.status === "processing");

	const results = useQueries({
		queries: active.map((entry) => jobQuery(entry.jobId, entry.createdAt)),
	});

	const signature = results
		.map((result) => `${result.dataUpdatedAt}:${result.errorUpdatedAt}`)
		.join("|");

	// biome-ignore lint/correctness/useExhaustiveDependencies: `signature` captures every result change.
	useEffect(() => {
		results.forEach((result, index) => {
			const entry = active[index];
			if (!entry) return;
			const job = result.data;
			if (job) {
				if (job.status === "processing") {
					update(entry.jobId, { percent: job.progress.percent });
				} else if (job.status === "failed") {
					update(entry.jobId, {
						status: "failed",
						percent: job.progress.percent,
						errorCode: job.error.code,
					});
				} else {
					update(entry.jobId, {
						status: "done",
						percent: 100,
						verdict: job.verdict,
						violationsCount: job.violations_count,
					});
				}
			} else if (isApiError(result.error) && result.error.status === 404) {
				update(entry.jobId, { status: "failed", errorCode: "JOB_NOT_FOUND" });
			}
		});
	}, [signature]);
}
