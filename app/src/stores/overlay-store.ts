import { create } from "zustand";
import { persist } from "zustand/middleware";

type OverlayState = {
	visible: boolean;
	mode: "resolved" | "raw";
	setVisible: (visible: boolean) => void;
	setMode: (mode: "resolved" | "raw") => void;
};

export const useOverlayStore = create<OverlayState>()(
	persist(
		(set) => ({
			visible: true,
			mode: "resolved",
			setVisible: (visible) => set({ visible }),
			setMode: (mode) => set({ mode }),
		}),
		{
			name: "review-overlays",
			partialize: ({ visible, mode }) => ({ visible, mode }),
		},
	),
);
