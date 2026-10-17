import type { z } from "zod";
import { useAuthStore } from "@/stores/auth-store";
import { ApiErrorResponseSchema } from "./contracts.ts";

export type ApiErrorCode =
	| z.infer<typeof ApiErrorResponseSchema>["error"]["code"]
	| "NETWORK"
	| "INVALID_RESPONSE";

export class ApiError extends Error {
	readonly status: number;
	readonly code: ApiErrorCode;
	readonly retryAfterSec: number | null;

	constructor(
		status: number,
		code: ApiErrorCode,
		message: string,
		retryAfterSec: number | null = null,
	) {
		super(message);
		this.name = "ApiError";
		this.status = status;
		this.code = code;
		this.retryAfterSec = retryAfterSec;
	}
}

export function isApiError(error: unknown): error is ApiError {
	return error instanceof ApiError;
}

async function toApiError(response: Response): Promise<ApiError> {
	const retry = Number(response.headers.get("retry-after"));
	const retryAfterSec = Number.isFinite(retry) && retry > 0 ? retry : null;
	const parsed = ApiErrorResponseSchema.safeParse(
		await response.json().catch(() => null),
	);
	if (parsed.success) {
		return new ApiError(
			response.status,
			parsed.data.error.code,
			parsed.data.error.message,
			retryAfterSec,
		);
	}
	return new ApiError(
		response.status,
		"INTERNAL_ERROR",
		"Неожиданный ответ сервера.",
		retryAfterSec,
	);
}

/** Real network call to the browser boundary (`/api/review/*`). */
export async function apiFetch(
	path: string,
	init: RequestInit = {},
): Promise<Response> {
	let response: Response;
	try {
		response = await fetch(path, {
			cache: "no-store",
			credentials: "same-origin",
			...init,
		});
	} catch (error) {
		if (error instanceof DOMException && error.name === "AbortError")
			throw error;
		throw new ApiError(
			0,
			"NETWORK",
			"Нет связи с сервером. Проверьте подключение.",
		);
	}
	if (response.status === 401) useAuthStore.getState().expire();
	return response;
}

/** JSON request validated against a contract schema; throws ApiError otherwise. */
export async function apiJson<S extends z.ZodType>(
	path: string,
	schema: S,
	init?: RequestInit,
	accept: readonly number[] = [200],
): Promise<z.infer<S>> {
	const response = await apiFetch(path, init);
	if (!accept.includes(response.status)) throw await toApiError(response);
	const parsed = schema.safeParse(await response.json().catch(() => null));
	if (!parsed.success) {
		throw new ApiError(
			response.status,
			"INVALID_RESPONSE",
			"Ответ сервера не соответствует контракту.",
		);
	}
	return parsed.data;
}

export { toApiError };
