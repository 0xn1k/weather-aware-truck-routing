/// <reference types="vitest/config" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
  optimizeDeps: {
    // MapLibre GL JS constructs its tile-processing Web Worker's URL at
    // runtime from its own module location. Vite's dependency pre-bundling
    // rewrites/chunks the library into .vite/deps/, which breaks that
    // construction and causes "Worker failed to load" — confirmed via a
    // captured browser console error, not a guess. Excluding it from
    // pre-bundling serves it as-is from node_modules instead.
    exclude: ["maplibre-gl"],
  },
  test: {
    environment: "jsdom",
    globals: false,
  },
});
