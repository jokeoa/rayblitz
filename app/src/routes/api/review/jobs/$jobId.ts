import { createFileRoute } from "@tanstack/react-router";
import { JobResponseSchema } from "@/lib/api/contracts";
import { isResourceId } from "@/lib/api/query";
import {
	authorize,
	contractViolation,
	errorResponse,
	forwardError,
	jsonResponse,
	parseUpstream,
	UpstreamUnreachable,
	upstreamFetch,
	upstreamUnavailable,
} from "@/server/upstream";

export const Route = createFileRoute("/api/review/jobs/$jobId")({
	server: {
		handlers: {
			GET: async ({ request, params }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				// The browser boundary always asks for `view=ui`; no query is accepted.
				if (
					new URL(request.url).searchParams.size > 0 ||
					!isResourceId(params.jobId)
				) {
					return errorResponse(400, "BAD_REQUEST", "Некорректный запрос.");
				}

				let upstream: Response;
				try {
					upstream = await upstreamFetch(
						`/jobs/${encodeURIComponent(params.jobId)}?view=ui`,
						auth.apiKey,
					);
				} catch (error) {
					if (error instanceof UpstreamUnreachable)
						return upstreamUnavailable();
					throw error;
				}

				if (upstream.status !== 200) return forwardError(upstream);
				const job = await parseUpstream(upstream, JobResponseSchema);
				return job ? jsonResponse(job) : contractViolation();
			},
		},
	},
});
