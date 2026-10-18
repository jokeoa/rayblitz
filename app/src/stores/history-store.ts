import { create } from "zustand";
export type HistoryStatus = "processing" | "done" | "failed";
export type HistoryEntry = {
	jobId: string;
	fileName: string;
	sizeBytes: number;
	createdAt: number;
	startedAt?: number | null;
	queued?: boolean;
	playbackReady?: boolean;
	status: HistoryStatus;
	percent: number;
	verdict?: "violation" | "no_violation";
	violationsCount?: number;
	errorCode?: string;
};
type HistoryState = {
	entries: HistoryEntry[];
	replace: (entries: HistoryEntry[]) => void;
	add: (entry: HistoryEntry) => void;
	clear: () => void;
};
export const useHistoryStore = create<HistoryState>((set) => ({
	entries: [],
	replace: (entries) => set({ entries }),
	add: (entry) =>
		set((s) => ({
			entries: [entry, ...s.entries.filter((e) => e.jobId !== entry.jobId)],
		})),
	clear: () => set({ entries: [] }),
}));
