import {
	type HTMLMotionProps,
	motion,
	useMotionValue,
	useReducedMotion,
	useTransform,
} from "motion/react";
import {
	type CSSProperties,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { Slider } from "@/components/ui/slider";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Violation } from "@/lib/api/contracts";
import { formatTimecode } from "@/lib/format";
import {
	createJellyValues,
	destroyJellyValues,
	jellyTo,
	useJellyTransform,
} from "@/lib/jelly";
import {
	buildLanes,
	type Lane,
	type MarkerTarget,
	markerTargets,
	rulerTicks,
} from "@/lib/timeline";
import { cn } from "@/lib/utils";
import { playheadTime, usePlayerStore } from "@/stores/player-store";

const ROW_HEIGHT = 22;
const LANE_PADDING = 4;
const RULER_HEIGHT = 24;

/** Same jelly as `JellyRadio`, tuned for 16px markers that must stay inside a 22px row. */
const MARKER_JELLY = {
	swell: 0.3,
	barge: 4,
	shrink: 0.05,
	jelly: 1,
	bounce: 0.25,
	stagger: 22,
	stiffness: 580,
};
/** Narrowest a marker is drawn: Tailwind's `min-w-3.5`. */
const MARKER_MIN_WIDTH = 14;

const REST: MarkerTarget = { x: 0, scale: 1, far: 0 };

/** A marker that swells and nudges its neighbours aside whenever it becomes the selected one. */
function Marker({
	target = REST,
	style,
	...props
}: Omit<HTMLMotionProps<"button">, "style"> & {
	target?: MarkerTarget;
	style?: CSSProperties;
}) {
	const reduce = useReducedMotion();
	const [values] = useState(createJellyValues);
	const transform = useJellyTransform(values);
	const far = useRef(target.far);
	far.current = target.far;
	useEffect(() => {
		jellyTo(values, target.x, target.scale, far.current, {
			...MARKER_JELLY,
			reduce,
		});
	}, [values, target.x, target.scale, reduce]);
	useEffect(() => () => destroyJellyValues(values), [values]);
	return (
		<motion.button type="button" style={{ ...style, transform }} {...props} />
	);
}

const laneHeight = (lane: Lane) =>
	lane.rows.length * ROW_HEIGHT + LANE_PADDING * 2;

/**
 * Multi-layer timeline. Each violation type is a layer, overlapping events of
 * one type stack into extra rows, and one slider spans every layer so the
 * playhead can be dragged anywhere across the whole stack.
 */
export function Timeline({
	violations,
	state,
	onSelect,
}: {
	violations: Violation[];
	/** `pending` while the analysis runs, `empty` when no events were found. */
	state: "pending" | "empty" | "ready" | "unavailable";
	onSelect: (violation: Violation) => void;
}) {
	const duration = usePlayerStore((state) => state.duration);
	const currentTime = usePlayerStore((state) => state.currentTime);
	const selectedId = usePlayerStore((state) => state.selectedViolationId);
	const controller = usePlayerStore((state) => state.controller);

	const safeDuration = duration > 0 ? duration : 0;
	const lanes = useMemo(
		() => buildLanes(violations, safeDuration * 0.012),
		[violations, safeDuration],
	);
	// While one event is chosen the others fall back to grey and light up red on hover.
	const hasSelection = useMemo(
		() => violations.some((violation) => violation.id === selectedId),
		[violations, selectedId],
	);
	const [trackWidth, setTrackWidth] = useState(0);
	const targets = useMemo(
		() =>
			markerTargets(lanes, selectedId, {
				...MARKER_JELLY,
				duration: safeDuration,
				trackWidth,
				minWidth: MARKER_MIN_WIDTH,
			}),
		[lanes, selectedId, safeDuration, trackWidth],
	);
	// One tick label needs about 64px, so a narrow track gets fewer, never overlapping ones.
	const ticks = useMemo(
		() => rulerTicks(safeDuration, Math.max(2, Math.floor(trackWidth / 64))),
		[safeDuration, trackWidth],
	);
	const lanesHeight = lanes.reduce((sum, lane) => sum + laneHeight(lane), 0);
	const bodyHeight = Math.max(lanesHeight, ROW_HEIGHT + LANE_PADDING * 2);

	// Playhead: a transform driven by motion values, so playback never re-renders React.
	const trackRef = useRef<HTMLDivElement>(null);
	const width = useMotionValue(0);
	const durationMv = useMotionValue(safeDuration);
	const x = useTransform(() =>
		durationMv.get() > 0
			? (playheadTime.get() / durationMv.get()) * width.get()
			: 0,
	);
	useEffect(() => durationMv.set(safeDuration), [safeDuration, durationMv]);
	useEffect(() => {
		const element = trackRef.current;
		if (!element) return;
		const observer = new ResizeObserver(([entry]) => {
			width.set(entry.contentRect.width);
			setTrackWidth(entry.contentRect.width);
		});
		observer.observe(element);
		width.set(element.getBoundingClientRect().width);
		setTrackWidth(element.getBoundingClientRect().width);
		return () => observer.disconnect();
	}, [width]);

	const empty = state !== "ready";
	const hint =
		state === "pending"
			? "События появятся после завершения анализа."
			: state === "empty"
				? "События не обнаружены."
				: state === "unavailable"
					? "События недоступны."
					: null;

	return (
		<div className="rounded-2xl border bg-card p-3 shadow-card">
			<div ref={trackRef} className="relative min-w-0">
				<div className="relative" style={{ height: RULER_HEIGHT }} aria-hidden>
					{ticks.map((tick) => (
						<span
							key={tick}
							className="absolute top-0 flex h-full flex-col justify-between"
							style={{ left: `${(tick / safeDuration) * 100}%` }}
						>
							<span className="font-mono text-[11px] leading-none tabular text-muted-foreground">
								{formatTimecode(tick)}
							</span>
							<span className="h-1.5 w-px bg-border" />
						</span>
					))}
				</div>

				<div className="relative" style={{ height: bodyHeight }}>
					{empty
						? null
						: lanes.map((lane) => (
								<div
									key={lane.type}
									className="relative border-t border-border/70 first:border-t-0"
									style={{ height: laneHeight(lane) }}
								>
									{lane.rows.map((row, rowIndex) => (
										<div
											key={row[0].violation.id}
											className="absolute inset-x-0"
											style={{
												top: LANE_PADDING + rowIndex * ROW_HEIGHT,
												height: ROW_HEIGHT,
											}}
										>
											{row.map((segment) => {
												const start = Math.min(segment.start, safeDuration);
												const end = Math.min(segment.end, safeDuration);
												const selected = selectedId === segment.violation.id;
												return (
													<Tooltip key={segment.violation.id}>
														<TooltipTrigger
															render={
																<Marker
																	target={targets.get(segment.violation.id)}
																	aria-label={`${segment.violation.type}, ${formatTimecode(segment.violation.timecode_sec)}`}
																	aria-pressed={selected}
																	onClick={() => onSelect(segment.violation)}
																	className={cn(
																		"absolute top-1/2 z-20 h-4 min-w-3.5 -translate-y-1/2 rounded-full outline-none transition-[background-color,box-shadow] hover:bg-destructive focus-visible:ring-2 focus-visible:ring-ring",
																		selected
																			? "bg-destructive ring-2 ring-info ring-offset-1 ring-offset-card"
																			: hasSelection
																				? "bg-muted-foreground/35"
																				: "bg-destructive/80",
																	)}
																	style={{
																		left: `${safeDuration > 0 ? (start / safeDuration) * 100 : 0}%`,
																		width: `${safeDuration > 0 ? ((end - start) / safeDuration) * 100 : 0}%`,
																	}}
																/>
															}
														/>
														<TooltipContent className="max-w-64 flex-col items-start gap-0.5">
															<span className="font-medium">
																{segment.violation.type}
															</span>
															<span className="font-mono tabular opacity-80">
																{formatTimecode(segment.violation.timecode_sec)}
															</span>
														</TooltipContent>
													</Tooltip>
												);
											})}
										</div>
									))}
								</div>
							))}
					{empty ? (
						<p className="flex h-full items-center text-xs text-muted-foreground">
							{hint}
						</p>
					) : null}

					{/* One slider across every layer. Its thumb is the keyboard focus target only. */}
					<Slider
						aria-label="Позиция воспроизведения"
						value={[Math.min(currentTime, safeDuration)]}
						min={0}
						max={safeDuration || 1}
						step={0.05}
						disabled={!controller || safeDuration === 0}
						thumbAlignment="center"
						onValueChange={(value) => {
							const next = Array.isArray(value) ? value[0] : value;
							controller?.seek(next);
						}}
						className="absolute inset-0 z-10"
						controlClassName="h-full cursor-pointer"
						trackClassName="h-full rounded-none bg-transparent"
						indicatorClassName="bg-transparent"
						thumbClassName="h-full w-3 rounded-sm bg-transparent shadow-none ring-0 hover:ring-0 focus-visible:ring-2"
					/>

					<motion.div
						aria-hidden
						className="pointer-events-none absolute top-[-4px] bottom-0 left-0 z-30 w-0.5 -translate-x-1/2 rounded-full bg-info"
						style={{ x }}
					>
						<span className="absolute -top-1 left-1/2 size-2 -translate-x-1/2 rounded-full bg-info" />
					</motion.div>
				</div>
			</div>
		</div>
	);
}
