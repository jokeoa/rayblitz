import { createFileRoute } from "@tanstack/react-router";
import { FileVideo, Plus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { HealthPanel } from "@/components/health-panel";
import { Button } from "@/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VideoList } from "@/components/video-list";
import {
	displayStatus,
	type HistoryEntry,
	useHistoryStore,
} from "@/stores/history-store";
import { useUiStore } from "@/stores/ui-store";

export const Route = createFileRoute("/_app/")({ component: Dashboard });

const FILTERS = [
	{ value: "all", label: "Все", test: () => true },
	{
		value: "processing",
		label: "В работе",
		test: (entry: HistoryEntry) => displayStatus(entry) === "processing",
	},
	{
		value: "violation",
		label: "С нарушениями",
		test: (entry: HistoryEntry) =>
			entry.status === "done" && entry.verdict === "violation",
	},
	{
		value: "clean",
		label: "Без нарушений",
		test: (entry: HistoryEntry) =>
			entry.status === "done" && entry.verdict === "no_violation",
	},
	{
		value: "failed",
		label: "Ошибки",
		test: (entry: HistoryEntry) => {
			const status = displayStatus(entry);
			return status === "failed" || status === "timeout";
		},
	},
] as const;

function Dashboard() {
	const reduce = useReducedMotion();
	const openUpload = useUiStore((state) => state.openUpload);
	const entries = useHistoryStore((state) => state.entries);
	const [filter, setFilter] =
		useState<(typeof FILTERS)[number]["value"]>("all");

	return (
		<motion.div
			initial={reduce ? false : { opacity: 0, y: 6 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
			className="mx-auto flex w-full max-w-[1400px] flex-col gap-8 px-4 py-6 md:px-8 md:py-8"
		>
			<header className="flex flex-wrap items-center justify-between gap-4">
				<div>
					<h1 className="text-2xl font-semibold tracking-tight">Дашборд</h1>
					<p className="mt-1 text-sm text-muted-foreground">
						Видео, результаты анализа и состояние сервисов.
					</p>
				</div>
				<Button onClick={openUpload}>
					<Plus data-icon="inline-start" aria-hidden />
					Загрузить новое видео
				</Button>
			</header>

			<HealthPanel />

			<section aria-labelledby="videos-title" className="flex flex-col gap-3">
				<h2
					id="videos-title"
					className="text-base font-semibold tracking-tight"
				>
					Видео
				</h2>

				{entries.length === 0 ? (
					<Empty className="border">
						<EmptyHeader>
							<EmptyMedia variant="icon">
								<FileVideo aria-hidden />
							</EmptyMedia>
							<EmptyTitle>Пока нет загруженных видео</EmptyTitle>
							<EmptyDescription>
								Отправьте файл .mov, и здесь появятся статус, вердикт и число
								событий.
							</EmptyDescription>
						</EmptyHeader>
						<EmptyContent>
							<Button onClick={openUpload}>
								<Plus data-icon="inline-start" aria-hidden />
								Загрузить новое видео
							</Button>
						</EmptyContent>
					</Empty>
				) : (
					<Tabs
						value={filter}
						onValueChange={(value) => setFilter(value as typeof filter)}
					>
						<TabsList className="h-auto max-w-full flex-wrap justify-start">
							{FILTERS.map(({ value, label, test }) => (
								<TabsTrigger key={value} value={value} className="flex-none">
									{label}
									<span className="font-mono text-xs tabular text-muted-foreground">
										{entries.filter(test).length}
									</span>
								</TabsTrigger>
							))}
						</TabsList>
						{FILTERS.map(({ value, test }) => {
							const rows = entries.filter(test);
							return (
								<TabsContent key={value} value={value}>
									{rows.length === 0 ? (
										<p className="rounded-2xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
											В этой категории пока ничего нет.
										</p>
									) : (
										<VideoList
											entries={rows}
											variant="full"
											className={
												rows.length >= 4 ? "grid xl:grid-cols-2" : undefined
											}
										/>
									)}
								</TabsContent>
							);
						})}
					</Tabs>
				)}
			</section>
		</motion.div>
	);
}
