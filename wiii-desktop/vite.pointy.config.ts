/**
 * Vite library config for the Wiii Pointy host bundle.
 *
 *   npx cross-env BUILD_TARGET=pointy vite build -c vite.pointy.config.ts
 *
 * Output: dist-pointy/wiii-pointy.umd.js (+ .es.js).
 *
 * Self-contained — no React, no Zustand, no Tauri APIs. Safe to ship to
 * a third-party host page.
 */
import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist-pointy",
    emptyOutDir: true,
    minify: "esbuild",
    sourcemap: false,
    target: "es2020",
    lib: {
      entry: path.resolve(__dirname, "src/pointy-host/index.ts"),
      name: "WiiiPointy",
      fileName: (format) => `wiii-pointy.${format}.js`,
      formats: ["umd", "es"],
    },
    rollupOptions: {
      // No external deps; pointy-host is intentionally framework-free.
      external: [],
      output: {
        globals: {},
      },
    },
  },
});
