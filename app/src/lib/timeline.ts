import type { Violation } from "@/lib/api/contracts";

export type Segment = {
	violation: Violation;
	start: number;
	end: number;
};

export type Lane = {
	type: string;
	/** Packed sub-rows so overlapping events of one type never hide each other. */
	rows: Segment[][];
};

/** An event spans from its first to its last evidence frame (or the timecode itself). */
export function segmentOf(violation: Violation): Segment {
	const times = [
		violation.timecode_sec,
		...violation.evidence_frames.map((frame) => frame.timestamp_sec),
	];
	return {
		violation,
		start: Math.min(...times),
		end: Math.max(...times),
	};
}

/**
 * One lane per violation type, in order of first appearance. Inside a lane,
 * events are packed greedily into rows; `minSpan` keeps point events from
 * colliding visually at their rendered minimum width.
 */
export function buildLanes(violations: Violation[], minSpan: number): Lane[] {
	const byType = new Map<string, Segment[]>();
	for (const violation of violations) {
		const list = byType.get(violation.type) ?? [];
		list.push(segmentOf(violation));
		byType.set(violation.type, list);
	}

	const lanes: Lane[] = [];
	for (const [type, segments] of byType) {
		segments.sort((a, b) => a.start - b.start || a.end - b.end);
		const rows: Segment[][] = [];
		const rowEnds: number[] = [];
		for (const segment of segments) {
			let index = rowEnds.findIndex((end) => end <= segment.start);
			if (index === -1) {
				index = rows.length;
				rows.push([]);
				rowEnds.push(Number.NEGATIVE_INFINITY);
			}
			rows[index].push(segment);
			rowEnds[index] = Math.max(segment.end, segment.start + minSpan);
		}
		lanes.push({ type, rows });
	}
	return lanes.sort((a, b) => a.rows[0][0].start - b.rows[0][0].start);
}

const TICK_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

/** Ruler ticks: the smallest "nice" step that keeps `maxTicks` labels or fewer. */
export function rulerTicks(duration: number, maxTicks = 10): number[] {
	if (!Number.isFinite(duration) || duration <= 0) return [];
	const step =
		TICK_STEPS.find((candidate) => duration / candidate <= maxTicks) ?? 3600;
	const ticks: number[] = [];
	for (let t = 0; t < duration; t += step) ticks.push(t);
	return ticks;
}

export type MarkerTarget = {
	/** Horizontal shift in px away from the chosen marker. */
	x: number;
	scale: number;
	/** Distance from the chosen marker in time order, for the stagger delay. */
	far: number;
};

export type MarkerLayout = {
	duration: number;
	/** Rendered width of the track in px. */
	trackWidth: number;
	/** Narrowest a marker is ever drawn, in px. */
	minWidth: number;
	swell: number;
	barge: number;
	shrink: number;
};

/**
 * Where every marker should rest once `selectedId` is chosen, the way
 * `JellyRadio` lays out its chips: the chosen marker swells, the rest give up a
 * little, and neighbours in the same row that the swell would overlap step
 * aside. Markers keep their true position when they have room to spare.
 */
export function markerTargets(
	lanes: Lane[],
	selectedId: string | null,
	layout: MarkerLayout,
): Map<string, MarkerTarget> {
	const { duration, trackWidth, minWidth, swell, barge, shrink } = layout;
	const ordered = lanes
		.flatMap((lane) => lane.rows.flat())
		.sort((a, b) => a.start - b.start || a.end - b.end);
	const selectedRank = ordered.findIndex(
		(segment) => segment.violation.id === selectedId,
	);
	const targets = new Map<string, MarkerTarget>();
	if (selectedRank === -1) {
		for (const segment of ordered)
			targets.set(segment.violation.id, { x: 0, scale: 1, far: 0 });
		return targets;
	}

	const selected = ordered[selectedRank];
	const toPx = (seconds: number) =>
		duration > 0
			? (Math.min(Math.max(seconds, 0), duration) / duration) * trackWidth
			: 0;
	const left = (segment: Segment) => toPx(segment.start);
	const right = (segment: Segment) =>
		left(segment) + Math.max(minWidth, toPx(segment.end) - toPx(segment.start));
	const room = ((right(selected) - left(selected)) * swell) / 2 + barge;
	const row = lanes
		.flatMap((lane) => lane.rows)
		.find((candidate) => candidate.includes(selected));

	ordered.forEach((segment, rank) => {
		const id = segment.violation.id;
		let x = 0;
		if (segment !== selected && row?.includes(segment)) {
			const after = segment.start >= selected.start;
			const gap = after
				? left(segment) - right(selected)
				: left(selected) - right(segment);
			x = (after ? 1 : -1) * Math.max(0, room - gap);
		}
		targets.set(id, {
			x,
			scale: segment === selected ? 1 + swell : 1 - shrink,
			far: Math.abs(rank - selectedRank),
		});
	});
	return targets;
}
