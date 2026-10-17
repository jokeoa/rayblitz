const pad = (value: number) => String(Math.floor(value)).padStart(2, "0");

/** 83.4 -> "01:23", 3725 -> "1:02:05". Accepts raw seconds from the API. */
export function formatTimecode(seconds: number): string {
	const total = Math.max(0, Math.floor(seconds));
	const h = Math.floor(total / 3600);
	const m = Math.floor((total % 3600) / 60);
	const s = total % 60;
	return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function formatBytes(bytes: number): string {
	if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
	return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} МБ`;
}

const relative = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

export function formatRelative(timestamp: number, now = Date.now()): string {
	const diffSec = Math.round((timestamp - now) / 1000);
	const abs = Math.abs(diffSec);
	if (abs < 45) return "только что";
	if (abs < 3600) return relative.format(Math.round(diffSec / 60), "minute");
	if (abs < 86_400) return relative.format(Math.round(diffSec / 3600), "hour");
	return relative.format(Math.round(diffSec / 86_400), "day");
}

const clock = new Intl.DateTimeFormat("ru", { timeStyle: "medium" });
export const formatClock = (iso: string | number) =>
	clock.format(new Date(iso));

export function pluralize(
	count: number,
	forms: readonly [one: string, few: string, many: string],
): string {
	const mod100 = count % 100;
	const mod10 = count % 10;
	if (mod100 >= 11 && mod100 <= 14) return forms[2];
	if (mod10 === 1) return forms[0];
	if (mod10 >= 2 && mod10 <= 4) return forms[1];
	return forms[2];
}

export const formatEvents = (count: number) =>
	`${count} ${pluralize(count, ["событие", "события", "событий"])}`;
