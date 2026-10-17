import { ApiError, apiFetch, apiJson, toApiError } from "./client";
import {
	type AnalyzeAccepted,
	AnalyzeAcceptedSchema,
	type JobResponse,
	JobResponseSchema,
	MAX_PAGE_SIZE,
	type Violation,
	type ViolationsPage,
	ViolationsPageSchema,
} from "./contracts.ts";
import {
	type HealthResponse,
	HealthResponseSchema,
} from "./health-contracts.ts";
import {
	type LoginResponse,
	LoginResponseSchema,
} from "./session-contracts.ts";

const BASE = "/api/review";
const seg = encodeURIComponent;

/** `/health` carries a health body for both 200 and 503; only other statuses are errors. */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
	return apiJson(
		`${BASE}/health`,
		HealthResponseSchema,
		{ signal },
		[200, 503],
	);
}

export function login(apiKey: string): Promise<LoginResponse> {
	return apiJson(`${BASE}/session`, LoginResponseSchema, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ api_key: apiKey }),
	});
}

export async function logout(): Promise<void> {
	const response = await apiFetch(`${BASE}/session`, { method: "DELETE" });
	if (!response.ok && response.status !== 401) throw await toApiError(response);
}

/** Single POST, never retried automatically: a lost response leaves the outcome unknown. */
export function startAnalysis(
	file: File,
	signal?: AbortSignal,
): Promise<AnalyzeAccepted> {
	const body = new FormData();
	body.append("file", file, file.name);
	return apiJson(
		`${BASE}/analyze`,
		AnalyzeAcceptedSchema,
		{ method: "POST", body, signal },
		[202],
	);
}

export function getJob(
	jobId: string,
	signal?: AbortSignal,
): Promise<JobResponse> {
	return apiJson(`${BASE}/jobs/${seg(jobId)}`, JobResponseSchema, { signal });
}

export function getViolationsPage(
	jobId: string,
	page: number,
	pageSize: number,
	signal?: AbortSignal,
): Promise<ViolationsPage> {
	return apiJson(
		`${BASE}/jobs/${seg(jobId)}/violations?page=${page}&page_size=${pageSize}`,
		ViolationsPageSchema,
		{ signal },
	);
}

/** Walks every page so the timeline and the list see the full, ordered result. */
export async function getAllViolations(
	jobId: string,
	signal?: AbortSignal,
): Promise<Violation[]> {
	const first = await getViolationsPage(jobId, 1, MAX_PAGE_SIZE, signal);
	const items = [...first.items];
	const pages = Math.ceil(first.total / MAX_PAGE_SIZE);
	for (let page = 2; page <= pages; page += 1) {
		const next = await getViolationsPage(jobId, page, MAX_PAGE_SIZE, signal);
		if (next.total !== first.total) {
			throw new ApiError(
				200,
				"INVALID_RESPONSE",
				"Результат изменился во время загрузки.",
			);
		}
		items.push(...next.items);
	}
	return items;
}

export function frameUrl(
	jobId: string,
	violationId: string,
	frameId: string,
): string {
	return `${BASE}/jobs/${seg(jobId)}/violations/${seg(violationId)}/frames/${seg(frameId)}`;
}
