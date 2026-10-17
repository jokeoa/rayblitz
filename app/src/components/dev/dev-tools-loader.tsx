import { lazy, Suspense, useEffect, useState } from "react";

// Written as a literal comparison so Vite folds it and drops the whole branch,
// including the lazy chunk, from presentation and production builds.
const DevTools =
	import.meta.env.VITE_DEV_TOOLS === "true"
		? lazy(() => import("./dev-tools"))
		: null;

/** Client-only host for every developer tool. Renders nothing in presentation mode. */
export function DevToolsLoader() {
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	if (!DevTools || !mounted) return null;
	return (
		<Suspense fallback={null}>
			<DevTools />
		</Suspense>
	);
}
