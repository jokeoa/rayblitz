import { Link } from "@tanstack/react-router";
import { FileVideo } from "lucide-react";
import { JobStatusBadge } from "@/components/job-status-badge";
import {
	Item,
	ItemActions,
	ItemContent,
	ItemDescription,
	ItemGroup,
	ItemMedia,
	ItemTitle,
} from "@/components/ui/item";
import { Progress } from "@/components/ui/progress";
import { formatBytes, formatEvents, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { displayStatus, type HistoryEntry } from "@/stores/history-store";

/**
 * The single video list used by the history modal (`compact`) and the
 * dashboard (`full`): same rows, same links, same statuses.
 */
export function VideoList({
	entries,
	variant,
	onNavigate,
	className,
}: {
	entries: HistoryEntry[];
	variant: "compact" | "full";
	onNavigate?: () => void;
	className?: string;
}) {
	const now = Date.now();
	return (
		<ItemGroup className={cn("gap-2", className)}>
			{entries.map((entry) => {
				const status = displayStatus(entry, now);
				return (
					<Item
						key={entry.jobId}
						variant="outline"
						size={variant === "full" ? "default" : "sm"}
						render={
							<Link
								to="/watch/$jobId"
								params={{ jobId: entry.jobId }}
								onClick={onNavigate}
							/>
						}
					>
						<ItemMedia
							variant="icon"
							className="size-9 rounded-xl bg-secondary text-muted-foreground"
						>
							<FileVideo aria-hidden />
						</ItemMedia>
						<ItemContent className="min-w-0">
							<ItemTitle className="max-w-full truncate" title={entry.fileName}>
								{entry.fileName}
							</ItemTitle>
							<ItemDescription className="tabular">
								{formatBytes(entry.sizeBytes)} ·{" "}
								{formatRelative(entry.createdAt, now)}
							</ItemDescription>
							{status === "processing" ? (
								<Progress
									value={entry.percent}
									aria-label="Прогресс анализа"
									className="mt-1 max-w-56"
								/>
							) : null}
						</ItemContent>
						<ItemActions className="ml-auto flex-wrap justify-end">
							{variant === "full" &&
							status === "done" &&
							entry.verdict === "violation" ? (
								<span className="font-mono text-xs tabular text-muted-foreground">
									{formatEvents(entry.violationsCount ?? 0)}
								</span>
							) : null}
							<JobStatusBadge entry={entry} status={status} />
						</ItemActions>
					</Item>
				);
			})}
		</ItemGroup>
	);
}
