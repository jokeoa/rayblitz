import { MOCK_API_KEY, startMockAnalyzer } from "../mock/analyzer/server.ts";

const port = Number(process.env.MOCK_ANALYZER_PORT ?? 4010);
const mock = await startMockAnalyzer({ port });
console.log(`[mock-analyzer] http://127.0.0.1:${mock.port}/api/v1  (API key: ${MOCK_API_KEY})`);

for (const signal of ["SIGINT", "SIGTERM"] as const) {
	process.on(signal, () => {
		void mock.close().then(() => process.exit(0));
	});
}
