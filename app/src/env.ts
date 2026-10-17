import { createEnv } from "@t3-oss/env-core";
import { z } from "zod";

const serverEnv: Record<string, string | undefined> =
	typeof process === "undefined" ? {} : process.env;

export const env = createEnv({
	server: {
		/** Base URL of the analyzer, including `/api/v1`. Never exposed to the browser. */
		ANALYSIS_API_URL: z.url().default("http://localhost:8000/api/v1"),
		/** Set by `dev:mock`: control endpoint of the local mock analyzer. */
		MOCK_CONTROL_URL: z.url().optional(),
	},

	clientPrefix: "VITE_",

	client: {
		VITE_APP_TITLE: z.string().min(1).optional(),
		VITE_DEV_TOOLS: z.stringbool().default(false),
		VITE_MOCK: z.stringbool().default(false),
	},

	runtimeEnv: { ...import.meta.env, ...serverEnv },

	emptyStringAsUndefined: true,
});
