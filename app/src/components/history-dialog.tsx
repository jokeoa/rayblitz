import { Link } from "@tanstack/react-router";
import { History, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Empty,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";
import { Item, ItemContent, ItemMedia, ItemTitle } from "@/components/ui/item";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VideoList } from "@/components/video-list";
import { useHistoryStore } from "@/stores/history-store";
import { useUiStore } from "@/stores/ui-store";

const RECENT_LIMIT = 8;

/** Sidebar "История": the latest videos, with the upload card pinned on top. */
export function HistoryDialog() {
	const open = useUiStore((state) => state.historyOpen);
	const setOpen = useUiStore((state) => state.setHistoryOpen);
	const openUpload = useUiStore((state) => state.openUpload);
	const entries = useHistoryStore((state) => state.entries);
	const recent = entries.slice(0, RECENT_LIMIT);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent className="sm:max-w-xl">
				<DialogHeader>
					<DialogTitle>История</DialogTitle>
					<DialogDescription>Последние загруженные видео.</DialogDescription>
				</DialogHeader>

				<Item
					variant="muted"
					size="sm"
					className="cursor-pointer border-dashed border-input bg-secondary hover:bg-secondary/70"
					render={<button type="button" onClick={openUpload} />}
				>
					<ItemMedia
						variant="icon"
						className="size-9 rounded-xl bg-background text-foreground shadow-card"
					>
						<Plus aria-hidden />
					</ItemMedia>
					<ItemContent>
						<ItemTitle>Загрузить новое видео +</ItemTitle>
					</ItemContent>
				</Item>

				{recent.length === 0 ? (
					<Empty className="border p-8">
						<EmptyHeader>
							<EmptyMedia variant="icon">
								<History aria-hidden />
							</EmptyMedia>
							<EmptyTitle>История пуста</EmptyTitle>
							<EmptyDescription>
								Здесь появятся видео, которые вы отправите на анализ.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				) : (
					<ScrollArea className="-mx-2 max-h-[min(24rem,50dvh)]">
						<VideoList
							entries={recent}
							variant="compact"
							onNavigate={() => setOpen(false)}
							className="px-2"
						/>
					</ScrollArea>
				)}

				{entries.length > RECENT_LIMIT ? (
					<Button
						variant="ghost"
						size="sm"
						className="justify-self-start"
						render={<Link to="/" onClick={() => setOpen(false)} />}
					>
						Все видео на дашборде
					</Button>
				) : null}
			</DialogContent>
		</Dialog>
	);
}
