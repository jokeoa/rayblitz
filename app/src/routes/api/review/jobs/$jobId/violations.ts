import { createFileRoute } from "@tanstack/react-router";
import { ViolationsPageSchema } from "@/lib/api/contracts";
import { isResourceId, parsePaginationQuery } from "@/lib/api/query";
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

export const Route = createFileRoute("/api/review/jobs/$jobId/violations")({
	server: {
		handlers: {
			GET: async ({ request, params }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				const query = parsePaginationQuery(new URL(request.url));
				if (!query || !isResourceId(params.jobId)) {
					return errorResponse(
						400,
						"BAD_REQUEST",
						"Некорректные параметры страницы.",
					);
				}

				let upstream: Response;
				try {
					upstream = await upstreamFetch(
						`/jobs/${encodeURIComponent(params.jobId)}/violations?page=${query.page}&page_size=${query.page_size}`,
						auth.apiKey,
					);
				} catch (error) {
					if (error instanceof UpstreamUnreachable)
						return upstreamUnavailable();
					throw error;
				}

				if (upstream.status !== 200) return forwardError(upstream);
				const page = await parseUpstream(upstream, ViolationsPageSchema);
				return page ? jsonResponse(page) : contractViolation();
			},
		},
	},
});
