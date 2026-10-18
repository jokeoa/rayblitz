import { CircleAlert, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { StageProgress } from "@/components/stage-progress";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictBadge } from "@/components/verdict-badge";
import { ViolationCard } from "@/components/watch/violation-card";
import { isApiError } from "@/lib/api/client";
import type { JobResponse, Violation } from "@/lib/api/contracts";
import { formatEvents, formatTimecode } from "@/lib/format";
import { usePlayerStore } from "@/stores/player-store";

export type ReviewState = {
	job: JobResponse | undefined;
	jobError: unknown;
	violations: Violation[] | undefined;
	violationsLoading: boolean;
	violationsError: boolean;
	onRefresh: () => void;
	refreshing: boolean;
	onBack: () => void;
	onSelect: (violation: Violation) => void;
};

function Overview({ job }: { job: Extract<JobResponse, { status: "done" }> }) {
	const { summary, limitations } = job.overview;
	return (
		<section aria-labelledby="overview-title" className="flex flex-col gap-3">
			<div className="flex items-center gap-2">
				<Sparkles className="size-4 text-info" aria-hidden />
				<h2
					id="overview-title"
					className="text-sm font-semibold tracking-tight"
				>
					AI Overview
				</h2>
			</div>
			<VerdictBadge verdict={job.verdict} className="self-start" />
			<p className="text-sm leading-relaxed whitespace-pre-line">{summary}</p>
			{limitations.length > 0 && (
				<details className="text-xs leading-relaxed text-muted-foreground">
					<summary className="cursor-pointer font-medium">
						Ограничения анализа · {limitations.length}
					</summary>
					<ul className="mt-2 list-disc space-y-2 pl-4">
						{limitations.map((item, index) => (
							<li key={index}>{item}</li>
						))}
					</ul>
				</details>
			)}
		</section>
	);
}

function ViolationList({
	jobId,
	state,
}: {
	jobId: string;
	state: ReviewState;
}) {
	const selectedId = usePlayerStore((s) => s.selectedViolationId);
	const select = usePlayerStore((s) => s.select);
	const controller = usePlayerStore((s) => s.controller);
	const { violations, violationsLoading, violationsError } = state;

	useEffect(() => {
		if (!selectedId) return;
		document.getElementById(`violation-${selectedId}`)?.scrollIntoView({
			block: "nearest",
			behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
				? "auto"
				: "smooth",
		});
	}, [selectedId]);

	if (violationsLoading) {
		return (
			<div className="flex flex-col gap-2">
				<Skeleton className="h-12 w-full rounded-2xl" />
				<Skeleton className="h-12 w-full rounded-2xl" />
				<Skeleton className="h-12 w-full rounded-2xl" />
			</div>
		);
	}
	if (violationsError) {
		return (
			<Alert variant="destructive">
				<CircleAlert aria-hidden />
				<AlertTitle>Не удалось загрузить события</AlertTitle>
				<AlertDescription>
					<Button
						variant="outline"
						size="sm"
						className="mt-2"
						onClick={state.onRefresh}
					>
						Повторить
					</Button>
				</AlertDescription>
			</Alert>
		);
	}
	if (!violations || violations.length === 0) {
		return (
			<p className="rounded-2xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
				События не обнаружены.
			</p>
		);
	}

	return (
		<Accordion
			className="gap-2 overflow-visible rounded-none border-0"
			value={selectedId ? [selectedId] : []}
			onValueChange={(value) => {
				const next = (value[0] as string | undefined) ?? null;
				select(next);
				const violation = violations.find((item) => item.id === next);
				if (violation) controller?.seek(violation.timecode_sec);
			}}
		>
			{violations.map((violation) => (
				<AccordionItem
					key={violation.id}
					value={violation.id}
					id={`violation-${violation.id}`}
					className="overflow-hidden rounded-2xl border bg-card shadow-card not-last:border-b data-open:bg-card"
				>
					<AccordionTrigger className="items-center gap-3 px-3.5 py-3 hover:no-underline">
						<span className="rounded-full bg-secondary px-2 py-0.5 font-mono text-xs tabular">
							{formatTimecode(violation.timecode_sec)}
						</span>
						<span className="line-clamp-2 min-w-0 flex-1 text-sm font-medium">
							{violation.type}
						</span>
					</AccordionTrigger>
					<AccordionContent className="px-3.5">
						<ViolationCard jobId={jobId} violation={violation} />
					</AccordionContent>
				</AccordionItem>
			))}
		</Accordion>
	);
}

/** Right-hand column: job state, AI overview and the violation cards. */
export function ReviewPanel({
	jobId,
	state,
}: {
	jobId: string;
	state: ReviewState;
}) {
	const { job, jobError } = state;

	let body: React.ReactNode;
	if (!job && isApiError(jobError) && jobError.status === 404) {
		body = (
			<Alert>
				<CircleAlert aria-hidden />
				<AlertTitle>Задание не найдено</AlertTitle>
				<AlertDescription>
					<p>Сервер не знает этого задания. Возможно, данные были удалены.</p>
					<Button
						variant="outline"
						size="sm"
						className="mt-3"
						onClick={state.onBack}
					>
						К списку видео
					</Button>
				</AlertDescription>
			</Alert>
		);
	} else if (!job && jobError) {
		body = (
			<Alert variant="destructive">
				<CircleAlert aria-hidden />
				<AlertTitle>Не удалось получить статус</AlertTitle>
				<AlertDescription>
					<p>
						{isApiError(jobError)
							? jobError.message
							: "Попробуйте обновить страницу."}
					</p>
					<Button
						variant="outline"
						size="sm"
						className="mt-3"
						onClick={state.onRefresh}
					>
						Обновить
					</Button>
				</AlertDescription>
			</Alert>
		);
	} else if (!job) {
		body = (
			<div className="flex flex-col gap-3">
				<Skeleton className="h-5 w-32" />
				<Skeleton className="h-5 w-full" />
				<Skeleton className="h-24 w-full rounded-2xl" />
			</div>
		);
	} else if (job.status === "processing") {
		body = (
			<div className="flex flex-col gap-4">
				<h2 className="text-sm font-semibold tracking-tight">Идёт анализ</h2>
				<StageProgress progress={job.progress} />
			</div>
		);
	} else if (job.status === "failed") {
		body = (
			<div className="flex flex-col gap-4">
				<Alert variant="destructive">
					<CircleAlert aria-hidden />
					<AlertTitle>Анализ не завершён</AlertTitle>
					<AlertDescription>{job.error.message}</AlertDescription>
				</Alert>
				<StageProgress progress={job.progress} />
			</div>
		);
	} else {
		body = (
			<div className="flex flex-col gap-6">
				<Overview job={job} />
				<section
					aria-labelledby="violations-title"
					className="flex flex-col gap-3"
				>
					<div className="flex items-baseline justify-between gap-2">
						<h2
							id="violations-title"
							className="text-sm font-semibold tracking-tight"
						>
							Нарушения
						</h2>
						<span className="text-xs tabular text-muted-foreground">
							{formatEvents(job.violations_count)}
						</span>
					</div>
					<ViolationList jobId={jobId} state={state} />
				</section>
			</div>
		);
	}

	return <div className="p-4 md:p-5">{body}</div>;
}
