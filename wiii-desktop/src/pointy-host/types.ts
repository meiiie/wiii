/**
 * Wiii Pointy — type definitions for the host-side action protocol.
 *
 * The pointy bundle runs INSIDE the parent (host) page, listening for
 * `wiii:action-request` messages emitted by the Wiii iframe (Sprint 222
 * HostActionBridge). It executes UI tutoring actions (highlight, scroll,
 * navigate, safe-click, multi-step tour) on the host DOM and replies via
 * `wiii:action-response`.
 *
 * V1 safe-click is fail-closed: no auto-fill, and click only works on targets
 * explicitly marked `data-wiii-click-safe="true"`.
 */

/** Identity reserved for the Wiii iframe's PostMessage envelope. */
export const POINTY_PROTOCOL_VERSION = 1;

/** Action names the AI can call. Keep aligned with HostCapabilities tools. */
export const POINTY_ACTIONS = [
  "ui.highlight",
  "ui.scroll_to",
  "ui.navigate",
  "ui.show_tour",
  "ui.click",
] as const;
export type PointyAction = (typeof POINTY_ACTIONS)[number];

/** Inbound request from the Wiii iframe. */
export interface PointyRequest {
  type: "wiii:action-request";
  id: string;
  action: string;
  params: Record<string, unknown>;
}

/** Outbound reply sent to the Wiii iframe. */
export interface PointyResponse {
  type: "wiii:action-response";
  id: string;
  result: {
    success: boolean;
    data?: Record<string, unknown>;
    error?: string;
  };
}

/** Capability declaration sent once on iframe load. */
export interface PointyCapabilities {
  type: "wiii:capabilities";
  payload: {
    host_type: string;
    host_name?: string;
    version: string;
    surfaces: string[];
    tools: PointyToolDefinition[];
  };
}

export interface PointyToolDefinition {
  name: PointyAction | string;
  description: string;
  input_schema: {
    type: "object";
    properties: Record<string, { type: string; description?: string }>;
    required?: string[];
  };
  roles?: string[];
  surface?: string;
  mutates_state: boolean;
  requires_confirmation: boolean;
}

export interface HighlightParams {
  selector: string;
  message?: string;
  duration_ms?: number;
}

export interface ScrollToParams {
  selector: string;
  block?: ScrollLogicalPosition;
}

export interface NavigateParams {
  /** Internal route (preferred) or absolute URL. */
  route?: string;
  url?: string;
}

export interface TourStep {
  selector: string;
  message: string;
  duration_ms?: number;
}

export interface ShowTourParams {
  steps: TourStep[];
  /** Step index to start at; defaults to 0. */
  start_at?: number;
}

export interface ClickParams {
  selector: string;
  message?: string;
}

export interface PointyConfig {
  /** Origin of the Wiii iframe; required so we never message untrusted frames. */
  iframeOrigin: string;
  /** The iframe element to message (or window) — used for reply targeting. */
  iframe?: HTMLIFrameElement | Window;
  /** Optional Angular Router-like callback for ui.navigate. */
  onNavigate?: (route: string) => void | Promise<void>;
  /** Optional logger. Defaults to console. Pass `() => {}` to silence. */
  log?: (level: "info" | "warn" | "error", msg: string, ctx?: unknown) => void;
}

export type PointyResult = PointyResponse["result"];
