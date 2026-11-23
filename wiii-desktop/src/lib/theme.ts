/**
 * Theme management — CSS variable-based light/dark mode.
 * Matches system preference by default, with user override.
 */

export type ThemeMode = "light" | "dark" | "system";

const THEME_STORAGE_KEY = "wiii:theme";
const themeListeners = new Set<() => void>();

/** Observe effective appearance, including system changes without a mode change. */
export function subscribeTheme(listener: () => void): () => void {
  themeListeners.add(listener);
  return () => { themeListeners.delete(listener); };
}

/**
 * Resolve the effective theme (light or dark) from a mode setting.
 */
function resolveTheme(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

/**
 * Apply theme to the document root.
 */
function applyTheme(theme: "light" | "dark") {
  const root = document.documentElement;
  const previous = getCurrentTheme();
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  if (previous !== theme) themeListeners.forEach((listener) => listener());
}

/**
 * Read the chosen mode, not the effective system color.
 */
export function getThemeMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage unavailable
  }
  return "system";
}

/** Initialize before React renders to prevent a flash of the wrong theme. */
export function initTheme(): ThemeMode {
  const mode = getThemeMode();

  applyTheme(resolveTheme(mode));

  // Listen for system preference changes when mode is "system"
  if (mode === "system") {
    setupSystemListener();
  } else {
    removeSystemListener();
  }

  return mode;
}

/**
 * Set theme mode and persist.
 */
export function setTheme(mode: ThemeMode) {
  applyTheme(resolveTheme(mode));

  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // ignore
  }

  // Manage system listener
  if (mode === "system") {
    setupSystemListener();
  } else {
    removeSystemListener();
  }
}

// System preference change listener
let stopSystemListener: (() => void) | null = null;

function setupSystemListener() {
  if (stopSystemListener) return;
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const listener = (e: MediaQueryListEvent) => {
    applyTheme(e.matches ? "dark" : "light");
  };
  mq.addEventListener("change", listener);
  stopSystemListener = () => mq.removeEventListener("change", listener);
}

function removeSystemListener() {
  stopSystemListener?.();
  stopSystemListener = null;
}

/**
 * Get current effective theme.
 */
export function getCurrentTheme(): "light" | "dark" {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}
