import { z } from "zod";
import { TextSchema } from "./contracts.ts";

/**
 * Session endpoints exist only on the browser boundary (`/api/review/session`).
 * The pasted API key travels once in the login request body; afterwards the
 * browser holds only the opaque, HttpOnly `review_session` cookie.
 */
export const LoginRequestSchema = z.strictObject({
	api_key: z.string().trim().min(1).max(512),
});

export const ProfileSchema = z.strictObject({
	name: TextSchema,
	seed: z.string().min(1),
});

export const LoginResponseSchema = z.strictObject({
	profile: ProfileSchema,
	verified: z
		.boolean()
		.describe(
			"False when the analyzer was unreachable and the key is unchecked.",
		),
});

export const SessionStateSchema = z.discriminatedUnion("authenticated", [
	z.strictObject({ authenticated: z.literal(true), profile: ProfileSchema }),
	z.strictObject({ authenticated: z.literal(false), profile: z.null() }),
]);

export type Profile = z.infer<typeof ProfileSchema>;
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
export type SessionState = z.infer<typeof SessionStateSchema>;
