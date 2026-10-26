import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API runs on :8000. Proxying keeps the browser same-origin, so the API needs no CORS changes.
declare const process: { env: Record<string, string | undefined> };
const API = process.env.GREENOPS_API_URL ?? "http://127.0.0.1:8000";
const proxied = ["/v1", "/health", "/docs", "/openapi.json"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: API, changeOrigin: false }])),
  },
  preview: { port: 5173, proxy: Object.fromEntries(proxied.map((p) => [p, { target: API }])) },
});
