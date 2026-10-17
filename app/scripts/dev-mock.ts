import { spawn } from "node:child_process";
import { MOCK_API_KEY, startMockAnalyzer } from "../mock/analyzer/server.ts";

/**
 * Runs the app against the local mock analyzer.
 *
 *   node scripts/dev-mock.ts             Vite dev server, developer tools on
 *   node scripts/dev-mock.ts --present   production build served in presentation
 *                                        mode: no developer tools
 *
 * The mock is a real HTTP server that implements docs/api-contract.md, so the
 * browser still talks to /api/review/* and the proxy still forwards with fetch.
 */
const present = process.argv.includes("--present");
const mockPort = Number(process.env.MOCK_ANALYZER_PORT ?? 4010);
const appPort = process.env.PORT ?? "3000";

const mock = await startMockAnalyzer({ port: mockPort });
const origin = `http://127.0.0.1:${mock.port}`;
console.log(`[mock] analyzer on ${origin}/api/v1, API key: ${MOCK_API_KEY}`);

const env = {
	...process.env,
	ANALYSIS_API_URL: `${origin}/api/v1`,
	MOCK_CONTROL_URL: origin,
	VITE_MOCK: "true",
};

const run = (args: string[], extra: Record<string, string> = {}) =>
	spawn("npx", args, {
		stdio: "inherit",
		env: { ...env, ...extra },
	});

let child = present
	? run(["vite", "build", "--mode", "presentation", "--host"])
	: run(["vite", "dev", "--port", appPort, "--host"]);

if (present) {
	// Build first, then serve; both steps see VITE_MOCK so the flag is baked in.
	await new Promise<void>((resolve, reject) => {
		child.once("exit", (code) =>
			code === 0 ? resolve() : reject(new Error(`build exited with ${code}`)),
		);
	});
	child = run(["vite", "preview", "--mode", "presentation", "--port", appPort]);
}

const shutdown = (code: number) => {
	child.kill("SIGTERM");
	void mock.close().then(() => process.exit(code));
};
child.once("exit", (code) => shutdown(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM"] as const) {
	process.on(signal, () => shutdown(0));
}
