import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import * as contracts from "../src/lib/api/contracts.ts";
import { JuryJobResponseSchema } from "../src/lib/api/jury-contracts.ts";
import { HealthResponseSchema } from "../src/lib/api/health-contracts.ts";

const directory = mkdtempSync(join(tmpdir(), "backend-contracts-"));
const output = join(directory, "responses.json");
const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
const schemas = { ...contracts, JuryJobResponseSchema, HealthResponseSchema };
try {
	execFileSync(process.env.BACKEND_PYTHON ?? "python3", ["tests/test_contracts.py"], {
		cwd: backend,
		env: { ...process.env, PYTHONPATH: backend, CONTRACT_OUTPUT: output },
		stdio: "inherit",
	});
	const records = JSON.parse(readFileSync(output, "utf8"));
	for (const { schema, body } of records) {
		const validator = schemas[schema as keyof typeof schemas] as { parse(value: unknown): unknown };
		validator.parse(body);
	}
	console.log(`Validated ${records.length} backend responses against frontend Zod contracts.`);
} finally {
	rmSync(directory, { recursive: true, force: true });
}
