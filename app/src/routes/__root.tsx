import type { QueryClient } from "@tanstack/react-query";
import {
	createRootRouteWithContext,
	HeadContent,
	Scripts,
} from "@tanstack/react-router";
import { DevToolsLoader } from "@/components/dev/dev-tools-loader";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import appCss from "../styles.css?url";

interface RouterContext {
	queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{ name: "viewport", content: "width=device-width, initial-scale=1" },
			{ title: "Видеоанализ" },
			{ name: "color-scheme", content: "light" },
			{
				name: "description",
				content: "Анализ видео кассовой дисциплины: события, таймкоды и обзор.",
			},
		],
		links: [
			{ rel: "stylesheet", href: appCss },
			{
				rel: "icon",
				type: "image/svg+xml",
				href: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23171717'/%3E%3Ccircle cx='16' cy='16' r='6' fill='none' stroke='white' stroke-width='2.5'/%3E%3C/svg%3E",
			},
		],
	}),
	shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="ru">
			<head>
				<HeadContent />
			</head>
			<body>
				<TooltipProvider delay={300}>{children}</TooltipProvider>
				<Toaster position="bottom-right" />
				<DevToolsLoader />
				<Scripts />
			</body>
		</html>
	);
}
