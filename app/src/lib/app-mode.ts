/**
 * Build-time switches. Both are literal comparisons on `import.meta.env`, so
 * Vite folds them to constants and every developer-only branch (devtools,
 * Agentation, mock controls, health internals) is removed from the
 * presentation and production bundles.
 */
export const DEV_TOOLS = import.meta.env.VITE_DEV_TOOLS === "true";
export const IS_MOCK = import.meta.env.VITE_MOCK === "true";
