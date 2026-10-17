import { motionValue } from "motion";
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { DEV_TOOLS } from "@/lib/app-mode";

/**
 * Smooth playhead position in seconds. It lives outside React state so the
 * 60 fps updates move the playhead and the clock without re-rendering anything.
 */
export const playheadTime = motionValue(0);

export type PlayerController = {
	toggle: () => void;
	play: () => void;
	pause: () => void;
	seek: (seconds: number) => void;
	skip: (deltaSeconds: number) => void;
	setRate: (rate: number) => void;
};

export type PlayerStatus = "loading" | "ready" | "unavailable";

type PlayerState = {
	jobId: string | null;
	status: PlayerStatus;
	duration: number;
	/** Coarse position (about 4 Hz) for controls that need React state. */
	currentTime: number;
	playing: boolean;
	rate: number;
	selectedViolationId: string | null;
	controller: PlayerController | null;
	open: (jobId: string) => void;
	setStatus: (status: PlayerStatus) => void;
	setDuration: (duration: number) => void;
	setCurrentTime: (seconds: number) => void;
	setPlaying: (playing: boolean) => void;
	setRate: (rate: number) => void;
	select: (violationId: string | null) => void;
	register: (controller: PlayerController | null) => void;
};

export const usePlayerStore = create<PlayerState>()(
	devtools(
		(set, get) => ({
			jobId: null,
			status: "loading",
			duration: 0,
			currentTime: 0,
			playing: false,
			rate: 1,
			selectedViolationId: null,
			controller: null,
			open: (jobId) => {
				if (get().jobId === jobId) return;
				playheadTime.set(0);
				set({
					jobId,
					status: "loading",
					duration: 0,
					currentTime: 0,
					playing: false,
					selectedViolationId: null,
				});
			},
			setStatus: (status) => set({ status }),
			setDuration: (duration) => set({ duration }),
			setCurrentTime: (currentTime) => set({ currentTime }),
			setPlaying: (playing) => set({ playing }),
			setRate: (rate) => set({ rate }),
			select: (selectedViolationId) => set({ selectedViolationId }),
			register: (controller) => set({ controller }),
		}),
		{ name: "player", enabled: DEV_TOOLS },
	),
);
