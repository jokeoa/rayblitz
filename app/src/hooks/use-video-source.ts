export type VideoSource =
	| { state: "loading"; url: null }
	| { state: "ready"; url: string }
	| { state: "missing"; url: null };

/** Authenticated server playback supports seeking and survives browser restarts. */
export function useVideoSource(jobId: string, preparing = false): VideoSource {
	return preparing
		? { state: "loading", url: null }
		: {
				state: "ready",
				url: `/api/review/jobs/${encodeURIComponent(jobId)}/video`,
			};
}
