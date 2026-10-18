import type { Observations } from "@/lib/api/observations";
import { usePlayerStore } from "@/stores/player-store";

export type OverlayMode = "resolved" | "raw";

function at<T extends { t: number }>(
	rows: T[],
	t: number,
	fps: number,
): T | undefined {
	let lo = 0,
		hi = rows.length;
	while (lo < hi) {
		const m = (lo + hi) >>> 1;
		if (rows[m].t <= t + 1e-8) lo = m + 1;
		else hi = m;
	}
	const row = rows[lo - 1];
	return row && t - row.t <= 1.1 / fps ? row : undefined;
}

const ROLES: Record<string, string> = {
	banker: "Банкир",
	customer: "Клиент",
	unknown: "Роль не определена",
};

export function ObservationOverlay({
	data,
	mode,
}: {
	data: Observations;
	mode: OverlayMode;
}) {
	const t = usePlayerStore((state) => state.currentTime);
	const people = data.people;
	if (!people) return null;
	const row = at(people.rows, t, people.fps);
	const objects = data.objects && at(data.objects.rows, t, data.objects.fps);
	const labels = Object.fromEntries(
		data.objects?.classes.map((c) => [c.id, c.name]) ?? [],
	);
	const predictions = mode === "raw" ? objects?.raw : objects?.tracks;
	const geometry = people.geometry.objects;
	return (
		<svg
			className="pointer-events-none absolute inset-0 size-full"
			viewBox={`0 0 ${people.info.width} ${people.info.height}`}
			preserveAspectRatio="xMidYMid meet"
			role="img"
			aria-label="Рамки людей и предметов на текущем таймкоде"
		>
			{geometry.desk && (
				<rect
					x={geometry.desk.box[0]}
					y={geometry.desk.box[1]}
					width={geometry.desk.box[2] - geometry.desk.box[0]}
					height={geometry.desk.box[3] - geometry.desk.box[1]}
					fill="none"
					stroke="#e2e8f0"
					strokeWidth={1}
					strokeDasharray="6 5"
				/>
			)}
			{geometry.desk?.side_divider && (
				<line
					x1={geometry.desk.side_divider[0][0]}
					y1={geometry.desk.side_divider[0][1]}
					x2={geometry.desk.side_divider[1][0]}
					y2={geometry.desk.side_divider[1][1]}
					stroke="#e2e8f0"
					strokeDasharray="4 4"
				/>
			)}
			{row?.tracks.map((p) => {
				const reflection = p.classification.possible_reflection;
				const color = reflection
					? "#fbbf24"
					: p.classification.role === "banker"
						? "#34d399"
						: p.classification.role === "customer"
							? "#60a5fa"
							: "#cbd5e1";
				const label = reflection
					? "Возможное отражение"
					: `${p.person_id ?? `T${p.id}`} · ${ROLES[p.classification.role] ?? p.classification.role}${p.association.usable_for_actions ? "" : " ?"}`;
				return (
					<g key={p.id}>
						<rect
							x={p.box[0]}
							y={p.box[1]}
							width={p.box[2] - p.box[0]}
							height={p.box[3] - p.box[1]}
							fill="none"
							stroke={color}
							strokeWidth={2}
							strokeDasharray={reflection ? "5 4" : undefined}
						/>
						<text
							x={p.box[0] + 2}
							y={Math.max(12, p.box[1] - 5)}
							fill={color}
							stroke="#111"
							strokeWidth={2}
							paintOrder="stroke"
							fontSize={11}
						>
							{label}
						</text>
					</g>
				);
			})}
			{predictions
				?.filter((o) => o.score >= 0.15)
				.map((o, i) => (
					<g key={`${o.id ?? o.class}-${i}`}>
						<rect
							x={o.box[0]}
							y={o.box[1]}
							width={o.box[2] - o.box[0]}
							height={o.box[3] - o.box[1]}
							fill="none"
							stroke={o.semantic_status === "uncertain" ? "#fb923c" : "#e879f9"}
							strokeWidth={1.5}
						/>
						<text
							x={o.box[0] + 1}
							y={Math.max(10, o.box[1] - 3)}
							fill="#f5d0fe"
							stroke="#111"
							strokeWidth={2}
							paintOrder="stroke"
							fontSize={9}
						>
							{labels[o.class] ?? o.class}
							{["cash", "card", "packaging", "stamp"].includes(o.class)
								? " ?"
								: ""}
						</text>
					</g>
				))}
		</svg>
	);
}
