import type { Violation } from "../../src/lib/api/contracts.ts";

/** Reference length the fixture timecodes are written for. They are scaled to the real upload. */
export const FIXTURE_DURATION_SEC = 90;
export const FRAME_FILE_TIMES = [6, 18, 31, 47, 59, 73, 84];

type FrameSpec = { id: string; t: number };
type EventSpec = {
	id: string;
	type: string;
	t: number;
	description: string;
	rule: string;
	section: string | null;
	frames: FrameSpec[];
};

const SOURCE_TITLE = "Условный регламент кассовой дисциплины (мок-данные)";

const EVENTS: EventSpec[] = [
	{
		id: "evt_001",
		type: "Касса без присмотра",
		t: 6.4,
		description:
			"Рабочее место кассира пусто, касса остаётся открытой и доступной со стороны зала.",
		rule: "Касса не должна оставаться открытой без присутствия кассира.",
		section: "п. 2.1",
		frames: [
			{ id: "fr_a", t: 5.8 },
			{ id: "fr_b", t: 6.4 },
		],
	},
	{
		id: "evt_002",
		type: "Операция без пробития чека",
		t: 17.9,
		description:
			"Сотрудник принимает наличные от покупателя и убирает их в ящик до того, как на экране появилась позиция чека.",
		rule: "Каждая приёмка наличных подтверждается кассовым чеком до размещения в ящике.",
		section: "п. 4.3",
		frames: [
			{ id: "fr_a", t: 17.2 },
			{ id: "fr_b", t: 18.6 },
		],
	},
	{
		id: "evt_003",
		type: "Посторонний в служебной зоне",
		t: 31.2,
		description:
			"За стойкой рядом с кассой находится человек без служебной формы и не участвует в обслуживании.",
		rule: "Доступ в кассовую зону разрешён только сотрудникам, закреплённым за ней.",
		section: null,
		frames: [
			{ id: "fr_a", t: 30.4 },
			{ id: "fr_b", t: 31.2 },
			{ id: "fr_c", t: 32.8 },
		],
	},
	{
		id: "evt_004",
		type: "Денежные средства вне кассовой зоны",
		t: 31.6,
		description:
			"Пачка купюр лежит на краю стойки со стороны покупателя, вне ящика и вне поля обзора сотрудника.",
		rule: "Наличные хранятся только в кассовом ящике или в закрытом лотке.",
		section: "п. 3.4",
		frames: [
			{ id: "fr_a", t: 31.6 },
			{ id: "fr_b", t: 33.1 },
		],
	},
	{
		id: "evt_005",
		type: "Касса без присмотра",
		t: 47.0,
		description:
			"Сотрудник отходит от стойки на несколько шагов, оставляя ящик выдвинутым.",
		rule: "Касса не должна оставаться открытой без присутствия кассира.",
		section: "п. 2.1",
		frames: [
			{ id: "fr_a", t: 46.2 },
			{ id: "fr_b", t: 48.9 },
		],
	},
	{
		id: "evt_006",
		type: "Операция без пробития чека",
		t: 47.9,
		description:
			"Покупатель получает товар, при этом чек на мониторе кассира не открыт.",
		rule: "Каждая приёмка наличных подтверждается кассовым чеком до размещения в ящике.",
		section: "п. 4.3",
		frames: [
			{ id: "fr_a", t: 47.9 },
			{ id: "fr_b", t: 49.5 },
		],
	},
	{
		id: "evt_007",
		type: "Денежные средства вне кассовой зоны",
		t: 58.5,
		description:
			"Наличные передаются через стойку без использования лотка, часть купюр остаётся на поверхности.",
		rule: "Наличные хранятся только в кассовом ящике или в закрытом лотке.",
		section: "п. 3.4",
		frames: [
			{ id: "fr_a", t: 57.9 },
			{ id: "fr_b", t: 59.4 },
		],
	},
	{
		id: "evt_008",
		type: "Посторонний в служебной зоне",
		t: 73.2,
		description:
			"Второй человек заходит за стойку и задерживается у кассового терминала.",
		rule: "Доступ в кассовую зону разрешён только сотрудникам, закреплённым за ней.",
		section: null,
		frames: [
			{ id: "fr_a", t: 72.6 },
			{ id: "fr_b", t: 73.2 },
			{ id: "fr_c", t: 74.5 },
		],
	},
	{
		id: "evt_009",
		type: "Операция без пробития чека",
		t: 18.4,
		description:
			"Повторная передача наличных без отображения чека на экране кассира.",
		rule: "Каждая приёмка наличных подтверждается кассовым чеком до размещения в ящике.",
		section: "п. 4.3",
		frames: [{ id: "fr_a", t: 18.4 }],
	},
];

export function frameFileIndex(timestamp: number, scale: number): number {
	const reference = timestamp / scale;
	let best = 0;
	for (let i = 1; i < FRAME_FILE_TIMES.length; i += 1) {
		if (
			Math.abs(FRAME_FILE_TIMES[i] - reference) <
			Math.abs(FRAME_FILE_TIMES[best] - reference)
		) {
			best = i;
		}
	}
	return best + 1;
}

const round = (value: number) => Math.round(value * 10) / 10;

/** Fixture events scaled to the real duration of the uploaded file. */
export function buildViolations(durationSec: number): Violation[] {
	const scale = durationSec / FIXTURE_DURATION_SEC;
	const clamp = (t: number) => round(Math.min(Math.max(t * scale, 0), durationSec));
	return EVENTS.map((event) => ({
		id: event.id,
		type: event.type,
		timecode_sec: clamp(event.t),
		description: event.description,
		rule: {
			text: event.rule,
			sources: [
				{
					document_title: SOURCE_TITLE,
					section: event.section,
					url: "https://example.invalid/regulation",
				},
			],
		},
		evidence_frames: event.frames.map((frame) => ({
			frame_id: frame.id,
			timestamp_sec: clamp(frame.t),
		})),
	})).sort(
		(a, b) =>
			a.timecode_sec - b.timecode_sec || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
	);
}

export const OVERVIEW_LIMITATION =
	"Данные сформированы мок-анализатором и не относятся к содержимому видео.";

export function overviewFor(
	verdict: "violation" | "no_violation",
	violations: Violation[],
) {
	if (verdict === "no_violation") {
		return {
			summary:
				"Демонстрационный обзор: в доступных фрагментах признаки нарушений не обнаружены. Это ответ мок-анализатора, он не основан на содержимом видео.",
			limitations: [OVERVIEW_LIMITATION],
		};
	}
	const counts = new Map<string, number>();
	for (const violation of violations) {
		counts.set(violation.type, (counts.get(violation.type) ?? 0) + 1);
	}
	const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
	return {
		summary: `Демонстрационный обзор: отмечено ${violations.length} эпизодов, которые стоит проверить вручную. Чаще всего повторяется «${top[0]}». Описания и таймкоды приведены в списке событий. Это ответ мок-анализатора, он не основан на содержимом видео.`,
		limitations: [
			OVERVIEW_LIMITATION,
			"Нормативные источники в этом режиме условные и не являются реальными документами.",
		],
	};
}
