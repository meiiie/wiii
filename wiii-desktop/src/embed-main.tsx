/**
 * Embed entry point — lightweight React bootstrap for iframe embed.
 * Sprint 176: Wiii Chat Embed for LMS iframe integration.
 *
 * Differences from main.tsx:
 * - No Tauri-specific initialization
 * - Sets __WIII_EMBED__ flag for runtime detection
 */
import React from "react";
import ReactDOM from "react-dom/client";
import EmbedApp from "./EmbedApp";
import { initTheme } from "@/lib/theme";
import "./styles/globals.css";
import "./styles/markdown.css";

// Global embed flag — used by storage.ts and other modules
(window as any).__WIII_EMBED__ = true;

// Initialize theme before React renders (prevents flash of wrong theme)
initTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <EmbedApp />
  </React.StrictMode>
);
