/// <reference types="vitest/config" />
import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// MapLibre GL JS resolves its tile-processing Web Worker's URL as a sibling
// file next to its own bundled module (web_worker.ts's defaultWorkerUrl()),
// e.g. ".../assets/maplibre-gl-worker.mjs" — a literal filename, not
// hash-dependent. The production build bundles maplibre-gl into a single
// hashed chunk via Rollup and never copies that separate worker file into
// dist/, so the browser requests a file that doesn't exist, the static
// host's SPA fallback silently serves index.html instead, and the worker
// never starts — tiles never render, with no visible error. optimizeDeps
// .exclude below only fixes this for the dev server; this plugin covers
// the actual production build.
function copyMaplibreWorker(): Plugin {
  return {
    name: "copy-maplibre-worker",
    apply: "build",
    closeBundle() {
      const outDir = path.resolve(__dirname, "dist/assets");
      mkdirSync(outDir, { recursive: true });
      copyFileSync(
        path.resolve(__dirname, "node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs"),
        path.join(outDir, "maplibre-gl-worker.mjs"),
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), copyMaplibreWorker()],
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
