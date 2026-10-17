import { createFileRoute } from "@tanstack/react-router";
import {
	HEALTH_REQUEST_TIMEOUT_MS,
	type HealthResponse,
	HealthResponseSchema,
} from "@/lib/api/health-contracts";
import {
	authorize,
	contractViolation,
	forwardError,
	jsonResponse,
	parseUpstream,
	UpstreamUnreachable,
	upstreamFetch,
} from "@/server/upstream";

/** Local 503 body when the analyzer is unreachable. GPU state is never guessed. */
function unreachableHealth(): HealthResponse {
	return {
		status: "unavailable",
		checked_at: new Date().toISOString(),
		services: {
			backend: { status: "error", message: "Не удалось связаться с бэкендом." },
			gpu_server: {
				status: "unknown",
				message: "Проверка GPU-сервера недоступна без бэкенда.",
			},
		},
	};
}

export const Route = createFileRoute("/api/review/health")({
	server: {
		handlers: {
			GET: async ({ request }) => {
				const auth = authorize(request);
				if (!auth.ok) return auth.response;
				if (new URL(request.url).searchParams.size > 0) {
					return jsonResponse(
						{
							error: {
								code: "BAD_REQUEST",
								message: "Параметры запроса не поддерживаются.",
							},
						},
						400,
					);
				}

				let upstream: Response;
				try {
					upstream = await upstreamFetch("/health", auth.apiKey, {
						timeoutMs: HEALTH_REQUEST_TIMEOUT_MS,
					});
				} catch (error) {
					if (error instanceof UpstreamUnreachable) {
						return jsonResponse(unreachableHealth(), 503);
					}
					throw error;
				}

				// Both 200 and 503 carry a health body; everything else is the error envelope.
				if (upstream.status === 200 || upstream.status === 503) {
					const body = await parseUpstream(upstream, HealthResponseSchema);
					if (!body) return contractViolation();
					return jsonResponse(body, upstream.status);
				}
				return forwardError(upstream);
			},
		},
	},
});
