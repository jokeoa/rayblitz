import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { MAX_VIDEO_BYTES } from "@/lib/api/contracts";
import { startAnalysis } from "@/lib/api/review";
import { formatBytes } from "@/lib/format";
import { useHistoryStore } from "@/stores/history-store";

/** Client-side pre-check mirroring the contract; the server stays authoritative. */
export function validateVideoFile(file: File): string | null {
	if (!file.name.toLowerCase().endsWith(".mov")) {
		return "Принимаются только файлы .mov.";
	}
	if (file.size === 0) return "Файл пустой.";
	if (file.size > MAX_VIDEO_BYTES) {
		return `Файл ${formatBytes(file.size)} больше лимита 100 МБ.`;
	}
	return null;
}

export function useStartAnalysis(options: { onAccepted?: () => void } = {}) {
	const navigate = useNavigate();

	return useMutation({
		// One POST, no automatic retry: if the response is lost the outcome is unknown.
		retry: false,
		mutationFn: async (file: File) => ({
			accepted: await startAnalysis(file),
			file,
		}),
		onSuccess: ({ accepted, file }) => {
			useHistoryStore.getState().add({
				jobId: accepted.job_id,
				fileName: file.name,
				sizeBytes: file.size,
				createdAt: Date.now(),
				status: "processing",
				queued: true,
				percent: 0,
			});
			toast.success("Видео принято в обработку", {
				description: `Задание ${accepted.job_id}`,
			});
			options.onAccepted?.();
			void navigate({
				to: "/watch/$jobId",
				params: { jobId: accepted.job_id },
			});
		},
	});
}

export function uploadErrorMessage(code: string, fallback: string): string {
	switch (code) {
		case "FILE_TOO_LARGE":
			return "Размер видео превышает 100 МБ.";
		case "UNSUPPORTED_MEDIA_TYPE":
			return "Формат не поддерживается. Загрузите файл .mov.";
		case "INVALID_VIDEO":
			return "Не удалось прочитать видео. Проверьте, что файл не повреждён.";
		case "SERVICE_UNAVAILABLE":
			return "Сервис анализа временно недоступен. Повторите попытку позже.";
		case "NETWORK":
			return "Нет связи с сервером. Проверьте подключение и отправьте файл ещё раз.";
		default:
			return fallback;
	}
}
