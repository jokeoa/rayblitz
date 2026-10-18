import { createFileRoute } from "@tanstack/react-router";
import { HistorySchema } from "@/lib/api/observations";
import {
	authorize,
	jsonResponse,
	parseUpstream,
	upstreamFetch,
	forwardError,
	contractViolation,
	upstreamUnavailable,
} from "@/server/upstream";

export const Route = createFileRoute("/api/review/jobs/")({
	server: {
		handlers: {
			GET: async ({ request }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				try {
					const response = await upstreamFetch("/jobs", auth.apiKey);
					if (!response.ok) return forwardError(response);
					const data = await parseUpstream(response, HistorySchema);
					return data ? jsonResponse(data) : contractViolation();
				} catch {
					return upstreamUnavailable();
				}
			},
		},
	},
});
