import {
	DEFAULT_PAGE_SIZE,
	PaginationQuerySchema,
	ResourceIdSchema,
} from "./contracts.ts";

export type PaginationQuery = { page: number; page_size: number };

const DECIMAL = /^\d+$/;

/**
 * Strict query parsing from the contract: only `page` and `page_size`, each at
 * most once, decimal digits only. Anything else is a 400, never a silent clamp.
 */
export function parsePaginationQuery(url: URL): PaginationQuery | null {
	const raw: Record<string, string> = {};
	for (const key of new Set(url.searchParams.keys())) {
		if (key !== "page" && key !== "page_size") return null;
		const values = url.searchParams.getAll(key);
		if (values.length !== 1 || !DECIMAL.test(values[0])) return null;
		raw[key] = values[0];
	}
	const parsed = PaginationQuerySchema.safeParse({
		page: raw.page === undefined ? 1 : Number(raw.page),
		page_size:
			raw.page_size === undefined ? DEFAULT_PAGE_SIZE : Number(raw.page_size),
	});
	return parsed.success ? parsed.data : null;
}

export function isResourceId(value: string): boolean {
	return ResourceIdSchema.safeParse(value).success;
}
