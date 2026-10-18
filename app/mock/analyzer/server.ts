import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
	createServer,
	type IncomingMessage,
	type Server,
	type ServerResponse,
} from "node:http";
import { fileURLToPath } from "node:url";
import {
	type ApiErrorResponse,
	JobResponseSchema,
	MAX_VIDEO_BYTES,
	ViolationsPageSchema,
} from "../../src/lib/api/contracts.ts";
import { DevScenarioSchema, type DevScenario } from "../../src/lib/api/dev-contracts.ts";
import {
	HealthResponseSchema,
	type HealthResponse,
} from "../../src/lib/api/health-contracts.ts";
import { JuryJobResponseSchema } from "../../src/lib/api/jury-contracts.ts";
import {
	isResourceId,
	parsePaginationQuery,
} from "../../src/lib/api/query.ts";
import {
	FIXTURE_DURATION_SEC,
	buildViolations,
	frameFileIndex,
	overviewFor,
} from "./fixtures.ts";

export const MOCK_API_KEY = "fb-demo-key";

const FRAMES_DIR = fileURLToPath(new URL("../frames/", import.meta.url));
const MULTIPART_OVERHEAD = 1024 * 1024;
const QUEUE_MS = 1_500;
const TOTAL_MS = 17_000;
const FAIL_AT_PERCENT = 52;

const STAGES = [
	{
		id: "prepare_video",
		label: "Подготовка видео",
		description: "Проверяем видеопоток и извлекаем кадры.",
		weight: 15,
	},
	{
		id: "detect_events",
		label: "Анализ событий",
		description: "Ищем визуальные признаки возможных нарушений.",
		weight: 60,
	},
	{
		id: "write_overview",
		label: "Подготовка обзора",
		description: "Локальная LLM формирует обзор проверенных результатов.",
		weight: 25,
	},
] as const;

type Outcome = "violation" | "no_violation" | "failed";
type Job = {
	id: string;
	createdAt: number;
	outcome: Outcome;
	durationSec: number;
	fileName: string;
	video: Buffer;
	review: { reviewed: boolean; notes: string };
};


function stageView(overall: number, failedAt: number | null) {
	let start = 0;
	return STAGES.map((stage) => {
		const end = start + stage.weight;
		const base = { id: stage.id, label: stage.label, description: stage.description };
		let view:
			| (typeof base & { status: "pending"; percent: 0 })
			| (typeof base & { status: "running"; percent: number })
			| (typeof base & { status: "done"; percent: 100 })
			| (typeof base & { status: "failed"; percent: number });
		if (failedAt !== null && failedAt >= start && failedAt < end) {
			view = {
				...base,
				status: "failed",
				percent: Math.min(99, ((failedAt - start) / stage.weight) * 100),
			};
		} else if (overall >= end) {
			view = { ...base, status: "done", percent: 100 };
		} else if (overall > start || (overall === start && start > 0)) {
			view = {
				...base,
				status: "running",
				percent: Math.min(99.5, ((overall - start) / stage.weight) * 100),
			};
		} else {
			view = { ...base, status: "pending", percent: 0 };
		}
		start = end;
		return view;
	});
}

function snapshot(job: Job, now: number) {
	const elapsed = now - job.createdAt;
	const progressOverall =
		elapsed < QUEUE_MS ? 0 : ((elapsed - QUEUE_MS) / (TOTAL_MS - QUEUE_MS)) * 100;

	if (job.outcome === "failed" && progressOverall >= FAIL_AT_PERCENT) {
		return {
			job_id: job.id,
			status: "failed" as const,
			progress: {
				percent: FAIL_AT_PERCENT,
				stages: stageView(FAIL_AT_PERCENT, FAIL_AT_PERCENT),
			},
			error: {
				code: "ANALYSIS_FAILED" as const,
				message: "Не удалось выделить события на видео. Попробуйте загрузить файл ещё раз.",
			},
		};
	}

	if (progressOverall >= 100) {
		const violations = job.outcome === "violation" ? buildViolations(job.durationSec) : [];
		const common = {
			job_id: job.id,
			status: "done" as const,
			progress: { percent: 100 as const, stages: stageView(100, null) },
			overview: overviewFor(
				job.outcome === "violation" ? "violation" : "no_violation",
				violations,
			),
		};
		return violations.length > 0
			? { ...common, verdict: "violation" as const, violations_count: violations.length }
			: { ...common, verdict: "no_violation" as const, violations_count: 0 as const };
	}

	const percent = Math.min(progressOverall, 99.5);
	return {
		job_id: job.id,
		status: "processing" as const,
		progress: { percent, stages: stageView(percent, null) },
	};
}

/** The development mock keeps the original upload in memory for playback. */
async function inspectUpload(request: IncomingMessage) {
 const chunks: Buffer[] = [];
 let total = 0;
 for await (const chunk of request as AsyncIterable<Buffer>) {
  total += chunk.length;
  if (total > MAX_VIDEO_BYTES + MULTIPART_OVERHEAD) return { total, fileName:null, fieldName:null, durationSec:null, video:Buffer.alloc(0) };
  chunks.push(chunk);
 }
 const form = await new Response(Buffer.concat(chunks), {headers:{"Content-Type":request.headers["content-type"] ?? ""}}).formData();
 const file = form.get("file");
 if (!(file instanceof File) || [...form.keys()].length !== 1) return { total, fileName:null, fieldName:null, durationSec:null, video:Buffer.alloc(0) };
 const video = Buffer.from(await file.arrayBuffer());
 let durationSec: number | null = null;
 const at = video.indexOf("mvhd");
 if (at >= 0 && at+40 <= video.length) {
  const version = video[at+4];
  const timescale = video.readUInt32BE(at+(version === 1 ? 24 : 16));
  const duration = version === 1 ? Number(video.readBigUInt64BE(at+28)) : video.readUInt32BE(at+20);
  if (timescale > 0 && duration > 0) durationSec = duration/timescale;
 }
 return {total, fileName:file.name, fieldName:"file", durationSec, video};
}

export type MockAnalyzer = { server: Server; port: number; close: () => Promise<void> };

export async function startMockAnalyzer(options: { port?: number } = {}): Promise<MockAnalyzer> {
	const jobs = new Map<string, Job>();
	const scenario: DevScenario = { health: "ok", outcome: "auto" };
	const frameCache = new Map<number, Buffer>();

	const send = (
		res: ServerResponse,
		status: number,
		body: unknown,
		headers: Record<string, string> = {},
	) => {
		res.writeHead(status, {
			"Content-Type": "application/json; charset=utf-8",
			"Cache-Control": "no-store",
			...headers,
		});
		res.end(JSON.stringify(body));
	};
	const fail = (
		res: ServerResponse,
		status: number,
		code: ApiErrorResponse["error"]["code"],
		message: string,
		headers: Record<string, string> = {},
	) => send(res, status, { error: { code, message } } satisfies ApiErrorResponse, headers);

	const health = (): { status: number; body: HealthResponse } => {
		const checked_at = new Date().toISOString();
		switch (scenario.health) {
			case "gpu_error":
				return {
					status: 503,
					body: {
						status: "degraded",
						checked_at,
						services: {
							backend: { status: "ok", message: "Бэкенд готов принимать задания." },
							gpu_server: { status: "error", message: "Модели ещё загружаются на GPU." },
						},
					},
				};
			case "gpu_unknown":
				return {
					status: 503,
					body: {
						status: "degraded",
						checked_at,
						services: {
							backend: { status: "ok", message: "Бэкенд готов принимать задания." },
							gpu_server: { status: "unknown", message: "Состояние GPU-сервера не подтверждено." },
						},
					},
				};
			case "backend_error":
				return {
					status: 503,
					body: {
						status: "unavailable",
						checked_at,
						services: {
							backend: { status: "error", message: "База заданий не отвечает." },
							gpu_server: { status: "unknown", message: "Проверка GPU-сервера недоступна без бэкенда." },
						},
					},
				};
			default:
				return {
					status: 200,
					body: {
						status: "ok",
						checked_at,
						services: {
							backend: { status: "ok", message: "Бэкенд готов принимать задания." },
							gpu_server: { status: "ok", message: "GPU и модели готовы к анализу." },
						},
					},
				};
		}
	};

	const chooseOutcome = (fileName: string): Outcome => {
		if (scenario.outcome !== "auto") return scenario.outcome;
		const name = fileName.toLowerCase();
		if (name.includes("fail") || name.includes("error")) return "failed";
		if (name.includes("clean") || name.includes("ok")) return "no_violation";
		return "violation";
	};

	const handle = async (req: IncomingMessage, res: ServerResponse) => {
		const url = new URL(req.url ?? "/", "http://mock.local");
		const method = req.method ?? "GET";

		// Developer control surface, outside the product contract.
		if (url.pathname === "/__mock/scenario") {
			if (method === "POST") {
				const chunks: Buffer[] = [];
				for await (const chunk of req as AsyncIterable<Buffer>) chunks.push(chunk);
				const raw = Buffer.concat(chunks);
				const parsed = DevScenarioSchema.safeParse(JSON.parse(raw.toString() || "{}"));
				if (!parsed.success) return send(res, 400, { error: "invalid scenario" });
				Object.assign(scenario, parsed.data);
			}
			return send(res, 200, scenario);
		}

		if (!url.pathname.startsWith("/api/v1/")) return fail(res, 400, "BAD_REQUEST", "Неизвестный маршрут.");
		const path = url.pathname.slice("/api/v1".length);

		if (req.headers["x-api-key"] !== MOCK_API_KEY) {
			if (method === "POST") req.resume();
			return fail(res, 401, "UNAUTHORIZED", "Неверный или отсутствующий API-ключ.");
		}

		if (path === "/health" && method === "GET") {
			if (scenario.health === "slow") await new Promise((r) => setTimeout(r, 4_000));
			else await new Promise((r) => setTimeout(r, 20 + Math.random() * 90));
			const { status, body } = health();
			return send(res, status, HealthResponseSchema.parse(body));
		}

		if (path === "/analyze" && method === "POST") {
			const type = req.headers["content-type"] ?? "";
			if (!type.toLowerCase().startsWith("multipart/form-data")) {
				req.resume();
				return fail(res, 415, "UNSUPPORTED_MEDIA_TYPE", "Ожидается multipart/form-data.");
			}
			const upload = await inspectUpload(req);
			if (upload.total > MAX_VIDEO_BYTES + MULTIPART_OVERHEAD) {
				return fail(res, 413, "FILE_TOO_LARGE", "Размер видео превышает 100 MiB.");
			}
			if (upload.fieldName !== "file" || !upload.fileName) {
				return fail(res, 400, "BAD_REQUEST", "Нужно одно поле file с файлом.");
			}
			if (!upload.fileName.toLowerCase().endsWith(".mov")) {
				return fail(res, 415, "UNSUPPORTED_MEDIA_TYPE", "Принимаются только файлы .mov.");
			}
			if (upload.durationSec === null) {
				return fail(res, 422, "INVALID_VIDEO", "Не удалось декодировать видео.");
			}
			if (health().status !== 200) {
				return fail(res, 503, "SERVICE_UNAVAILABLE", "Сервис временно недоступен.", {
					"Retry-After": "5",
				});
			}
			const id = randomBytes(4).toString("hex");
			jobs.set(id, {
				id,
				createdAt: Date.now(),
				outcome: chooseOutcome(upload.fileName),
				durationSec: upload.durationSec ?? FIXTURE_DURATION_SEC,
                fileName: upload.fileName, video: upload.video, review: { reviewed:false, notes:"" },
			});
			return send(res, 202, { job_id: id }, {
				Location: `/api/v1/jobs/${id}`,
				"Retry-After": "2",
			});
		}

        if (path === "/jobs" && method === "GET") {
            return send(res, 200, {items:[...jobs.values()].reverse().map(job => {
                const state = snapshot(job, Date.now());
                return {jobId:job.id, fileName:job.fileName, sizeBytes:job.video.length,
                    createdAt:job.createdAt, startedAt:job.createdAt+QUEUE_MS,
                    queued:Date.now()-job.createdAt < QUEUE_MS, playbackReady:true,
                    status:state.status, percent:state.progress.percent,
                    ...(state.status === "done" ? {verdict:state.verdict, violationsCount:state.violations_count} : {}),
                    ...(state.status === "failed" ? {errorCode:state.error.code} : {})};
            })});
        }
        const mediaMatch = /^\/jobs\/([A-Za-z0-9_-]+)\/(video|observations|review)$/.exec(path);
        if (mediaMatch) {
            const job = jobs.get(mediaMatch[1]);
            if (!job) return fail(res, 404, "JOB_NOT_FOUND", "Задание не найдено.");
            if (mediaMatch[2] === "review") {
                if (method === "PUT") {
                    const chunks:Buffer[] = [];
                    for await (const chunk of req) chunks.push(Buffer.from(chunk));
                    const value = JSON.parse(Buffer.concat(chunks).toString());
                    if (typeof value.reviewed !== "boolean" || typeof value.notes !== "string" || value.notes.length > 8000) return fail(res,400,"BAD_REQUEST","Некорректная заметка.");
                    job.review = {reviewed:value.reviewed, notes:value.notes};
                }
                return send(res,200,job.review);
            }
            if (mediaMatch[2] === "observations") return send(res,200,{people:null,objects:null});
            const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range ?? "");
            const start = range ? Number(range[1]) : 0;
            const end = range?.[2] ? Math.min(Number(range[2]),job.video.length-1) : job.video.length-1;
            if (start > end || start >= job.video.length) {
                res.writeHead(416,{"Content-Range":`bytes */${job.video.length}`}); return res.end();
            }
            res.writeHead(range ? 206 : 200,{"Content-Type":"video/quicktime","Accept-Ranges":"bytes",
                "Content-Length":String(end-start+1),"Cache-Control":"no-store",
                ...(range ? {"Content-Range":`bytes ${start}-${end}/${job.video.length}`} : {})});
            return res.end(job.video.subarray(start,end+1));
        }

		const jobMatch = /^\/jobs\/([^/]+)(?:\/violations(?:\/([^/]+)\/frames\/([^/]+))?)?$/.exec(path);
		if (jobMatch && method === "GET") {
			const [whole, jobId, violationId, frameId] = jobMatch;
			if (![jobId, violationId, frameId].every((part) => part === undefined || isResourceId(part))) {
				return fail(res, 400, "BAD_REQUEST", "Некорректный идентификатор.");
			}
			const job = jobs.get(jobId);
			if (!job) return fail(res, 404, "JOB_NOT_FOUND", "Задание не найдено.");
			const state = snapshot(job, Date.now());
			const isViolations = whole.includes("/violations");

			if (!isViolations) {
				const view = url.searchParams.getAll("view");
				const keys = new Set(url.searchParams.keys());
				if (view.length > 1 || [...keys].some((key) => key !== "view") || (view[0] && !["jury", "ui"].includes(view[0]))) {
					return fail(res, 400, "BAD_REQUEST", "Недопустимый параметр view.");
				}
				if (view[0] === "ui") return send(res, 200, JobResponseSchema.parse(state));
				return send(res, 200, JuryJobResponseSchema.parse(await juryView(job, state)));
			}

			if (state.status !== "done") return fail(res, 409, "JOB_NOT_DONE", "Результат ещё не готов.");
			const all = job.outcome === "violation" ? buildViolations(job.durationSec) : [];

			if (frameId !== undefined && violationId !== undefined) {
				const frame = all
					.find((violation) => violation.id === violationId)
					?.evidence_frames.find((candidate) => candidate.frame_id === frameId);
				if (!frame) return fail(res, 404, "EVIDENCE_NOT_FOUND", "Кадр не найден.");
				const scale = job.durationSec / FIXTURE_DURATION_SEC;
				const bytes = await loadFrame(frameFileIndex(frame.timestamp_sec, scale));
				res.writeHead(200, { "Content-Type": "image/jpeg", "Cache-Control": "no-store" });
				return void res.end(bytes);
			}
			if (violationId !== undefined) return fail(res, 404, "EVIDENCE_NOT_FOUND", "Событие не найдено.");

			const query = parsePaginationQuery(url);
			if (!query) return fail(res, 400, "BAD_REQUEST", "Некорректные параметры страницы.");
			const offset = (query.page - 1) * query.page_size;
			const page = ViolationsPageSchema.parse({
				job_id: job.id,
				items: all.slice(offset, offset + query.page_size),
				page: query.page,
				page_size: query.page_size,
				total: all.length,
			});
			return send(res, 200, page);
		}

		return fail(res, 400, "BAD_REQUEST", "Неизвестный маршрут.");
	};

	const loadFrame = async (index: number) => {
		let bytes = frameCache.get(index);
		if (!bytes) {
			bytes = await readFile(`${FRAMES_DIR}frame-${index}.jpg`);
			frameCache.set(index, bytes);
		}
		return bytes;
	};

	const juryView = async (job: Job, state: ReturnType<typeof snapshot>) => {
		if (state.status === "processing") return { job_id: job.id, status: "processing" };
		if (state.status === "failed") return { job_id: job.id, status: "failed", error: state.error };
		const violations = job.outcome === "violation" ? buildViolations(job.durationSec) : [];
		const scale = job.durationSec / FIXTURE_DURATION_SEC;
		return {
			job_id: job.id,
			status: "done",
			verdict: state.verdict,
			violations: await Promise.all(
				violations.map(async (violation) => ({
					type: violation.type,
					timecode_sec: violation.timecode_sec,
					description: violation.description,
					evidence_frames: await Promise.all(
						violation.evidence_frames.map(async (frame) => ({
							timestamp_sec: frame.timestamp_sec,
							image_base64: (await loadFrame(frameFileIndex(frame.timestamp_sec, scale))).toString("base64"),
						})),
					),
				})),
			),
		};
	};

	const server = createServer((req, res) => {
		handle(req, res).catch((error) => {
			console.error("[mock-analyzer]", error);
			if (!res.headersSent) fail(res, 500, "INTERNAL_ERROR", "Ошибка мок-анализатора.");
			else res.end();
		});
	});

	await new Promise<void>((resolve, reject) => {
		server.once("error", reject);
		server.listen(options.port ?? 4010, "127.0.0.1", resolve);
	});
	const address = server.address();
	const port = typeof address === "object" && address ? address.port : (options.port ?? 4010);

	return {
		server,
		port,
		close: () =>
			new Promise<void>((resolve) => {
				server.closeAllConnections();
				server.close(() => resolve());
			}),
	};
}
