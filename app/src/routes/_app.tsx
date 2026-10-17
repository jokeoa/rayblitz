import { useQueryClient } from "@tanstack/react-query";
import {
	createFileRoute,
	Outlet,
	redirect,
	useNavigate,
} from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AppShellSkeleton } from "@/components/app-shell-skeleton";
import { AppSidebar } from "@/components/app-sidebar";
import { HistoryDialog } from "@/components/history-dialog";
import {
	SidebarInset,
	SidebarProvider,
	SidebarTrigger,
} from "@/components/ui/sidebar";
import { UploadDialog } from "@/components/upload-dialog";
import { useHealthRecorder } from "@/hooks/use-health";
import { useHistorySync } from "@/hooks/use-history-sync";
import { logout } from "@/lib/api/review";
import { clearVideos } from "@/lib/video-blobs";
import { getSessionState } from "@/server/auth.functions";
import { useAuthStore } from "@/stores/auth-store";
import { useHistoryStore } from "@/stores/history-store";

export const Route = createFileRoute("/_app")({
	// Everything behind the login is client state (history, blobs, player), so no SSR.
	ssr: false,
	beforeLoad: async () => {
		const state = await getSessionState();
		if (!state.authenticated) throw redirect({ to: "/login" });
		return { profile: state.profile };
	},
	pendingComponent: AppShellSkeleton,
	component: AppLayout,
});

function readSidebarCookie(): boolean {
	const match = /(?:^|; )sidebar_state=(true|false)/.exec(document.cookie);
	return match ? match[1] === "true" : true;
}

function AppLayout() {
	const { profile } = Route.useRouteContext();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const expired = useAuthStore((state) => state.expired);
	const setProfile = useAuthStore((state) => state.setProfile);
	const [loggingOut, setLoggingOut] = useState(false);

	useHealthRecorder();
	useHistorySync();

	useEffect(() => {
		setProfile(profile);
		// A different key must never inherit the previous person's history or videos.
		if (useHistoryStore.getState().claim(profile.seed)) void clearVideos();
	}, [profile, setProfile]);

	const leave = useCallback(
		async (reason: "expired" | "signed-out") => {
			if (reason === "signed-out") {
				// An explicit sign-out leaves nothing behind on a shared workstation.
				useHistoryStore.getState().clear();
				await clearVideos();
			}
			queryClient.clear();
			useAuthStore.getState().setProfile(null);
			await navigate({ to: "/login", search: { reason } });
		},
		[navigate, queryClient],
	);

	useEffect(() => {
		if (expired) void leave("expired");
	}, [expired, leave]);

	const onLogout = async () => {
		setLoggingOut(true);
		try {
			await logout();
			await leave("signed-out");
		} catch {
			toast.error("Не удалось выйти. Повторите попытку.");
		} finally {
			setLoggingOut(false);
		}
	};

	return (
		<SidebarProvider defaultOpen={readSidebarCookie()}>
			<AppSidebar
				profile={profile}
				onLogout={onLogout}
				loggingOut={loggingOut}
			/>
			<SidebarInset className="min-w-0">
				<header className="flex h-12 items-center gap-2 border-b px-3 md:hidden">
					<SidebarTrigger />
					<span className="text-sm font-semibold tracking-tight">
						Видеоанализ
					</span>
				</header>
				<Outlet />
			</SidebarInset>
			<HistoryDialog />
			<UploadDialog />
		</SidebarProvider>
	);
}
