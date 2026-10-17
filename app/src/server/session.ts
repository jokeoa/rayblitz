import "@tanstack/react-start/server-only";
import { createHash, randomBytes } from "node:crypto";
import type { Profile } from "@/lib/api/session-contracts";

/**
 * Anonymous review session (docs/api-contract.md, "Доступ браузера").
 *
 * The browser keeps only an opaque `review_session` id in an HttpOnly,
 * SameSite=Strict cookie. The analyzer API key pasted on the login page lives
 * in server memory next to that id and is never serialized back to the client.
 * State is process-local, so a restart signs everyone out; a shared store is
 * the production replacement.
 */
export const SESSION_COOKIE = "review_session";
const SESSION_TTL_SECONDS = 8 * 60 * 60;

type SessionRecord = {
	apiKey: string;
	profile: Profile;
	expiresAt: number;
};

const globalStore = globalThis as typeof globalThis & {
	__reviewSessions?: Map<string, SessionRecord>;
};
// Survive dev-server module reloads.
globalStore.__reviewSessions ??= new Map();
const sessions = globalStore.__reviewSessions;

function profileFor(apiKey: string): Profile {
	const digest = createHash("sha256")
		.update(`review-profile:${apiKey}`)
		.digest("hex");
	return {
		name: `Ревьюер ${digest.slice(0, 4).toUpperCase()}`,
		seed: digest.slice(0, 16),
	};
}

export function createSession(apiKey: string) {
	const id = randomBytes(32).toString("base64url");
	const profile = profileFor(apiKey);
	sessions.set(id, {
		apiKey,
		profile,
		expiresAt: Date.now() + SESSION_TTL_SECONDS * 1000,
	});
	return { id, profile };
}

function readCookie(request: Request, name: string): string | null {
	const header = request.headers.get("cookie");
	if (!header) return null;
	for (const part of header.split(";")) {
		const index = part.indexOf("=");
		if (index === -1) continue;
		if (part.slice(0, index).trim() === name) {
			return decodeURIComponent(part.slice(index + 1).trim());
		}
	}
	return null;
}

export function getSession(request: Request) {
	const id = readCookie(request, SESSION_COOKIE);
	if (!id) return null;
	const record = sessions.get(id);
	if (!record) return null;
	if (record.expiresAt < Date.now()) {
		sessions.delete(id);
		return null;
	}
	return { id, apiKey: record.apiKey, profile: record.profile };
}

export function destroySession(request: Request) {
	const id = readCookie(request, SESSION_COOKIE);
	if (id) sessions.delete(id);
}

function isSecure(request: Request): boolean {
	return (
		new URL(request.url).protocol === "https:" ||
		request.headers.get("x-forwarded-proto") === "https"
	);
}

export function sessionCookie(request: Request, id: string): string {
	const parts = [
		`${SESSION_COOKIE}=${encodeURIComponent(id)}`,
		"Path=/",
		"HttpOnly",
		"SameSite=Strict",
		`Max-Age=${SESSION_TTL_SECONDS}`,
	];
	if (isSecure(request)) parts.push("Secure");
	return parts.join("; ");
}

export function clearedSessionCookie(request: Request): string {
	const parts = [
		`${SESSION_COOKIE}=`,
		"Path=/",
		"HttpOnly",
		"SameSite=Strict",
		"Max-Age=0",
	];
	if (isSecure(request)) parts.push("Secure");
	return parts.join("; ");
}
