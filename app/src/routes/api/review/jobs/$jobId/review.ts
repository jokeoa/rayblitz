import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { isResourceId } from "@/lib/api/query";
import {
	authorize,
	checkOrigin,
	errorResponse,
	jsonResponse,
	upstreamFetch,
	forwardError,
	upstreamUnavailable,
} from "@/server/upstream";

const Review = z.strictObject({
	reviewed: z.boolean(),
	notes: z.string().max(8000),
});
async function handle(request: Request, jobId: string) {
	const auth = authorize(request);
	if (!auth.ok) return auth.response;
	if (!isResourceId(jobId))
		return errorResponse(400, "BAD_REQUEST", "Некорректное задание.");
	let body: string | undefined;
	if (request.method === "PUT") {
		const origin = checkOrigin(request);
		if (origin) return origin;
		const parsed = Review.safeParse(await request.json().catch(() => null));
		if (!parsed.success)
			return errorResponse(400, "BAD_REQUEST", "Некорректная заметка.");
		body = JSON.stringify(parsed.data);
	}
	try {
		const response = await upstreamFetch(`/jobs/${jobId}/review`, auth.apiKey, {
			method: request.method,
			body,
			headers: { "Content-Type": "application/json" },
		});
		if (!response.ok) return forwardError(response);
		return jsonResponse(Review.parse(await response.json()));
	} catch {
		return upstreamUnavailable();
	}
}
export const Route = createFileRoute("/api/review/jobs/$jobId/review")({
	server: {
		handlers: {
			GET: ({ request, params }) => handle(request, params.jobId),
			PUT: ({ request, params }) => handle(request, params.jobId),
		},
	},
});
