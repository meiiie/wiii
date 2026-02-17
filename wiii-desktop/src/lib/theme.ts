/**
 * Theme management — CSS variable-based light/dark mode.
 * Matches system preference by default, with user override.
 */

export type ThemeMode = "light" | "dark" | "system";

const THEME_STORAGE_KEY = "wiii:theme";

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
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

/**
 * Initialize theme from persisted preference.
 * Call once at app startup (before React renders).
 */
export function initTheme(): ThemeMode {
  let mode: ThemeMode = "system";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      mode = stored;
    }
  } catch {
    // localStorage unavailable
  }

  applyTheme(resolveTheme(mode));

  // Listen for system preference changes when mode is "system"
  if (mode === "system") {
    setupSystemListener();
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
let systemListener: ((e: MediaQueryListEvent) => void) | null = null;

function setupSystemListener() {
  if (systemListener) return;
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  systemListener = (e: MediaQueryListEvent) => {
    applyTheme(e.matches ? "dark" : "light");
  };
  mq.addEventListener("change", systemListener);
}

function removeSystemListener() {
  if (!systemListener) return;
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.removeEventListener("change", systemListener);
  systemListener = null;
}

/**
 * Get current effective theme.
 */
export function getCurrentTheme(): "light" | "dark" {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}
