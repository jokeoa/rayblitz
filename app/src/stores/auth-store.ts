import { create } from "zustand";
import type { Profile } from "@/lib/api/session-contracts";

type AuthState = {
	profile: Profile | null;
	/** Set when any API call answers 401; the app shell then returns to /login. */
	expired: boolean;
	setProfile: (profile: Profile | null) => void;
	expire: () => void;
};

/**
 * Mirrors the server session for the UI. The API key itself is never stored
 * client-side: only the display profile derived from it.
 */
export const useAuthStore = create<AuthState>()((set) => ({
	profile: null,
	expired: false,
	setProfile: (profile) => set({ profile, expired: false }),
	expire: () => set({ expired: true }),
}));
