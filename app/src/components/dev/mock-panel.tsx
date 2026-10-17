import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { apiJson } from "@/lib/api/client";
import { type DevScenario, DevScenarioSchema } from "@/lib/api/dev-contracts";
import { startAnalysis } from "@/lib/api/review";
import { saveVideo } from "@/lib/video-blobs";
import { useHistoryStore } from "@/stores/history-store";
import cleanUrl from "../../../mock/samples/kassa-clean.mov?url";
import demoUrl from "../../../mock/samples/kassa-demo.mov?url";

const ENDPOINT = "/api/review/dev/mock-scenario";

const HEALTH_OPTIONS: Record<DevScenario["health"], string> = {
	ok: "Все сервисы работают",
	gpu_error: "GPU: модели загружаются",
	gpu_unknown: "GPU: статус неизвестен",
	backend_error: "Бэкенд недоступен",
	slow: "Медленный ответ health",
};

const OUTCOME_OPTIONS: Record<DevScenario["outcome"], string> = {
	auto: "По имени файла",
	violation: "Всегда с нарушениями",
	no_violation: "Всегда без нарушений",
	failed: "Всегда ошибка анализа",
};

/** Developer-only: flips the mock analyzer between states and uploads bundled samples. */
export function MockPanel() {
	const queryClient = useQueryClient();
	const navigate = useNavigate();
	const scenario = useQuery({
		queryKey: ["dev", "scenario"],
		queryFn: () => apiJson(ENDPOINT, DevScenarioSchema),
	});
	const change = useMutation({
		mutationFn: (patch: Partial<DevScenario>) =>
			apiJson(ENDPOINT, DevScenarioSchema, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ ...scenario.data, ...patch }),
			}),
		onSuccess: (next) => {
			queryClient.setQueryData(["dev", "scenario"], next);
			void queryClient.invalidateQueries({ queryKey: ["health"] });
		},
	});

	const uploadSample = async (url: string, name: string) => {
		try {
			const blob = await (await fetch(url)).blob();
			const file = new File([blob], name, { type: "video/quicktime" });
			const accepted = await startAnalysis(file);
			useHistoryStore.getState().add({
				jobId: accepted.job_id,
				fileName: file.name,
				sizeBytes: file.size,
				createdAt: Date.now(),
				status: "processing",
				percent: 0,
			});
			await saveVideo(accepted.job_id, file);
			void navigate({
				to: "/watch/$jobId",
				params: { jobId: accepted.job_id },
			});
		} catch (error) {
			toast.error(
				error instanceof Error ? error.message : "Не удалось загрузить пример",
			);
		}
	};

	return (
		<Popover>
			<PopoverTrigger
				render={
					<Button
						variant="outline"
						size="sm"
						className="fixed bottom-3 left-1/2 z-40 -translate-x-1/2 bg-background shadow-card"
					/>
				}
			>
				<FlaskConical aria-hidden />
				Mock
			</PopoverTrigger>
			<PopoverContent side="top" align="start" className="w-72 gap-3">
				<div className="flex flex-col gap-1.5">
					<span className="text-xs font-medium text-muted-foreground">
						Health
					</span>
					<Select
						value={scenario.data?.health ?? "ok"}
						onValueChange={(health) =>
							change.mutate({ health: health as DevScenario["health"] })
						}
					>
						<SelectTrigger className="w-full">
							<SelectValue>
								{(value: DevScenario["health"]) => HEALTH_OPTIONS[value]}
							</SelectValue>
						</SelectTrigger>
						<SelectContent>
							{Object.entries(HEALTH_OPTIONS).map(([value, label]) => (
								<SelectItem key={value} value={value}>
									{label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex flex-col gap-1.5">
					<span className="text-xs font-medium text-muted-foreground">
						Результат анализа
					</span>
					<Select
						value={scenario.data?.outcome ?? "auto"}
						onValueChange={(outcome) =>
							change.mutate({ outcome: outcome as DevScenario["outcome"] })
						}
					>
						<SelectTrigger className="w-full">
							<SelectValue>
								{(value: DevScenario["outcome"]) => OUTCOME_OPTIONS[value]}
							</SelectValue>
						</SelectTrigger>
						<SelectContent>
							{Object.entries(OUTCOME_OPTIONS).map(([value, label]) => (
								<SelectItem key={value} value={value}>
									{label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex flex-col gap-1.5">
					<span className="text-xs font-medium text-muted-foreground">
						Загрузить пример
					</span>
					<div className="flex gap-2">
						<Button
							variant="secondary"
							size="sm"
							className="flex-1"
							onClick={() => uploadSample(demoUrl, "kassa-demo.mov")}
						>
							kassa-demo
						</Button>
						<Button
							variant="secondary"
							size="sm"
							className="flex-1"
							onClick={() => uploadSample(cleanUrl, "kassa-clean.mov")}
						>
							kassa-clean
						</Button>
					</div>
				</div>
			</PopoverContent>
		</Popover>
	);
}
