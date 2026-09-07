import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Presentation-only fixture. No production proxy, dist build, or provider access.
export default defineConfig({ root: import.meta.dirname, plugins: [react()], server: { host: "127.0.0.1", port: 18333, strictPort: true, fs: { allow: [resolve(import.meta.dirname, "../..")] } } });
