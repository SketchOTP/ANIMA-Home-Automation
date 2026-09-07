import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Isolated presentation fixture: no proxy and no owner API connection.
export default defineConfig({ root: resolve(import.meta.dirname, "../.."), plugins: [react()], server: { host: "127.0.0.1", port: 18331, strictPort: true } });
