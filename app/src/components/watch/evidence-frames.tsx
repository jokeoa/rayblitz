import { ImageOff } from "lucide-react";
import { useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { EvidenceFrame } from "@/lib/api/contracts";
import { frameUrl } from "@/lib/api/review";
import { formatTimecode } from "@/lib/format";
import { cn } from "@/lib/utils";
import { usePlayerStore } from "@/stores/player-store";

function FrameThumb({
	jobId,
	violationId,
	frame,
}: {
	jobId: string;
	violationId: string;
	frame: EvidenceFrame;
}) {
	const [state, setState] = useState<"loading" | "ready" | "error">("loading");
	const controller = usePlayerStore((s) => s.controller);

	return (
		<button
			type="button"
			disabled={!controller}
			onClick={() => {
				controller?.pause();
				controller?.seek(frame.timestamp_sec);
			}}
			className="group/frame flex flex-col gap-1 text-left outline-none"
			aria-label={`Перейти к кадру на ${formatTimecode(frame.timestamp_sec)}`}
		>
			<span
				className={cn(
					"relative block aspect-video w-full overflow-hidden rounded-lg bg-secondary ring-1 ring-border transition-shadow group-hover/frame:ring-2 group-hover/frame:ring-ring group-focus-visible/frame:ring-2 group-focus-visible/frame:ring-ring",
				)}
			>
				{state === "loading" ? (
					<Skeleton className="absolute inset-0 rounded-none" />
				) : null}
				{state === "error" ? (
					<span className="absolute inset-0 grid place-items-center text-muted-foreground">
						<ImageOff className="size-4" aria-hidden />
					</span>
				) : (
					<img
						src={frameUrl(jobId, violationId, frame.frame_id)}
						alt=""
						loading="lazy"
						decoding="async"
						onLoad={() => setState("ready")}
						onError={() => setState("error")}
						className={cn(
							"size-full object-cover transition-opacity",
							state === "ready" ? "opacity-100" : "opacity-0",
						)}
					/>
				)}
			</span>
			<span className="font-mono text-[11px] tabular text-muted-foreground">
				{formatTimecode(frame.timestamp_sec)}
			</span>
		</button>
	);
}

/** One to three evidence frames; JPEG bytes come from the frame endpoint, never from JSON. */
export function EvidenceFrames({
	jobId,
	violationId,
	frames,
}: {
	jobId: string;
	violationId: string;
	frames: EvidenceFrame[];
}) {
	return (
		<div
			className={cn(
				"grid gap-2",
				frames.length === 1
					? "grid-cols-1"
					: frames.length === 2
						? "grid-cols-2"
						: "grid-cols-3",
			)}
		>
			{frames.map((frame) => (
				<FrameThumb
					key={frame.frame_id}
					jobId={jobId}
					violationId={violationId}
					frame={frame}
				/>
			))}
		</div>
	);
}
