import { useState } from "react";
import type { Observations } from "@/lib/api/observations";
import { Button } from "@/components/ui/button";
import { usePlayerStore } from "@/stores/player-store";
import type { OverlayMode } from "./observation-overlay";

const time = (t: number) =>
	`${Math.floor(t / 60)}:${Math.floor(t % 60)
		.toString()
		.padStart(2, "0")}`;

export function ObservationsPanel({
	data,
	mode,
	onMode,
}: {
	data?: Observations;
	mode: OverlayMode;
	onMode: (m: OverlayMode) => void;
}) {
	const [expanded, setExpanded] = useState(false);
	const labels = Object.fromEntries(
		data?.objects?.classes.map((c) => [c.id, c.name]) ?? [],
	);
	const intervals = data?.objects?.intervals ?? [];
	return (
		<section
			className="rounded-2xl border bg-background p-4"
			aria-label="Люди и предметы"
		>
			<div className="flex flex-wrap items-center justify-between gap-3">
				<h2 className="text-sm font-semibold">Люди и предметы</h2>
				<div
					className="flex flex-wrap gap-1"
					role="group"
					aria-label="Режим рамок"
				>
					{(
						[
							["resolved", "С учётом контекста"],
							["raw", "Ответ детектора"],
						] as const
					).map(([value, label]) => (
						<Button
							key={value}
							size="sm"
							variant={mode === value ? "secondary" : "ghost"}
							aria-pressed={mode === value}
							onClick={() => onMode(value)}
						>
							{label}
						</Button>
					))}
				</div>
			</div>
			{data?.people ? (
				<p className="mt-2 text-xs text-muted-foreground">
					Зелёный — банкир · синий — клиент · жёлтый пунктир — возможное
					отражение. Знак ? означает неопределённость.
				</p>
			) : (
				<p className="mt-2 text-sm text-muted-foreground">
					Наблюдения появятся после этапа отслеживания.
				</p>
			)}
			{data?.objects && (
				<>
					<p className="mt-3 text-xs leading-relaxed text-muted-foreground">
						{data.objects.limitation}
					</p>
					<Button
						variant="ghost"
						size="sm"
						className="mt-2"
						onClick={() => setExpanded(!expanded)}
						aria-expanded={expanded}
					>
						Интервалы предметов · {intervals.length} {expanded ? "↑" : "↓"}
					</Button>
					{expanded && (
						<div className="mt-2 max-h-80 overflow-auto divide-y">
							{intervals.length ? (
								intervals.map((item) => (
									<div
										key={item.id}
										className="flex items-start justify-between gap-4 py-3 text-xs"
									>
										<div>
											<span className="font-medium">
												{labels[item.class] ?? item.class}
											</span>
											<p className="mt-1 font-mono text-muted-foreground">
												{item.id} · наблюдался{" "}
												{item.observed_seconds.toFixed(1)} с
											</p>
										</div>
										<div className="flex max-w-[65%] flex-wrap justify-end gap-1">
											{item.intervals.map(([start, end]) => (
												<button
													key={start}
													type="button"
													className="rounded-md bg-secondary px-2 py-1 font-mono hover:bg-muted"
													onClick={() =>
														usePlayerStore.getState().controller?.seek(start)
													}
												>
													{time(start)}–{time(end)}
												</button>
											))}
										</div>
									</div>
								))
							) : (
								<p className="py-3 text-sm text-muted-foreground">
									Устойчивых треков предметов не найдено.
								</p>
							)}
						</div>
					)}
				</>
			)}
		</section>
	);
}
