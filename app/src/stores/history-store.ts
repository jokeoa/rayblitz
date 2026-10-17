import { create } from "zustand";
import { createJSONStorage, devtools, persist } from "zustand/middleware";
import { PROCESSING_DEADLINE_MS } from "@/lib/api/contracts";
import { DEV_TOOLS } from "@/lib/app-mode";

export type HistoryStatus = "processing" | "done" | "failed";

export type HistoryEntry = {
	jobId: string;
	fileName: string;
	sizeBytes: number;
	/** Client clock at the moment the POST was accepted (202). */
	createdAt: number;
	status: HistoryStatus;
	/** Overall backend progress while processing, 0-100. */
	percent: number;
	verdict?: "violation" | "no_violation";
	violationsCount?: number;
	errorCode?: string;
};

/** What the list shows: `timeout` is a UI state, not a backend status. */
export type DisplayStatus = HistoryStatus | "timeout";

export function displayStatus(
	entry: HistoryEntry,
	now = Date.now(),
): DisplayStatus {
	if (
		entry.status === "processing" &&
		now - entry.createdAt > PROCESSING_DEADLINE_MS
	) {
		return "timeout";
	}
	return entry.status;
}

const MAX_ENTRIES = 30;

type HistoryState = {
	/** Fingerprint of the key this history belongs to; another key starts empty. */
	ownerSeed: string | null;
	entries: HistoryEntry[];
	/** Returns true when a different owner's entries were dropped. */
	claim: (seed: string) => boolean;
	add: (entry: HistoryEntry) => string[];
	update: (jobId: string, patch: Partial<HistoryEntry>) => void;
	remove: (jobId: string) => void;
	clear: () => void;
};

export const useHistoryStore = create<HistoryState>()(
	devtools(
		persist(
			(set, get) => ({
				ownerSeed: null,
				entries: [],
				claim: (seed) => {
					const { ownerSeed } = get();
					if (ownerSeed === seed) return false;
					set({
						ownerSeed: seed,
						entries: ownerSeed === null ? get().entries : [],
					});
					return ownerSeed !== null;
				},
				/** Returns the job ids that fell out of the list so their videos can be freed. */
				add: (entry) => {
					let evicted: string[] = [];
					set((state) => {
						const next = [
							entry,
							...state.entries.filter((e) => e.jobId !== entry.jobId),
						];
						evicted = next.slice(MAX_ENTRIES).map((e) => e.jobId);
						return { entries: next.slice(0, MAX_ENTRIES) };
					});
					return evicted;
				},
				update: (jobId, patch) =>
					set((state) => ({
						entries: state.entries.map((entry) =>
							entry.jobId === jobId ? { ...entry, ...patch } : entry,
						),
					})),
				remove: (jobId) =>
					set((state) => ({
						entries: state.entries.filter((entry) => entry.jobId !== jobId),
					})),
				clear: () => set({ ownerSeed: null, entries: [] }),
			}),
			{
				name: "review-history-v1",
				version: 1,
				storage: createJSONStorage(() => localStorage),
				partialize: (state) => ({
					ownerSeed: state.ownerSeed,
					entries: state.entries,
				}),
			},
		),
		{ name: "history", enabled: DEV_TOOLS },
	),
);
