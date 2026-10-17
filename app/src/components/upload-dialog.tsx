import { CircleAlert, FileVideo, Upload, X } from "lucide-react";
import { useId, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Item,
	ItemActions,
	ItemContent,
	ItemDescription,
	ItemMedia,
	ItemTitle,
} from "@/components/ui/item";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { useHealth } from "@/hooks/use-health";
import {
	uploadErrorMessage,
	useStartAnalysis,
	validateVideoFile,
} from "@/hooks/use-start-analysis";
import { isApiError } from "@/lib/api/client";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

/** Contract: new analyses are blocked while either service is not confirmed ready. */
function useUploadGate() {
	const { kind, health } = useHealth();
	if (kind === "ok") return { ready: true as const };
	const reason =
		kind === "checking"
			? "Проверяем доступность сервиса анализа."
			: kind === "unknown"
				? "Статус сервиса неизвестен: нет связи с сервером."
				: [health?.services.backend, health?.services.gpu_server]
						.filter((service) => service && service.status !== "ok")
						.map((service) => service?.message)
						.join(" ");
	return { ready: false as const, reason };
}

export function UploadDialog() {
	const open = useUiStore((state) => state.uploadOpen);
	const setOpen = useUiStore((state) => state.setUploadOpen);
	const inputId = useId();
	const inputRef = useRef<HTMLInputElement>(null);
	const [file, setFile] = useState<File | null>(null);
	const [localError, setLocalError] = useState<string | null>(null);
	const [dragging, setDragging] = useState(false);
	const gate = useUploadGate();

	const reset = () => {
		setFile(null);
		setLocalError(null);
		setDragging(false);
	};
	const mutation = useStartAnalysis({
		onAccepted: () => {
			setOpen(false);
			reset();
		},
	});

	const choose = (candidate: File | undefined) => {
		if (!candidate) return;
		mutation.reset();
		const problem = validateVideoFile(candidate);
		setLocalError(problem);
		setFile(problem ? null : candidate);
	};

	const serverError = mutation.error
		? isApiError(mutation.error)
			? uploadErrorMessage(mutation.error.code, mutation.error.message)
			: "Не удалось отправить файл."
		: null;
	const error = localError ?? serverError;
	const uploading = mutation.isPending;

	return (
		<Dialog
			open={open}
			onOpenChange={(next) => {
				// An upload in flight cannot be recalled, so the dialog stays until it settles.
				if (uploading) return;
				setOpen(next);
				if (!next) {
					reset();
					mutation.reset();
				}
			}}
		>
			<DialogContent showCloseButton={!uploading} className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Загрузка видео</DialogTitle>
					<DialogDescription>
						Один файл .mov до 100 МБ. Анализ запустится после загрузки.
					</DialogDescription>
				</DialogHeader>

				{file ? (
					<Item variant="outline" size="sm">
						<ItemMedia
							variant="icon"
							className="size-9 rounded-xl bg-secondary"
						>
							<FileVideo aria-hidden />
						</ItemMedia>
						<ItemContent className="min-w-0">
							<ItemTitle className="max-w-full truncate">{file.name}</ItemTitle>
							<ItemDescription className="tabular">
								{formatBytes(file.size)}
							</ItemDescription>
						</ItemContent>
						<ItemActions>
							<Button
								variant="ghost"
								size="icon-sm"
								aria-label="Убрать файл"
								disabled={uploading}
								onClick={reset}
							>
								<X aria-hidden />
							</Button>
						</ItemActions>
					</Item>
				) : (
					<label
						htmlFor={inputId}
						onDragOver={(event) => {
							event.preventDefault();
							setDragging(true);
						}}
						onDragLeave={() => setDragging(false)}
						onDrop={(event) => {
							event.preventDefault();
							setDragging(false);
							choose(event.dataTransfer.files[0]);
						}}
						className={cn(
							"flex cursor-pointer flex-col items-center gap-2 rounded-2xl border border-dashed border-input bg-secondary/50 px-6 py-10 text-center transition-colors hover:bg-secondary focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30",
							dragging && "border-ring bg-info-soft",
						)}
					>
						<Upload className="size-5 text-muted-foreground" aria-hidden />
						<span className="text-sm font-medium">
							Перетащите файл или выберите на диске
						</span>
						<span className="text-xs text-muted-foreground">Формат .mov</span>
						<input
							ref={inputRef}
							id={inputId}
							type="file"
							accept=".mov,video/quicktime"
							className="sr-only"
							onChange={(event) => {
								choose(event.target.files?.[0]);
								event.target.value = "";
							}}
						/>
					</label>
				)}

				{uploading ? (
					<Progress value={null} aria-label="Загрузка файла" className="gap-2">
						<span className="text-sm text-muted-foreground">
							Загружаем файл. Процент анализа появится после приёма.
						</span>
					</Progress>
				) : null}

				{error ? (
					<Alert variant="destructive">
						<CircleAlert aria-hidden />
						<AlertTitle>Не удалось отправить</AlertTitle>
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				) : null}

				{!gate.ready ? (
					<Alert>
						<CircleAlert aria-hidden />
						<AlertTitle>Загрузка недоступна</AlertTitle>
						<AlertDescription>{gate.reason}</AlertDescription>
					</Alert>
				) : null}

				<DialogFooter>
					<Button
						variant="outline"
						disabled={uploading}
						onClick={() => {
							setOpen(false);
							reset();
							mutation.reset();
						}}
					>
						Отмена
					</Button>
					<Button
						disabled={!file || !gate.ready || uploading}
						onClick={() => file && mutation.mutate(file)}
					>
						{uploading ? <Spinner data-icon="inline-start" /> : null}
						{uploading ? "Загружаем" : "Отправить на анализ"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
