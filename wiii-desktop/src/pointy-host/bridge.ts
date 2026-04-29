/**
 * Wiii Pointy — PostMessage bridge between the host page and the Wiii iframe.
 *
 * Listens for `wiii:action-request` messages whose `action` starts with `ui.`
 * and dispatches them to cursor/spotlight/tour handlers. Replies via
 * `wiii:action-response`. Cross-origin safe: only accepts requests from the
 * configured iframeOrigin and only replies to that same origin.
 */
import { hideCursor, moveCursorToRect } from "./cursor";
import { hideSpotlight, showSpotlight } from "./spotlight";
import { runTour } from "./tour";
import type {
  ClickParams,
  HighlightParams,
  NavigateParams,
  PointyConfig,
  PointyRequest,
  PointyResponse,
  PointyResult,
  ScrollToParams,
  ShowTourParams,
  TourStep,
} from "./types";

function defaultLog(level: "info" | "warn" | "error", msg: string, ctx?: unknown): void {
  const tag = "[wiii-pointy]";
  if (level === "error") console.error(tag, msg, ctx ?? "");
  else if (level === "warn") console.warn(tag, msg, ctx ?? "");
  else console.info(tag, msg, ctx ?? "");
}

function isPointyRequest(data: unknown): data is PointyRequest {
  if (typeof data !== "object" || data === null) return false;
  const d = data as Record<string, unknown>;
  return (
    d.type === "wiii:action-request" &&
    typeof d.id === "string" &&
    typeof d.action === "string" &&
    typeof d.params === "object" &&
    d.params !== null
  );
}

function ok(data?: Record<string, unknown>): PointyResult {
  return { success: true, ...(data ? { data } : {}) };
}
function fail(error: string): PointyResult {
  return { success: false, error };
}

/** Resolve a selector with light hardening: trim, reject empty, allow data-wiii-id. */
export function resolveSelector(selector: unknown): Element | null {
  if (typeof selector !== "string") return null;
  const trimmed = selector.trim();
  if (!trimmed) return null;
  if (typeof document === "undefined") return null;
  try {
    const direct = document.querySelector(trimmed);
    if (direct) return direct;
  } catch {
    // Treat a bare semantic id such as "browse-courses" as data-wiii-id.
  }
  if (/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
    try {
      return document.querySelector(`[data-wiii-id="${trimmed.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"]`);
    } catch {
      return null;
    }
  }
  return null;
}

export async function handleHighlight(params: HighlightParams): Promise<PointyResult> {
  const target = resolveSelector(params.selector);
  if (!target) return fail(`selector_not_found:${params.selector}`);
  const rect = target.getBoundingClientRect();
  if ("scrollIntoView" in target && typeof (target as HTMLElement).scrollIntoView === "function") {
    (target as HTMLElement).scrollIntoView({ behavior: "smooth", block: "center" });
  }
  moveCursorToRect(rect, { duration_ms: 600 });
  showSpotlight(target, {
    message: params.message,
    duration_ms: params.duration_ms,
  });
  return ok({ summary: `Đã trỏ vào element: ${describeTarget(target)}` });
}

export async function handleScrollTo(params: ScrollToParams): Promise<PointyResult> {
  const target = resolveSelector(params.selector);
  if (!target) return fail(`selector_not_found:${params.selector}`);
  if ("scrollIntoView" in target && typeof (target as HTMLElement).scrollIntoView === "function") {
    (target as HTMLElement).scrollIntoView({
      behavior: "smooth",
      block: params.block ?? "center",
    });
  }
  return ok({ summary: `Đã cuộn tới element: ${describeTarget(target)}` });
}

export async function handleNavigate(
  params: NavigateParams,
  config: PointyConfig,
): Promise<PointyResult> {
  const route = (params.route ?? "").trim();
  const url = (params.url ?? "").trim();
  if (!route && !url) return fail("missing_target");
  if (route) {
    if (config.onNavigate) {
      try {
        await config.onNavigate(route);
        return ok({ summary: `Đã chuyển sang route: ${route}` });
      } catch (e) {
        return fail(`navigate_failed:${(e as Error).message}`);
      }
    }
    if (typeof window !== "undefined") {
      window.location.assign(route);
      return ok({ summary: `Đã chuyển sang: ${route}` });
    }
    return fail("no_navigator_available");
  }
  if (!isSafeUrl(url)) return fail("unsafe_url");
  if (typeof window !== "undefined") {
    window.location.assign(url);
    return ok({ summary: `Đã chuyển sang URL: ${url}` });
  }
  return fail("no_navigator_available");
}

export async function handleShowTour(params: ShowTourParams): Promise<PointyResult> {
  if (!Array.isArray(params.steps) || params.steps.length === 0) {
    return fail("empty_tour");
  }
  const steps: TourStep[] = params.steps.filter(
    (s): s is TourStep => !!s && typeof s.selector === "string" && typeof s.message === "string",
  );
  if (steps.length === 0) return fail("invalid_tour_steps");
  const result = await runTour(steps, { startAt: params.start_at });
  return ok({
    summary: `Tour ${result.completed_steps}/${result.total_steps} bước.`,
    completed_steps: result.completed_steps,
    total_steps: result.total_steps,
    missing_selectors: result.missing_selectors,
    cancelled: result.cancelled,
  });
}

export async function handleClick(params: ClickParams): Promise<PointyResult> {
  const target = resolveSelector(params.selector);
  if (!target) return fail(`selector_not_found:${params.selector}`);
  if (!(target instanceof HTMLElement) || target.getAttribute("data-wiii-click-safe") !== "true") {
    return fail(`unsafe_click_target:${params.selector}`);
  }
  if (
    target.hasAttribute("disabled")
    || target.getAttribute("aria-disabled") === "true"
    || (target instanceof HTMLButtonElement && target.disabled)
  ) {
    return fail(`disabled_click_target:${params.selector}`);
  }
  if ("scrollIntoView" in target && typeof target.scrollIntoView === "function") {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  moveCursorToRect(target.getBoundingClientRect(), { duration_ms: 260 });
  showSpotlight(target, {
    message: params.message || "Wiii dang mo muc nay cho ban.",
    duration_ms: 900,
  });
  target.click();
  return ok({
    summary: `Da bam element: ${describeTarget(target)}`,
    clicked: true,
    click_kind: target.getAttribute("data-wiii-click-kind") || "safe",
  });
}

export function describeTarget(el: Element): string {
  const labels: string[] = [];
  const id = el.getAttribute("data-wiii-id") || el.id;
  if (id) labels.push(`#${id}`);
  const aria = el.getAttribute("aria-label");
  if (aria) labels.push(`"${aria}"`);
  if (!labels.length) {
    const text = (el.textContent || "").trim();
    if (text) labels.push(`"${text.slice(0, 40)}"`);
  }
  if (!labels.length) labels.push(el.tagName.toLowerCase());
  return labels.join(" ");
}

function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url, typeof window !== "undefined" ? window.location.href : undefined);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    const host = parsed.hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0") return false;
    if (host.endsWith(".local") || host.endsWith(".internal")) return false;
    return true;
  } catch {
    return false;
  }
}

export interface BridgeHandle {
  dispose: () => void;
}

export function createBridge(config: PointyConfig): BridgeHandle {
  const log = config.log ?? defaultLog;
  const targetOrigin = config.iframeOrigin;

  const handler = (event: MessageEvent): void => {
    if (event.origin !== targetOrigin) return;
    if (!isPointyRequest(event.data)) return;

    const req = event.data;
    void dispatch(req, config)
      .then((result) => sendResponse(event, req.id, result, targetOrigin, log))
      .catch((err) => {
        log("error", "dispatch_threw", err);
        sendResponse(event, req.id, fail((err as Error).message ?? "unknown_error"), targetOrigin, log);
      });
  };

  if (typeof window !== "undefined") {
    window.addEventListener("message", handler);
  }

  return {
    dispose: () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("message", handler);
      }
      hideSpotlight();
      hideCursor();
    },
  };
}

async function dispatch(req: PointyRequest, config: PointyConfig): Promise<PointyResult> {
  switch (req.action) {
    case "ui.highlight":
      return handleHighlight(req.params as unknown as HighlightParams);
    case "ui.scroll_to":
      return handleScrollTo(req.params as unknown as ScrollToParams);
    case "ui.navigate":
      return handleNavigate(req.params as unknown as NavigateParams, config);
    case "ui.show_tour":
      return handleShowTour(req.params as unknown as ShowTourParams);
    case "ui.click":
      return handleClick(req.params as unknown as ClickParams);
    default:
      return fail(`unsupported_action:${req.action}`);
  }
}

function sendResponse(
  event: MessageEvent,
  id: string,
  result: PointyResult,
  targetOrigin: string,
  log: NonNullable<PointyConfig["log"]>,
): void {
  const reply: PointyResponse = {
    type: "wiii:action-response",
    id,
    result,
  };
  const target = (event.source as Window) ?? null;
  if (!target) {
    log("warn", "no_event_source");
    return;
  }
  try {
    target.postMessage(reply, targetOrigin);
  } catch (e) {
    log("error", "postMessage_failed", e);
  }
}

export const _testing = {
  isPointyRequest,
  isSafeUrl,
  ok,
  fail,
};
