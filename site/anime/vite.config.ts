import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const root = dirname(fileURLToPath(import.meta.url));

const filmRoute = (req: { url?: string }, _res: unknown, next: () => void) => {
  const url = req.url || "";
  const path = url.split("?")[0];
  if (path === "/film" || path === "/film/") {
    const q = url.includes("?") ? url.slice(url.indexOf("?")) : "";
    req.url = `/film.html${q}`;
  }
  next();
};

export default defineConfig({
  base: "/",
  build: {
    outDir: "dist",
    sourcemap: false,
    cssCodeSplit: true,
    rollupOptions: {
      input: {
        main: resolve(root, "index.html"),
        film: resolve(root, "film.html"),
      },
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/gsap")) return "gsap";
          if (id.includes("node_modules/lenis")) return "lenis";
          return undefined;
        },
      },
    },
  },
  plugins: [
    {
      name: "film-route",
      configureServer(server) {
        server.middlewares.use(filmRoute);
      },
      configurePreviewServer(server) {
        server.middlewares.use(filmRoute);
      },
    },
  ],
  server: {
    host: "127.0.0.1",
    port: 4173,
  },
});
