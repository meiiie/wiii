import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const isEmbed = process.env.BUILD_TARGET === "embed";

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
  build: {
    outDir: isEmbed ? "dist-embed" : "dist",
    // Embed: modern browsers only; Tauri: Chromium/WebKit
    target: isEmbed
      ? "es2020"
      : process.env.TAURI_PLATFORM === "windows"
        ? "chrome105"
        : "safari13",
    // Embed: always minify; Tauri: only in release
    minify: isEmbed ? "esbuild" : !process.env.TAURI_DEBUG ? "esbuild" : false,
    // Embed: no sourcemaps; Tauri: only in debug
    sourcemap: isEmbed ? false : !!process.env.TAURI_DEBUG,
    rollupOptions: {
      input: isEmbed
        ? { embed: path.resolve(__dirname, "embed.html") }
        : undefined,
      // Tauri-only plugins resolved at runtime (dynamic import with try/catch fallback)
      external: isEmbed ? [] : ["@fabianlars/tauri-plugin-oauth"],
    },
  },
});
