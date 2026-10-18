export default {
  root: new URL("./", import.meta.url).pathname,
  publicDir: false,
  build: { outDir: "runs" },
  preview: { host: "127.0.0.1", port: 8765, strictPort: true },
};
