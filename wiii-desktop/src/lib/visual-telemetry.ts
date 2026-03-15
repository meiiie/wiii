type VisualTelemetryName =
  | "visual_requested"
  | "visual_emitted"
  | "visual_opened"
  | "visual_patched"
  | "visual_committed"
  | "visual_disposed"
  | "visual_interacted"
  | "visual_rendered"
  | "visual_fallback_used"
  | "visual_render_error"
  | `visual_${string}`;

export function trackVisualTelemetry(
  name: VisualTelemetryName,
  detail: Record<string, unknown>,
): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("wiii:visual-telemetry", { detail: { name, ...detail } }));
  }
  if (import.meta.env.DEV) {
    console.debug("[visual]", name, detail);
  }
}
