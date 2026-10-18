import { createFileRoute } from "@tanstack/react-router";
import { isResourceId } from "@/lib/api/query";
import {
	authorize,
	errorResponse,
	upstreamFetch,
	forwardError,
	upstreamUnavailable,
} from "@/server/upstream";

export const Route = createFileRoute("/api/review/jobs/$jobId/video")({
	server: {
		handlers: {
			GET: async ({ request, params }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				if (!isResourceId(params.jobId))
					return errorResponse(400, "BAD_REQUEST", "Некорректное задание.");
				try {
					const range = request.headers.get("range");
					const response = await upstreamFetch(
						`/jobs/${params.jobId}/video`,
						auth.apiKey,
						{ headers: range ? { Range: range } : {} },
					);
					if (![200, 206, 416].includes(response.status))
						return forwardError(response);
					const headers = new Headers({ "Cache-Control": "private, no-store" });
					for (const name of [
						"Content-Type",
						"Content-Length",
						"Content-Range",
						"Accept-Ranges",
					]) {
						const value = response.headers.get(name);
						if (value) headers.set(name, value);
					}
					return new Response(response.body, {
						status: response.status,
						headers,
					});
				} catch {
					return upstreamUnavailable();
				}
			},
		},
	},
});
