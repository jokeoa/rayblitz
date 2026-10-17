import { createFileRoute } from "@tanstack/react-router";
import { HEALTH_REQUEST_TIMEOUT_MS } from "@/lib/api/health-contracts";
import {
	LoginRequestSchema,
	type LoginResponse,
	type SessionState,
} from "@/lib/api/session-contracts";
import {
	clearedSessionCookie,
	createSession,
	destroySession,
	getSession,
	sessionCookie,
} from "@/server/session";
import {
	checkOrigin,
	errorResponse,
	jsonResponse,
	UpstreamUnreachable,
	unauthorized,
	upstreamFetch,
} from "@/server/upstream";

export const Route = createFileRoute("/api/review/session")({
	server: {
		handlers: {
			GET: ({ request }) => {
				const session = getSession(request);
				const state: SessionState = session
					? { authenticated: true, profile: session.profile }
					: { authenticated: false, profile: null };
				return jsonResponse(state);
			},

			POST: async ({ request }) => {
				const badOrigin = checkOrigin(request);
				if (badOrigin) return badOrigin;

				const body = LoginRequestSchema.safeParse(
					await request.json().catch(() => null),
				);
				if (!body.success) {
					return errorResponse(400, "BAD_REQUEST", "Вставьте API-ключ.");
				}
				const apiKey = body.data.api_key;

				// The health endpoint requires the key, so it doubles as key validation.
				let verified = true;
				try {
					const probe = await upstreamFetch("/health", apiKey, {
						timeoutMs: HEALTH_REQUEST_TIMEOUT_MS,
					});
					if (probe.status === 401) return unauthorized();
				} catch (error) {
					if (!(error instanceof UpstreamUnreachable)) throw error;
					// Let people in during an outage so the health block can say what is wrong.
					verified = false;
				}

				const { id, profile } = createSession(apiKey);
				const result: LoginResponse = { profile, verified };
				return jsonResponse(result, 200, {
					"Set-Cookie": sessionCookie(request, id),
				});
			},

			DELETE: ({ request }) => {
				const badOrigin = checkOrigin(request);
				if (badOrigin) return badOrigin;
				destroySession(request);
				return new Response(null, {
					status: 204,
					headers: {
						"Set-Cookie": clearedSessionCookie(request),
						"Cache-Control": "no-store",
					},
				});
			},
		},
	},
});
