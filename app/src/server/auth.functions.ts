import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import type { SessionState } from "@/lib/api/session-contracts";
import { getSession } from "./session";

/** Route-guard helper. The data boundary is still enforced in each API handler. */
export const getSessionState = createServerFn({ method: "GET" }).handler(
	async (): Promise<SessionState> => {
		const session = getSession(getRequest());
		return session
			? { authenticated: true, profile: session.profile }
			: { authenticated: false, profile: null };
	},
);
