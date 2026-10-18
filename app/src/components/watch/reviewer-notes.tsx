import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiJson } from "@/lib/api/client";

const Review = z.object({ reviewed: z.boolean(), notes: z.string() });
export function ReviewerNotes({ jobId }: { jobId: string }) {
	const path = `/api/review/jobs/${encodeURIComponent(jobId)}/review`;
	const queryClient = useQueryClient();
	const [notes, setNotes] = useState("");
	const [reviewed, setReviewed] = useState(false);
	const query = useQuery({
		queryKey: ["review", jobId],
		queryFn: () => apiJson(path, Review),
		staleTime: Infinity,
		refetchOnWindowFocus: false,
	});
	useEffect(() => {
		if (query.data) {
			setNotes(query.data.notes);
			setReviewed(query.data.reviewed);
		}
	}, [query.data]);
	const save = useMutation({
		mutationFn: () =>
			apiJson(path, Review, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ reviewed, notes }),
			}),
		onSuccess: (data) => {
			queryClient.setQueryData(["review", jobId], data);
			toast.success("Проверка сохранена");
		},
		onError: () => toast.error("Не удалось сохранить проверку"),
	});
	return (
		<section className="rounded-2xl border p-4">
			<h2 className="text-sm font-semibold">Моя проверка</h2>
			{query.isError && (
				<p className="mt-2 text-sm text-destructive">
					Не удалось загрузить заметки.{" "}
					<button
						type="button"
						className="underline"
						onClick={() => void query.refetch()}
					>
						Повторить
					</button>
				</p>
			)}
			<label className="mt-3 flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					disabled={query.isPending || query.isError || save.isPending}
					checked={reviewed}
					onChange={(e) => setReviewed(e.target.checked)}
				/>
				Видео проверено
			</label>
			<Textarea
				disabled={query.isPending || query.isError || save.isPending}
				aria-label="Заметки к проверке"
				placeholder="Ошибки ролей, пропущенные предметы, неверные события и таймкоды…"
				className="mt-3"
				value={notes}
				maxLength={8000}
				onChange={(e) => setNotes(e.target.value)}
			/>
			<div className="mt-3 flex items-center justify-between gap-3">
				<p className="text-xs text-muted-foreground">
					Заметки сохраняются отдельно от ответа модели.
				</p>
				<Button
					size="sm"
					disabled={save.isPending || query.isPending || query.isError}
					onClick={() => save.mutate()}
				>
					{save.isPending ? "Сохраняется…" : "Сохранить"}
				</Button>
			</div>
		</section>
	);
}
