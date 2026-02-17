import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // All brand colors now driven by CSS variables (globals.css)
        // No more hardcoded wiii-* palette — use var(--accent) etc.
        surface: {
          DEFAULT: "var(--surface)",
          secondary: "var(--surface-secondary)",
          tertiary: "var(--surface-tertiary)",
        },
        border: {
          DEFAULT: "var(--border)",
          secondary: "var(--border-secondary)",
        },
        text: {
          DEFAULT: "var(--text)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
        },
      },
      fontFamily: {
        sans: [
          "IBM Plex Sans",
          "Source Sans 3",
          "Noto Sans",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        serif: ["Source Serif 4", "Noto Serif", "Georgia", "ui-serif", "serif"],
        mono: ["JetBrains Mono", "Fira Code", "SF Mono", "Consolas", "monospace"],
      },
      animation: {
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        "fade-in": "fade-in 0.2s ease-out",
        "slide-in": "slide-in 0.25s ease-out",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 80%, 100%": { opacity: "0.3" },
          "40%": { opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
