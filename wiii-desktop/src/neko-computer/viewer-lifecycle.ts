export const COMPUTER_VIEWER_SOURCE = "wiii-computer-viewer-v1" as const;

export type ComputerViewerPhase =
  | "viewer.loaded"
  | "rfb.connected"
  | "rfb.timeout"
  | "rfb.disconnected"
  | "rfb.security_failure"
  | "framebuffer.visible"
  | "framebuffer.timeout"
  | "framebuffer.failed";

export interface ComputerViewerMessage {
  source: typeof COMPUTER_VIEWER_SOURCE;
  phase: ComputerViewerPhase;
  at: number;
  clean?: boolean;
  reason?: string;
}

export type ComputerViewerInputMode = "observe" | "control";

export function buildComputerViewerUrl(
  attachUrl: string,
  inputMode: ComputerViewerInputMode,
): string {
  const url = new URL(attachUrl);
  url.searchParams.set("fit", "1");
  url.searchParams.set("view_only", inputMode === "control" ? "0" : "1");
  return url.toString();
}

const PHASES: ReadonlySet<string> = new Set<ComputerViewerPhase>([
  "viewer.loaded",
  "rfb.connected",
  "rfb.timeout",
  "rfb.disconnected",
  "rfb.security_failure",
  "framebuffer.visible",
  "framebuffer.timeout",
  "framebuffer.failed",
]);

export function parseComputerViewerMessage(value: unknown): ComputerViewerMessage | null {
  if (value == null || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (candidate.source !== COMPUTER_VIEWER_SOURCE) return null;
  if (typeof candidate.phase !== "string" || !PHASES.has(candidate.phase)) return null;
  if (typeof candidate.at !== "number" || !Number.isFinite(candidate.at)) return null;
  if (candidate.clean != null && typeof candidate.clean !== "boolean") return null;
  if (candidate.reason != null && typeof candidate.reason !== "string") return null;
  return candidate as unknown as ComputerViewerMessage;
}
