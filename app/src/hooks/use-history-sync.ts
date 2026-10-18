import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { getHistory } from "@/lib/api/observations";
import { useHistoryStore } from "@/stores/history-store";

/** One durable server history, shared across authorized browsers. */
export function useHistorySync() {
	const result = useQuery({
		queryKey: ["history"],
		queryFn: ({ signal }) => getHistory(signal),
		refetchInterval: 3000,
		retry: 1,
	});
	const replace = useHistoryStore((state) => state.replace);
	useEffect(() => {
		if (result.data) replace(result.data.items);
	}, [result.data, replace]);
	return result;
}
