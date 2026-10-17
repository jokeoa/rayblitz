import "@tanstack/react-start/server-only";
import type { z } from "zod";
import { env } from "@/env";
import { ApiErrorResponseSchema } from "@/lib/api/contracts";
import { getSession } from "./session";

export const NO_STORE = "no-store";

type ErrorCode = z.infer<typeof ApiErrorResponseSchema>["error"]["code"];

export function errorResponse(
	status: number,
	code: ErrorCode,
	message: string,
	headers?: HeadersInit,
): Response {
	const merged = new Headers(headers);
	merged.set("Cache-Control", NO_STORE);
	return Response.json(
		{ error: { code, message } },
		{ status, headers: merged },
	);
}

export function jsonResponse(
	body: unknown,
	status = 200,
	headers?: HeadersInit,
): Response {
	const merged = new Headers(headers);
	merged.set("Cache-Control", NO_STORE);
	return Response.json(body, { status, headers: merged });
}

export const unauthorized = () =>
	errorResponse(401, "UNAUTHORIZED", "Неверный или отсутствующий API-ключ.");

export const upstreamUnavailable = () =>
	errorResponse(
		503,
		"SERVICE_UNAVAILABLE",
		"Сервис анализа временно недоступен. Повторите попытку позже.",
		{ "Retry-After": "5" },
	);

export const contractViolation = () =>
	errorResponse(
		500,
		"INTERNAL_ERROR",
		"Сервис анализа вернул ответ, не соответствующий контракту.",
	);

/** POST requests must come from our own origin. A foreign Origin is a 400. */
export function checkOrigin(request: Request): Response | null {
	const origin = request.headers.get("origin");
	if (!origin) return null;
	const host =
		request.headers.get("x-forwarded-host") ?? request.headers.get("host");
	try {
		if (host && new URL(origin).host === host) return null;
	} catch {
		// fall through to the rejection below
	}
	return errorResponse(400, "BAD_REQUEST", "Недопустимый источник запроса.");
}

export type Authorized =
	| { ok: true; apiKey: string }
	| { ok: false; response: Response };

export function authorize(request: Request): Authorized {
	const session = getSession(request);
	if (!session) return { ok: false, response: unauthorized() };
	return { ok: true, apiKey: session.apiKey };
}

export class UpstreamUnreachable extends Error {}

export async function upstreamFetch(
	path: string,
	apiKey: string,
	init: RequestInit & { duplex?: "half"; timeoutMs?: number } = {},
): Promise<Response> {
	const { timeoutMs = 15_000, headers, ...rest } = init;
	const merged = new Headers(headers);
	merged.set("X-API-Key", apiKey);
	const base = env.ANALYSIS_API_URL.replace(/\/+$/, "");
	try {
		return await fetch(`${base}${path}`, {
			...rest,
			headers: merged,
			signal: AbortSignal.timeout(timeoutMs),
			redirect: "manual",
		});
	} catch {
		throw new UpstreamUnreachable();
	}
}

/** Parse a JSON upstream body against its contract schema. */
export async function parseUpstream<S extends z.ZodType>(
	response: Response,
	schema: S,
): Promise<z.infer<S> | null> {
	try {
		const parsed = schema.safeParse(await response.json());
		return parsed.success ? parsed.data : null;
	} catch {
		return null;
	}
}

/** Forward a documented error body unchanged, or flag a contract violation. */
export async function forwardError(response: Response): Promise<Response> {
	const parsed = await parseUpstream(response, ApiErrorResponseSchema);
	if (!parsed) return contractViolation();
	const headers = new Headers();
	const retryAfter = response.headers.get("retry-after");
	if (retryAfter) headers.set("Retry-After", retryAfter);
	return jsonResponse(parsed, response.status, headers);
}
