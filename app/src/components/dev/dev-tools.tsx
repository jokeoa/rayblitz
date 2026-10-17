import { TanStackDevtools } from "@tanstack/react-devtools";
import { ReactQueryDevtoolsPanel } from "@tanstack/react-query-devtools";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { Agentation } from "agentation";
import { IS_MOCK } from "@/lib/app-mode";
import { useAuthStore } from "@/stores/auth-store";
import { MockPanel } from "./mock-panel";

/**
 * Everything a developer needs and a presenter must never see: TanStack
 * devtools, Agentation annotations and the mock scenario switcher.
 * Loaded only when VITE_DEV_TOOLS=true (see dev-tools-loader.tsx).
 */
export default function DevTools() {
	const signedIn = useAuthStore((state) => state.profile !== null);
	return (
		<>
			<TanStackDevtools
				config={{ position: "bottom-right" }}
				plugins={[
					{ name: "TanStack Router", render: <TanStackRouterDevtoolsPanel /> },
					{ name: "TanStack Query", render: <ReactQueryDevtoolsPanel /> },
				]}
			/>
			<Agentation appName="Видеоанализ" />
			{IS_MOCK && signedIn ? <MockPanel /> : null}
		</>
	);
}
