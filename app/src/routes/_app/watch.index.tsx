import { createFileRoute, Navigate } from "@tanstack/react-router";
import { PlayCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";
import { useHistoryStore } from "@/stores/history-store";
import { useUiStore } from "@/stores/ui-store";

export const Route = createFileRoute("/_app/watch/")({ component: WatchIndex });

function WatchIndex() {
	const latest = useHistoryStore((state) => state.entries[0]);
	const openUpload = useUiStore((state) => state.openUpload);

	if (latest) {
		return (
			<Navigate to="/watch/$jobId" params={{ jobId: latest.jobId }} replace />
		);
	}
	return (
		<div className="mx-auto flex min-h-[70dvh] w-full max-w-xl items-center px-4">
			<Empty className="border">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<PlayCircle aria-hidden />
					</EmptyMedia>
					<EmptyTitle>Нечего смотреть</EmptyTitle>
					<EmptyDescription>
						Загрузите видео, и здесь появятся плеер, таймлайн событий и обзор.
					</EmptyDescription>
				</EmptyHeader>
				<EmptyContent>
					<Button onClick={openUpload}>
						<Plus data-icon="inline-start" aria-hidden />
						Загрузить новое видео
					</Button>
				</EmptyContent>
			</Empty>
		</div>
	);
}
