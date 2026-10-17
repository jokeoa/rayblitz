import { createFileRoute } from "@tanstack/react-router";
import { isResourceId } from "@/lib/api/query";
import {
	authorize,
	contractViolation,
	errorResponse,
	forwardError,
	NO_STORE,
	UpstreamUnreachable,
	upstreamFetch,
	upstreamUnavailable,
} from "@/server/upstream";

export const Route = createFileRoute(
	"/api/review/jobs/$jobId/violations/$violationId/frames/$frameId",
)({
	server: {
		handlers: {
			GET: async ({ request, params }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				const { jobId, violationId, frameId } = params;
				if (
					new URL(request.url).searchParams.size > 0 ||
					![jobId, violationId, frameId].every(isResourceId)
				) {
					return errorResponse(400, "BAD_REQUEST", "Некорректный запрос.");
				}

				let upstream: Response;
				try {
					upstream = await upstreamFetch(
						`/jobs/${encodeURIComponent(jobId)}/violations/${encodeURIComponent(violationId)}/frames/${encodeURIComponent(frameId)}`,
						auth.apiKey,
					);
				} catch (error) {
					if (error instanceof UpstreamUnreachable)
						return upstreamUnavailable();
					throw error;
				}

				if (upstream.status !== 200) return forwardError(upstream);
				if (!upstream.headers.get("content-type")?.startsWith("image/jpeg")) {
					return contractViolation();
				}
				return new Response(upstream.body, {
					status: 200,
					headers: { "Content-Type": "image/jpeg", "Cache-Control": NO_STORE },
				});
			},
		},
	},
});
