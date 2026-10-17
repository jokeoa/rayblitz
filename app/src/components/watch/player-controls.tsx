import {
	FastForward,
	Pause,
	Play,
	Rewind,
	SkipBack,
	SkipForward,
} from "lucide-react";
import { useMotionValueEvent } from "motion/react";
import { type ReactNode, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Violation } from "@/lib/api/contracts";
import { formatTimecode } from "@/lib/format";
import { playheadTime, usePlayerStore } from "@/stores/player-store";

const RATES = [0.5, 1, 1.5, 2] as const;
const SKIP_SECONDS = 10;

function ControlButton({
	label,
	onClick,
	disabled,
	children,
	primary = false,
}: {
	label: string;
	onClick: () => void;
	disabled?: boolean;
	children: ReactNode;
	primary?: boolean;
}) {
	return (
		<Tooltip>
			<TooltipTrigger
				render={
					<Button
						variant={primary ? "default" : "ghost"}
						size={primary ? "icon-lg" : "icon"}
						aria-label={label}
						disabled={disabled}
						onClick={onClick}
					/>
				}
			>
				{children}
			</TooltipTrigger>
			<TooltipContent>{label}</TooltipContent>
		</Tooltip>
	);
}

/** Current time label, written straight to the DOM so playback never re-renders it. */
function Clock() {
	const ref = useRef<HTMLSpanElement>(null);
	useEffect(() => {
		if (ref.current)
			ref.current.textContent = formatTimecode(playheadTime.get());
	}, []);
	useMotionValueEvent(playheadTime, "change", (seconds) => {
		if (ref.current) ref.current.textContent = formatTimecode(seconds);
	});
	return <span ref={ref} />;
}

export function PlayerControls({ violations }: { violations: Violation[] }) {
	const controller = usePlayerStore((state) => state.controller);
	const playing = usePlayerStore((state) => state.playing);
	const duration = usePlayerStore((state) => state.duration);
	const status = usePlayerStore((state) => state.status);
	const rate = usePlayerStore((state) => state.rate);
	const select = usePlayerStore((state) => state.select);
	const playable = status === "ready";
	const times = violations.map((violation) => violation.timecode_sec);

	const jump = (direction: "prev" | "next") => {
		if (!controller) return;
		const now = playheadTime.get();
		const target =
			direction === "next"
				? times.find((time) => time > now + 0.25)
				: [...times].reverse().find((time) => time < now - 0.75);
		if (target === undefined) return;
		controller.seek(target);
		const match = violations.find(
			(violation) => violation.timecode_sec === target,
		);
		if (match) select(match.id);
	};

	return (
		<div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
			<div className="flex items-center gap-1">
				<ControlButton
					label="Предыдущее событие"
					disabled={!controller || times.length === 0}
					onClick={() => jump("prev")}
				>
					<SkipBack aria-hidden />
				</ControlButton>
				<ControlButton
					label={`Назад на ${SKIP_SECONDS} секунд`}
					disabled={!controller}
					onClick={() => controller?.skip(-SKIP_SECONDS)}
				>
					<Rewind aria-hidden />
				</ControlButton>
				<ControlButton
					primary
					label={playing ? "Пауза" : "Воспроизвести"}
					disabled={!controller || !playable}
					onClick={() => controller?.toggle()}
				>
					{playing ? <Pause aria-hidden /> : <Play aria-hidden />}
				</ControlButton>
				<ControlButton
					label={`Вперёд на ${SKIP_SECONDS} секунд`}
					disabled={!controller}
					onClick={() => controller?.skip(SKIP_SECONDS)}
				>
					<FastForward aria-hidden />
				</ControlButton>
				<ControlButton
					label="Следующее событие"
					disabled={!controller || times.length === 0}
					onClick={() => jump("next")}
				>
					<SkipForward aria-hidden />
				</ControlButton>
			</div>

			<div className="flex items-center gap-3">
				<p className="font-mono text-sm tabular text-muted-foreground">
					<span className="sr-only">Текущее время: </span>
					<span className="text-foreground">
						<Clock />
					</span>
					{" / "}
					{formatTimecode(duration)}
				</p>
				<Select
					value={String(rate)}
					onValueChange={(value) => controller?.setRate(Number(value))}
					disabled={!playable}
				>
					<SelectTrigger
						size="sm"
						aria-label="Скорость воспроизведения"
						className="w-[4.5rem]"
					>
						<SelectValue>{(value: string) => `${value}x`}</SelectValue>
					</SelectTrigger>
					<SelectContent>
						{RATES.map((value) => (
							<SelectItem key={value} value={String(value)}>
								{value}x
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>
		</div>
	);
}
