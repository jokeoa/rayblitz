import { devtools } from "@tanstack/devtools-vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import viteReact from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const config = defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "VITE_");
	// Developer tooling exists only when the mode asks for it. `presentation`
	// and `production` builds never include the TanStack devtools plugin.
	const devTools = env.VITE_DEV_TOOLS === "true";

	return {
		resolve: { tsconfigPaths: true },
		plugins: [
			// Console piping echoes server errors into the browser and back, which floods the log.
			devTools ? devtools({ consolePiping: { enabled: false } }) : null,
			tailwindcss(),
			tanstackStart(),
			viteReact(),
		],
	};
});

export default config;
