import { createFileRoute } from "@tanstack/react-router";
import { env } from "@/env";
import { authorize, errorResponse, jsonResponse } from "@/server/upstream";

/**
 * Developer-only bridge to the mock analyzer's control endpoint. It answers 404
 * unless the mock analyzer is running and developer tools are enabled, so it
 * is inert in presentation and production builds.
 */
export const Route = createFileRoute("/api/review/dev/mock-scenario")({
	server: {
		handlers: {
			GET: async ({ request }) => forward(request),
			POST: async ({ request }) => forward(request),
		},
	},
});

async function forward(request: Request): Promise<Response> {
	const control = env.MOCK_CONTROL_URL;
	if (!control || import.meta.env.VITE_DEV_TOOLS !== "true") {
		return errorResponse(400, "BAD_REQUEST", "Недоступно.");
	}
	const auth = authorize(request);
	if (!auth.ok) return auth.response;
	const upstream = await fetch(`${control}/__mock/scenario`, {
		method: request.method,
		headers: { "Content-Type": "application/json" },
		body: request.method === "POST" ? await request.text() : undefined,
	}).catch(() => null);
	if (!upstream)
		return errorResponse(
			503,
			"SERVICE_UNAVAILABLE",
			"Мок-анализатор недоступен.",
		);
	return jsonResponse(await upstream.json(), upstream.status);
}
