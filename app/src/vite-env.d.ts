/// <reference types="vite/client" />

interface ImportMetaEnv {
	/** "true" in development mode only. Gates every developer tool in the UI. */
	readonly VITE_DEV_TOOLS?: string;
	/** "true" when the analyzer behind the proxy is the local mock (dev:mock, present:mock). */
	readonly VITE_MOCK?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
