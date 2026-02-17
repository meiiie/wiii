import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initTheme } from "@/lib/theme";
import "./styles/globals.css";
import "./styles/markdown.css";

// Initialize theme before React renders (prevents flash of wrong theme)
initTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
