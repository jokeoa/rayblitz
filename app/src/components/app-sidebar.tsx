import { Link, useRouterState } from "@tanstack/react-router";
import { History, LayoutDashboard, LogOut, PlayCircle } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarRail,
	SidebarTrigger,
	useSidebar,
} from "@/components/ui/sidebar";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { UserAvatar } from "@/components/user-avatar";
import type { Profile } from "@/lib/api/session-contracts";
import { useUiStore } from "@/stores/ui-store";

export function AppSidebar({
	profile,
	onLogout,
	loggingOut,
}: {
	profile: Profile;
	onLogout: () => void;
	loggingOut: boolean;
}) {
	const pathname = useRouterState({
		select: (state) => state.location.pathname,
	});
	const setHistoryOpen = useUiStore((state) => state.setHistoryOpen);
	const historyOpen = useUiStore((state) => state.historyOpen);
	const { state, isMobile } = useSidebar();
	const collapsed = state === "collapsed" && !isMobile;

	return (
		<Sidebar collapsible="icon">
			<SidebarHeader className="flex-row items-center justify-between gap-2 p-2 group-data-[collapsible=icon]:flex-col">
				<Link
					to="/"
					className="flex min-w-0 items-center rounded-xl px-3 py-1 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:hidden"
				>
					<Logo className="text-xl" />
				</Link>
				<SidebarTrigger aria-label="Свернуть или развернуть панель" />
			</SidebarHeader>

			<SidebarContent>
				<SidebarGroup>
					<SidebarGroupContent>
						<SidebarMenu>
							<SidebarMenuItem>
								<SidebarMenuButton
									tooltip="Дашборд"
									isActive={pathname === "/"}
									render={<Link to="/" />}
								>
									<LayoutDashboard aria-hidden />
									<span>Дашборд</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
							<SidebarMenuItem>
								<SidebarMenuButton
									tooltip="Просмотр"
									isActive={pathname.startsWith("/watch")}
									render={<Link to="/watch" />}
								>
									<PlayCircle aria-hidden />
									<span>Просмотр</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
							<SidebarMenuItem>
								<SidebarMenuButton
									tooltip="История"
									isActive={historyOpen}
									onClick={() => setHistoryOpen(true)}
								>
									<History aria-hidden />
									<span>История</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			</SidebarContent>

			<SidebarFooter className="p-2">
				<div className="flex items-center gap-2 rounded-2xl bg-background p-2 shadow-card group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:p-0 group-data-[collapsible=icon]:shadow-none">
					<UserAvatar seed={profile.seed} name={profile.name} />
					<div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
						<p className="truncate text-sm font-medium leading-tight">
							{profile.name}
						</p>
						<p className="truncate text-xs text-muted-foreground">
							Доступ по API-ключу
						</p>
					</div>
					<Tooltip>
						<TooltipTrigger
							render={
								<Button
									variant="ghost"
									size="icon-sm"
									aria-label="Выйти"
									disabled={loggingOut}
									onClick={onLogout}
								/>
							}
						>
							<LogOut aria-hidden />
						</TooltipTrigger>
						<TooltipContent side={collapsed ? "right" : "top"}>
							Выйти
						</TooltipContent>
					</Tooltip>
				</div>
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
