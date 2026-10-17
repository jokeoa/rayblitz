import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { PlayerControls } from "@/components/watch/player-controls";
import { ReviewPanel, type ReviewState } from "@/components/watch/review-panel";
import { Timeline } from "@/components/watch/timeline";
import { VideoPlayer } from "@/components/watch/video-player";
import { useVideoSource } from "@/hooks/use-video-source";
import { PROCESSING_DEADLINE_MS, type Violation } from "@/lib/api/contracts";
import { jobQuery, violationsQuery } from "@/lib/api/queries";
import { formatBytes, formatRelative } from "@/lib/format";
import { deleteVideo } from "@/lib/video-blobs";
import { useHistoryStore } from "@/stores/history-store";
import { usePlayerStore } from "@/stores/player-store";

export const Route = createFileRoute("/_app/watch/$jobId")({
	component: WatchPage,
});

const EMPTY: Violation[] = [];

function WatchPage() {
	const { jobId } = Route.useParams();
	const navigate = useNavigate();
	const entry = useHistoryStore((state) =>
		state.entries.find((e) => e.jobId === jobId),
	);
	const removeEntry = useHistoryStore((state) => state.remove);

	const job = useQuery(jobQuery(jobId, entry?.createdAt ?? null));
	const done = job.data?.status === "done" ? job.data : null;
	const hasEvents = (done?.violations_count ?? 0) > 0;
	const violations = useQuery({
		...violationsQuery(jobId),
		enabled: hasEvents,
	});
	const source = useVideoSource(jobId);

	useEffect(() => {
		usePlayerStore.getState().open(jobId);
	}, [jobId]);

	const events = hasEvents ? (violations.data ?? EMPTY) : EMPTY;

	// Preview fallback: the timeline still needs a length when the file cannot play.
	const fallbackDuration = useMemo(() => {
		const times = events.flatMap((v) => [
			v.timecode_sec,
			...v.evidence_frames.map((f) => f.timestamp_sec),
		]);
		return times.length > 0 ? Math.ceil(Math.max(...times) * 1.05) : 0;
	}, [events]);

	const select = (violation: Violation) => {
		const player = usePlayerStore.getState();
		player.select(violation.id);
		player.controller?.seek(violation.timecode_sec);
	};

	const timedOut =
		job.data?.status === "processing" &&
		entry !== undefined &&
		Date.now() - entry.createdAt > PROCESSING_DEADLINE_MS;

	const state: ReviewState = {
		job: job.data,
		jobError: job.error,
		violations: violations.data,
		violationsLoading: hasEvents && violations.isPending,
		violationsError: violations.isError,
		timedOut,
		onRefresh: () => {
			void job.refetch();
			if (violations.isError) void violations.refetch();
		},
		refreshing: job.isFetching,
		onRemove: () => {
			removeEntry(jobId);
			void deleteVideo(jobId);
			void navigate({ to: "/watch" });
		},
		onSelect: select,
	};

	const timelineState = done
		? hasEvents
			? "ready"
			: "empty"
		: job.data?.status === "failed" || (!job.data && job.error)
			? "unavailable"
			: "pending";

	return (
		<div className="grid flex-1 xl:h-svh xl:flex-none xl:grid-cols-[minmax(0,1fr)_26rem] xl:grid-rows-[minmax(0,1fr)] xl:overflow-hidden">
			<div className="flex min-w-0 flex-col gap-4 p-4 md:p-6 xl:overflow-y-auto">
				<header className="flex flex-wrap items-start justify-between gap-3">
					<div className="min-w-0">
						<h1
							className="truncate text-xl font-semibold tracking-tight"
							title={entry?.fileName}
						>
							{entry?.fileName ?? `Задание ${jobId}`}
						</h1>
						<p className="mt-1 text-sm tabular text-muted-foreground">
							{entry
								? `${formatBytes(entry.sizeBytes)} · загружено ${formatRelative(entry.createdAt)}`
								: "Видео не найдено в истории этого браузера"}
						</p>
					</div>
					{job.data?.status === "failed" ? (
						<Badge variant="destructive">Ошибка анализа</Badge>
					) : job.data?.status === "processing" ? (
						<Badge variant="secondary" className="tabular">
							Анализ {Math.floor(job.data.progress.percent)}%
						</Badge>
					) : null}
				</header>

				<VideoPlayer source={source} fallbackDuration={fallbackDuration} />
				<PlayerControls violations={events} />
				<Timeline violations={events} state={timelineState} onSelect={select} />
			</div>

			<aside
				aria-label="Результат анализа"
				className="min-w-0 border-t bg-sidebar/50 xl:overflow-y-auto xl:border-t-0 xl:border-l"
			>
				<ReviewPanel jobId={jobId} state={state} />
			</aside>
		</div>
	);
}
