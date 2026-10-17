import type {
	AnalyzeAccepted,
	ApiErrorResponse,
	JobResponse,
	Progress,
	ViolationsPage,
} from "./contracts.ts";
import type { HealthResponse } from "./health-contracts.ts";
import type { JuryJobResponse } from "./jury-contracts.ts";

export const healthyExample = {
	status: "ok",
	checked_at: "2026-10-17T14:00:00Z",
	services: {
		backend: { status: "ok", message: "Бэкенд готов принимать задания." },
		gpu_server: { status: "ok", message: "GPU и модели готовы к анализу." },
	},
} satisfies HealthResponse;

export const gpuUnavailableExample = {
	status: "degraded",
	checked_at: "2026-10-17T14:00:10Z",
	services: {
		backend: { status: "ok", message: "Бэкенд доступен." },
		gpu_server: {
			status: "error",
			message: "GPU-сервер не ответил за 2 секунды.",
		},
	},
} satisfies HealthResponse;

export const backendUnavailableExample = {
	status: "unavailable",
	checked_at: "2026-10-17T14:00:20Z",
	services: {
		backend: { status: "error", message: "Не удалось связаться с бэкендом." },
		gpu_server: {
			status: "unknown",
			message: "Проверка GPU-сервера недоступна без бэкенда.",
		},
	},
} satisfies HealthResponse;

// Synthetic 1x1 gray JPEG, used only in the mandatory jury representation.
const exampleJpeg =
	"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwAooooA/9k=";

export const acceptedExample = { job_id: "3f2a9c1e" } satisfies AnalyzeAccepted;
const stagePlan = [
	{
		id: "prepare_video",
		label: "Подготовка видео",
		description: "Проверяем видеопоток и извлекаем кадры.",
	},
	{
		id: "detect_events",
		label: "Анализ событий",
		description: "Ищем визуальные признаки возможных нарушений.",
	},
	{
		id: "write_overview",
		label: "Подготовка обзора",
		description: "Локальная LLM формирует обзор проверенных результатов.",
	},
];
export const processingExample = {
	job_id: "3f2a9c1e",
	status: "processing",
	progress: {
		percent: 55,
		stages: [
			{ ...stagePlan[0], status: "done", percent: 100 },
			{ ...stagePlan[1], status: "running", percent: 60 },
			{ ...stagePlan[2], status: "pending", percent: 0 },
		],
	},
} satisfies JobResponse;
const completedProgress = {
	percent: 100 as const,
	stages: stagePlan.map((stage) => ({
		...stage,
		status: "done" as const,
		percent: 100 as const,
	})),
} satisfies Progress;
export const noViolationExample = {
	job_id: "3f2a9c1e",
	status: "done",
	progress: completedProgress,
	verdict: "no_violation",
	violations_count: 0,
	overview: {
		summary:
			"Синтетический пример обзора: в доступных для анализа фрагментах признаки нарушений не обнаружены.",
		limitations: [],
	},
} satisfies JobResponse;
export const violationExample = {
	job_id: "3f2a9c1e",
	status: "done",
	progress: completedProgress,
	verdict: "violation",
	violations_count: 2,
	overview: {
		summary:
			"Синтетический пример обзора: два события требуют проверки человеком. Описания и таймкоды приведены в списке событий.",
		limitations: [
			"Демонстрационные данные не являются результатом анализа видео.",
		],
	},
} satisfies JobResponse;
export const failedExample = {
	job_id: "3f2a9c1e",
	status: "failed",
	progress: {
		percent: 55,
		stages: [
			{ ...stagePlan[0], status: "done", percent: 100 },
			{ ...stagePlan[1], status: "failed", percent: 60 },
			{ ...stagePlan[2], status: "pending", percent: 0 },
		],
	},
	error: {
		code: "PROCESSING_TIMEOUT",
		message: "Не удалось завершить анализ за 5 минут.",
	},
} satisfies JobResponse;
const exampleRule = {
	text: "Демонстрационное требование, не реальная нормативная оценка.",
	sources: [
		{
			document_title: "Пример источника — не нормативный акт",
			section: null,
			url: "https://example.invalid/regulation",
		},
	],
};
export const violationsPageExample = {
	job_id: "3f2a9c1e",
	page: 1,
	page_size: 1,
	total: 2,
	items: [
		{
			id: "event_001",
			type: "Демонстрационное событие",
			timecode_sec: 44.2,
			description:
				"Синтетический пример описания наблюдаемого действия и основания для проверки.",
			rule: exampleRule,
			evidence_frames: [{ frame_id: "frame_001", timestamp_sec: 44.2 }],
		},
	],
} satisfies ViolationsPage;
export const secondPageExample = {
	job_id: "3f2a9c1e",
	page: 2,
	page_size: 1,
	total: 2,
	items: [
		{
			id: "event_002",
			type: "Другое демонстрационное событие",
			timecode_sec: 63.5,
			description:
				"Синтетическое описание второго события. Не является утверждением о нарушении.",
			rule: exampleRule,
			evidence_frames: [{ frame_id: "frame_002", timestamp_sec: 63.5 }],
		},
	],
} satisfies ViolationsPage;
export const emptyPageExample = {
	job_id: "3f2a9c1e",
	page: 1,
	page_size: 20,
	total: 0,
	items: [],
} satisfies ViolationsPage;
export const juryProcessingExample = {
	job_id: "3f2a9c1e",
	status: "processing",
} satisfies JuryJobResponse;
export const juryNoViolationExample = {
	job_id: "3f2a9c1e",
	status: "done",
	verdict: "no_violation",
	violations: [],
} satisfies JuryJobResponse;
export const juryViolationExample = {
	job_id: "3f2a9c1e",
	status: "done",
	verdict: "violation",
	violations: [...violationsPageExample.items, ...secondPageExample.items].map(
		(item) => ({
			type: item.type,
			timecode_sec: item.timecode_sec,
			description: item.description,
			evidence_frames: item.evidence_frames.map((frame) => ({
				timestamp_sec: frame.timestamp_sec,
				image_base64: exampleJpeg,
			})),
		}),
	),
} satisfies JuryJobResponse;
export const juryFailedExample = {
	job_id: "3f2a9c1e",
	status: "failed",
	error: failedExample.error,
} satisfies JuryJobResponse;
export const unauthorizedExample = {
	error: {
		code: "UNAUTHORIZED",
		message: "Неверный или отсутствующий API-ключ.",
	},
} satisfies ApiErrorResponse;
