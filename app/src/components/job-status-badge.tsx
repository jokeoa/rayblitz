import { CircleAlert, LoaderCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { VerdictBadge } from "@/components/verdict-badge";
import type { HistoryStatus, HistoryEntry } from "@/stores/history-store";

/** Status chip shared by the history modal and the dashboard list. */
export function JobStatusBadge({
	entry,
	status,
}: {
	entry: HistoryEntry;
	status: HistoryStatus;
}) {
	switch (status) {
		case "processing":
			return (
				<Badge variant="secondary" className="tabular">
					<LoaderCircle
						className="animate-spin motion-reduce:animate-none"
						aria-hidden
					/>
					{entry.queued ? "В очереди" : `Анализ ${Math.floor(entry.percent)}%`}
				</Badge>
			);
		case "failed":
			return (
				<Badge variant="destructive">
					<CircleAlert aria-hidden />
					Ошибка
				</Badge>
			);
		case "done":
			return entry.verdict ? (
				<VerdictBadge verdict={entry.verdict} />
			) : (
				<Badge variant="secondary">Готово</Badge>
			);
	}
}
