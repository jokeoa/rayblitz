import "@tanstack/react-start/server-only";
import { createHash, randomBytes } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { mkdirSync, chmodSync } from "node:fs";
import { dirname, resolve } from "node:path";
import type { Profile } from "@/lib/api/session-contracts";

/** Persistent opaque sessions; API keys never leave the server. */
export const SESSION_COOKIE = "review_session";
const SESSION_TTL_SECONDS = 8 * 60 * 60;

type SessionRecord = {
	apiKey: string;
	profile: Profile;
	expiresAt: number;
};

const databasePath = resolve(process.env.SESSION_DB ?? "data/sessions.sqlite");
mkdirSync(dirname(databasePath), { recursive: true, mode: 0o700 });
const database = new DatabaseSync(databasePath);
chmodSync(databasePath, 0o600);
database.exec(
	"CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, record TEXT NOT NULL, expires_at INTEGER NOT NULL)",
);
const sessions = {
	set(id: string, record: SessionRecord) {
		database
			.prepare("DELETE FROM sessions WHERE expires_at < ?")
			.run(Date.now());
		database
			.prepare("INSERT INTO sessions VALUES (?, ?, ?)")
			.run(id, JSON.stringify(record), record.expiresAt);
	},
	get(id: string): SessionRecord | undefined {
		const row = database
			.prepare("SELECT record FROM sessions WHERE id = ?")
			.get(id);
		return row ? JSON.parse(row.record as string) : undefined;
	},
	delete(id: string) {
		database.prepare("DELETE FROM sessions WHERE id = ?").run(id);
	},
};

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
			try {
				return decodeURIComponent(part.slice(index + 1).trim());
			} catch {
				return null;
			}
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
