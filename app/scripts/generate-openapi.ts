import { readFile, writeFile } from "node:fs/promises";
import { z } from "zod";
import * as examples from "../src/lib/api/contract-examples.ts";
import {
  AnalyzeAcceptedSchema, ApiErrorResponseSchema, CompletedJobSchema, EvidenceFrameSchema,
  JobIdSchema, JobResponseSchema, JobViewSchema, MAX_VIDEO_BYTES, NormativeSourceSchema,
  OverviewSchema, PaginationQuerySchema, POLL_INTERVAL_MS, ProgressSchema, ResourceIdSchema,
  RuleSchema, StageSchema, ViolationSchema, ViolationsPageSchema,
} from "../src/lib/api/contracts.ts";
import { JuryEvidenceFrameSchema, JuryJobResponseSchema, JuryViolationSchema } from "../src/lib/api/jury-contracts.ts";
import { HealthResponseSchema, HealthyHealthSchema, UnhealthyHealthSchema, ServiceHealthSchema } from "../src/lib/api/health-contracts.ts";

const contracts = {
  JobId: JobIdSchema, ResourceId: ResourceIdSchema, AnalyzeAccepted: AnalyzeAcceptedSchema,
  JobView: JobViewSchema, Stage: StageSchema, Progress: ProgressSchema, Overview: OverviewSchema,
  CompletedJob: CompletedJobSchema, JobResponse: JobResponseSchema,
  NormativeSource: NormativeSourceSchema, Rule: RuleSchema, EvidenceFrame: EvidenceFrameSchema,
  Violation: ViolationSchema, PaginationQuery: PaginationQuerySchema, ViolationsPage: ViolationsPageSchema,
  JuryEvidenceFrame: JuryEvidenceFrameSchema, JuryViolation: JuryViolationSchema, JuryJobResponse: JuryJobResponseSchema,
  ApiErrorResponse: ApiErrorResponseSchema,
  ServiceHealth: ServiceHealthSchema, HealthResponse: HealthResponseSchema,
  HealthyHealth: HealthyHealthSchema, UnhealthyHealth: UnhealthyHealthSchema,
};
const registry = z.registry<{ id: string }>();
for (const [id, schema] of Object.entries(contracts)) registry.add(schema, { id });
const { schemas } = z.toJSONSchema(registry, { target: "draft-2020-12", uri: (id) => `#/components/schemas/${id}` });
for (const schema of Object.values(schemas)) { delete schema.$id; delete schema.$schema; }
const ref = (name: keyof typeof contracts) => ({ $ref: `#/components/schemas/${name}` });
const errorRef = (name: string) => ({ $ref: `#/components/responses/${name}` });
const noStore = { "Cache-Control": { description: "Do not cache video analysis responses or frames.", schema: { type: "string", const: "no-store" } } };
const jobParameter = { $ref: "#/components/parameters/JobId" };
const readErrors = {
  "400": errorRef("BadRequest"), "401": errorRef("Unauthorized"), "404": errorRef("NotFound"),
  "500": errorRef("InternalError"), "503": errorRef("Unavailable"),
};
const errors = {
  BadRequest: "400 BAD_REQUEST — malformed upload, identifier, view, page or page_size. Repeated or unknown query parameters are rejected.",
  Unauthorized: "401 UNAUTHORIZED — missing or invalid X-API-Key.",
  NotFound: "404 JOB_NOT_FOUND — unknown job or job owned by another API key.",
  NotDone: "409 JOB_NOT_DONE — events or frames requested before done, including a failed job.",
  EvidenceNotFound: "404 EVIDENCE_NOT_FOUND — event/frame not found in this job; inaccessible jobs still return JOB_NOT_FOUND.",
  TooLarge: `413 FILE_TOO_LARGE — file exceeds ${MAX_VIDEO_BYTES} bytes.`,
  UnsupportedMedia: "415 UNSUPPORTED_MEDIA_TYPE — request is not multipart/form-data or file is not MOV.",
  InvalidVideo: "422 INVALID_VIDEO — no decodable video stream, discovered before acceptance.",
  Unavailable: "503 SERVICE_UNAVAILABLE — temporary unavailability or unable to accept a new job.",
  InternalError: "500 INTERNAL_ERROR — HTTP handler failure; no stack traces or internal paths.",
};

const document = {
  openapi: "3.1.1",
  info: {
    title: "ForteBank video analysis API", version: "0.3.0",
    description: "Contract only; handlers are not implemented. Default job view satisfies the jury's required full JPEG/base64 result. view=ui supplies local-LLM overview and backend-defined progress; events are paginated and frames fetched separately. Both views are projections of the same immutable result, not separate analyses. Examples are synthetic. Cross-field invariants documented in api-contract.md must also be implemented by the server; Zod refinements are not represented in JSON Schema.",
  },
  servers: [{ url: "/api/v1" }], security: [{ ApiKeyAuth: [] }],
  tags: [{ name: "Analysis" }, { name: "Events" }, { name: "Health" }],
  paths: {
    "/health": {
      get: {
        tags: ["Health"], operationId: "getServiceHealth", summary: "Check backend and GPU-server readiness",
        description: "Authenticated aggregate readiness check, not job progress. backend=ok means the API can accept and persist jobs; gpu_server=ok requires a responsive GPU worker, usable GPU and loaded analysis/LLM models. Probe both independently with a 2-second budget; do not run inference. UI polls every 10 seconds through the same-origin proxy, which times out after 3 seconds. If the backend is unreachable, the proxy returns 503 HealthResponse with backend=error and gpu_server=unknown; it must not assert GPU failure. Health 503 uses the health body, not ApiErrorResponse. No query parameters. No cached success.",
        responses: {
          "200": {
            description: "Both services are ready. status=ok.", headers: noStore,
            content: { "application/json": { schema: ref("HealthyHealth"), example: examples.healthyExample } },
          },
          "503": {
            description: "At least one service is not ready. A valid health report, not a transport error. status=degraded when backend is ready but GPU is not; unavailable when backend is not ready.",
            headers: noStore,
            content: { "application/json": { schema: ref("UnhealthyHealth"), examples: {
              gpu_unavailable: { value: examples.gpuUnavailableExample },
              backend_unreachable: { value: examples.backendUnavailableExample },
            } } },
          },
          "400": errorRef("BadRequest"), "401": errorRef("Unauthorized"), "500": errorRef("InternalError"),
        },
      },
    },
    "/analyze": {
      post: {
        tags: ["Analysis"], operationId: "analyzeVideo", summary: "Upload one MOV and create a job",
        description: "Authenticate before reading the upload. Return 202 after persisting it, without waiting for inference. Repeated POST creates another job; do not retry automatically. Processing, local LLM overview and result publication share the five-minute deadline, measured from upload receipt start.",
        requestBody: {
          required: true,
          description: `One nonempty .mov file, at most ${MAX_VIDEO_BYTES} bytes. Verify container and video stream. Accept generic or absent part MIME for a valid MOV.`,
          content: { "multipart/form-data": {
            schema: { type: "object", required: ["file"], additionalProperties: false, properties: { file: { type: "string", format: "binary" } } },
            encoding: { file: { contentType: "video/quicktime, application/octet-stream" } },
          } },
        },
        responses: {
          "202": {
            description: "Accepted and persisted; no verdict yet.",
            headers: { ...noStore,
              Location: { description: "Job resource; UI clients append view=ui.", schema: { type: "string", examples: ["/api/v1/jobs/3f2a9c1e"] } },
              "Retry-After": { description: "Poll delay, seconds.", schema: { type: "integer", const: POLL_INTERVAL_MS / 1000 } },
            },
            content: { "application/json": { schema: ref("AnalyzeAccepted"), example: examples.acceptedExample } },
          },
          "400": errorRef("BadRequest"), "401": errorRef("Unauthorized"), "413": errorRef("TooLarge"),
          "415": errorRef("UnsupportedMedia"), "422": errorRef("InvalidVideo"), "500": errorRef("InternalError"), "503": errorRef("Unavailable"),
        },
      },
    },
    "/jobs/{job_id}": {
      parameters: [jobParameter],
      get: {
        tags: ["Analysis"], operationId: "getAnalysisJob", summary: "Get state and result in jury or UI representation",
        description: "view=jury (default) returns JuryJobResponse, including all events with JPEG/base64 on done. view=ui returns JobResponse: progress for every state, overview and violations_count only on done, never inline events or frames. Stage IDs, display labels, descriptions, ordered plan and percentages are determined by the backend. done and failed are terminal. Both views have the same job_id, status and verdict. A failed job is HTTP 200. Unknown/repeated view, or page/page_size on this endpoint, return 400; paginate via /violations.",
        parameters: [{ name: "view", in: "query", required: false, schema: ref("JobView") }],
        responses: {
          "200": {
            description: "Select response schema by view. No query means JuryJobResponse.", headers: noStore,
            content: { "application/json": {
              schema: { oneOf: [ref("JuryJobResponse"), ref("JobResponse")] },
              examples: {
                jury_processing: { value: examples.juryProcessingExample }, jury_no_violation: { value: examples.juryNoViolationExample },
                jury_violation: { value: examples.juryViolationExample }, jury_failed: { value: examples.juryFailedExample },
                ui_processing: { value: examples.processingExample }, ui_no_violation: { value: examples.noViolationExample },
                ui_violation: { value: examples.violationExample }, ui_failed: { value: examples.failedExample },
              },
            } },
          }, ...readErrors,
        },
      },
    },
    "/jobs/{job_id}/violations": {
      parameters: [jobParameter],
      get: {
        tags: ["Events"], operationId: "listViolations", summary: "Paginated event timecodes, descriptions, rules and frame references",
        description: "Only available on done. Order by (timecode_sec ascending, id ascending ASCII) is stable across pages of the immutable snapshot. Pages are 1-based; default page_size=20, maximum 100. Empty results or pages beyond the end return 200 with items=[]. total counts all events and equals UI violations_count. There are no inline image bytes. Rules are embedded in each event; there is no /rules endpoint. Cross-field checks: exact page length, unique event IDs, chronological order, unique frame IDs per event.",
        parameters: Object.entries(PaginationQuerySchema.shape).map(([name, schema]) => ({
          name, in: "query", required: false, schema: z.toJSONSchema(schema, { target: "draft-2020-12" }),
        })),
        responses: {
          "200": { description: "One page of events.", headers: noStore, content: { "application/json": {
            schema: ref("ViolationsPage"), examples: {
              first_page: { value: examples.violationsPageExample }, second_page: { value: examples.secondPageExample },
              no_violation: { value: examples.emptyPageExample },
              beyond_end: { value: { ...examples.secondPageExample, page: 3, items: [] } },
            },
          } } },
          ...readErrors, "409": errorRef("NotDone"),
        },
      },
    },
    "/jobs/{job_id}/violations/{violation_id}/frames/{frame_id}": {
      parameters: [jobParameter,
        { name: "violation_id", in: "path", required: true, schema: ref("ResourceId") },
        { name: "frame_id", in: "path", required: true, schema: ref("ResourceId") },
      ],
      get: {
        tags: ["Events"], operationId: "getEvidenceFrame", summary: "Load one evidence JPEG on demand",
        description: "Only available on done. Authenticate and check job ownership before resolving event/frame IDs. Returns the same JPEG bytes as the corresponding jury base64 frame. A frame from another event/job is never served. Browser clients use the same-origin session-protected proxy; do not put API keys in URLs.",
        responses: {
          "200": { description: "JPEG bytes, not JSON or base64.", headers: noStore, content: { "image/jpeg": { schema: { type: "string", format: "binary" } } } },
          ...readErrors, "404": errorRef("EvidenceNotFound"), "409": errorRef("NotDone"),
        },
      },
    },
  },
  components: {
    securitySchemes: { ApiKeyAuth: { type: "apiKey", in: "header", name: "X-API-Key" } },
    parameters: { JobId: { name: "job_id", in: "path", required: true, schema: ref("JobId") } },
    schemas,
    responses: Object.fromEntries(Object.entries(errors).map(([name, description]) => [name, {
      description, headers: { ...noStore, ...(name === "Unavailable" ? { "Retry-After": { schema: { type: "integer", minimum: 1 } } } : {}) },
      content: { "application/json": { schema: ref("ApiErrorResponse"), ...(name === "Unauthorized" ? { example: examples.unauthorizedExample } : {}) } },
    }])),
  },
};
const output = new URL("../../docs/openapi.json", import.meta.url);
const serialized = `${JSON.stringify(document, null, 2)}\n`;
if (process.argv.includes("--check")) {
  if ((await readFile(output, "utf8")) !== serialized) throw new Error("OpenAPI is outdated. Run npm run contracts:generate.");
  console.log("OpenAPI matches the contracts.");
} else {
  await writeFile(output, serialized);
  console.log("Generated docs/openapi.json.");
}
