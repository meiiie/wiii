import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const isEmbed = process.env.BUILD_TARGET === "embed";
const isWeb = process.env.BUILD_TARGET === "web";

// https://tauri.app/start/frontend/vite/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Prevent vite from obscuring rust errors
  clearScreen: false,
  server: {
    port: isEmbed ? 1421 : 1420,
    strictPort: true,
    watch: {
      // Tell vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
  // Env variables starting with TAURI_ are accessible in the client code
  envPrefix: ["VITE_", "TAURI_"],
  // Sprint 220b: Embed assets must use /embed/ base path (served via FastAPI StaticFiles)
  base: isEmbed ? "/embed/" : undefined,
  build: {
    outDir: isEmbed ? "dist-embed" : isWeb ? "dist-web" : "dist",
    // Embed/Web: modern browsers; Tauri: Chromium/WebKit
    target: isEmbed || isWeb
      ? "es2020"
      : process.env.TAURI_PLATFORM === "windows"
        ? "chrome105"
        : "safari13",
    // Embed/Web: always minify; Tauri: only in release
    minify: isEmbed || isWeb ? "esbuild" : !process.env.TAURI_DEBUG ? "esbuild" : false,
    // Embed/Web: no sourcemaps; Tauri: only in debug
    sourcemap: isEmbed || isWeb ? false : !!process.env.TAURI_DEBUG,
    rollupOptions: {
      input: isEmbed
        ? { embed: path.resolve(__dirname, "embed.html") }
        : undefined,
      // Tauri-only plugins resolved at runtime (dynamic import with try/catch fallback)
      // Web + Embed: bundle everything (Tauri APIs fail gracefully via try/catch)
      external: isEmbed || isWeb ? [] : ["@fabianlars/tauri-plugin-oauth"],
    },
  },
});
