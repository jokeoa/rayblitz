import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { DEV_TOOLS } from "@/lib/app-mode";

type UiState = {
	historyOpen: boolean;
	uploadOpen: boolean;
	setHistoryOpen: (open: boolean) => void;
	setUploadOpen: (open: boolean) => void;
	/** The history card hands over to the upload dialog without stacking modals. */
	openUpload: () => void;
};

export const useUiStore = create<UiState>()(
	devtools(
		(set) => ({
			historyOpen: false,
			uploadOpen: false,
			setHistoryOpen: (historyOpen) => set({ historyOpen }),
			setUploadOpen: (uploadOpen) => set({ uploadOpen }),
			openUpload: () => set({ historyOpen: false, uploadOpen: true }),
		}),
		{ name: "ui", enabled: DEV_TOOLS },
	),
);
