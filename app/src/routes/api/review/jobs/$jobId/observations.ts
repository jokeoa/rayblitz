import { createFileRoute } from "@tanstack/react-router";
import { ObservationsSchema } from "@/lib/api/observations";
import { isResourceId } from "@/lib/api/query";
import {
	authorize,
	errorResponse,
	jsonResponse,
	parseUpstream,
	upstreamFetch,
	forwardError,
	contractViolation,
	upstreamUnavailable,
} from "@/server/upstream";

export const Route = createFileRoute("/api/review/jobs/$jobId/observations")({
	server: {
		handlers: {
			GET: async ({ request, params }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				if (!isResourceId(params.jobId))
					return errorResponse(400, "BAD_REQUEST", "Некорректное задание.");
				try {
					const response = await upstreamFetch(
						`/jobs/${params.jobId}/observations`,
						auth.apiKey,
					);
					if (!response.ok) return forwardError(response);
					const data = await parseUpstream(response, ObservationsSchema);
					return data ? jsonResponse(data) : contractViolation();
				} catch {
					return upstreamUnavailable();
				}
			},
		},
	},
});
