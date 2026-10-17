import { createFileRoute } from "@tanstack/react-router";
import { AnalyzeAcceptedSchema, MAX_VIDEO_BYTES } from "@/lib/api/contracts";
import {
	authorize,
	checkOrigin,
	contractViolation,
	errorResponse,
	forwardError,
	jsonResponse,
	parseUpstream,
	UpstreamUnreachable,
	upstreamFetch,
	upstreamUnavailable,
} from "@/server/upstream";

// Room for multipart boundaries and headers on top of the 100 MiB file limit.
const MULTIPART_OVERHEAD_BYTES = 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 120_000;

export const Route = createFileRoute("/api/review/analyze")({
	server: {
		handlers: {
			POST: async ({ request }) => {
				const badOrigin = checkOrigin(request);
				if (badOrigin) return badOrigin;
				const auth = authorize(request);
				if (!auth.ok) return auth.response;

				const contentType = request.headers.get("content-type") ?? "";
				if (!contentType.toLowerCase().startsWith("multipart/form-data")) {
					return errorResponse(
						415,
						"UNSUPPORTED_MEDIA_TYPE",
						"Ожидается multipart/form-data с полем file.",
					);
				}
				const length = Number(request.headers.get("content-length"));
				if (
					Number.isFinite(length) &&
					length > MAX_VIDEO_BYTES + MULTIPART_OVERHEAD_BYTES
				) {
					return errorResponse(
						413,
						"FILE_TOO_LARGE",
						"Размер видео превышает 100 MiB.",
					);
				}
				if (!request.body) {
					return errorResponse(400, "BAD_REQUEST", "Пустое тело запроса.");
				}

				let upstream: Response;
				try {
					// Stream the body through; the boundary in Content-Type must survive untouched.
					upstream = await upstreamFetch("/analyze", auth.apiKey, {
						method: "POST",
						headers: { "Content-Type": contentType },
						body: request.body,
						duplex: "half",
						timeoutMs: UPLOAD_TIMEOUT_MS,
					});
				} catch (error) {
					if (error instanceof UpstreamUnreachable)
						return upstreamUnavailable();
					throw error;
				}

				if (upstream.status !== 202) return forwardError(upstream);
				const accepted = await parseUpstream(upstream, AnalyzeAcceptedSchema);
				if (!accepted) return contractViolation();
				return jsonResponse(accepted, 202, {
					Location: `/api/review/jobs/${encodeURIComponent(accepted.job_id)}`,
					"Retry-After": upstream.headers.get("retry-after") ?? "2",
				});
			},
		},
	},
});
