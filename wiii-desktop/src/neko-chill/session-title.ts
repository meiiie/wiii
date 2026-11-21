export function normalizeSessionTitle(title: string): string {
  return title.replace(/\.\.\. \[truncated\]$/, "…");
}
