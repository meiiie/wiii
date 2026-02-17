/**
 * Shared formatting utilities.
 * Sprint 109: Extracted from ContextPanel + SettingsPage.
 */

/** Format token count for compact display (e.g. 1500 → "1.5K"). */
export function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
