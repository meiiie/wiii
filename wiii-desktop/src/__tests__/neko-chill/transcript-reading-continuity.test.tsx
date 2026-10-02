import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NekoTranscript } from "@/neko-chill/components/NekoTranscript";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

function makeSession(): NekoSession {
  return {
    id: "prompt-rail",
    agentId: "codex",
    agentName: "Codex",
    title: "Điều hướng prompt",
    createdAt: 1,
    updatedAt: 1,
    workspace: { path: "C:/work/wiii", name: "Wiii" },
    launchProfile: null,
    backendSessionId: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 1,
    status: "idle",
    messages: [
      { id: "user-1", role: "user", text: "Phân tích luồng đăng nhập hiện tại" },
      {
        id: "assistant-1",
        role: "assistant",
        blocks: [{
          id: "answer-1",
          type: "answer",
          content: "Đã xác định dữ liệu cũ vẫn còn trong IndexedDB.",
        }],
      },
      { id: "user-2", role: "user", text: "Bật cho tôi xem được chứ?" },
      {
        id: "assistant-2",
        role: "assistant",
        blocks: [{ id: "answer-2", type: "answer", content: "Đã mở bản xem trước trên Chrome." }],
      },
    ],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
  };
}


let frames: Map<number, FrameRequestCallback>;
let nextFrame: number;
const observers: { callback: () => void; elements: Set<Element>; disconnected: boolean }[] = [];
const scroll = vi.fn();
function paint() {
  act(() => { const work = [...frames.values()]; frames.clear(); work.forEach((fn) => fn(0)); });
}
function resize(element: Element) {
  act(() => observers.filter(o => !o.disconnected && o.elements.has(element)).forEach(o => o.callback()));
}
function mount(session = makeSession()) {
  const view = render(<NekoTranscript session={session} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
  const viewport = screen.getByTestId("neko-transcript");
  Object.defineProperties(viewport, {
    scrollHeight: { configurable: true, value: 1600 },
    clientHeight: { configurable: true, value: 400 },
    scrollTop: { configurable: true, writable: true, value: 1200 },
  });
  paint(); scroll.mockClear();
  return { ...view, viewport, session, content: viewport.firstElementChild! };
}
beforeEach(() => {
  frames = new Map(); nextFrame = 0; observers.length = 0;
  vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) => { frames.set(++nextFrame, fn); return nextFrame; });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
  vi.stubGlobal("ResizeObserver", class {
    item: typeof observers[number];
    constructor(callback: () => void) { this.item = { callback, elements: new Set(), disconnected: false }; observers.push(this.item); }
    observe(element: Element) { this.item.elements.add(element); }
    unobserve(element: Element) { this.item.elements.delete(element); }
    disconnect() { this.item.disconnected = true; }
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scroll });
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Neko transcript reading continuity", () => {
  it("follows rendered growth without another message or block", () => {
    const { content } = mount();
    resize(content); resize(content); paint();
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(scroll).toHaveBeenLastCalledWith({ block: "end", behavior: "auto" });
  });
  it("follows viewport resizing while attached to the tail", () => {
    const { viewport } = mount(); resize(viewport); paint();
    expect(scroll).toHaveBeenCalled();
  });
  it("lets scrolling away cancel an already queued follow", () => {
    const { viewport, content } = mount(); resize(content);
    viewport.scrollTop = 100; fireEvent.scroll(viewport); paint();
    expect(scroll).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
  });
  it("does not pull a reader back after later growth", () => {
    const { viewport, content } = mount(); viewport.scrollTop = 100; fireEvent.scroll(viewport);
    resize(content); paint(); expect(scroll).not.toHaveBeenCalled();
  });
  it("resumes following after jumping and keeps keyboard focus in the transcript", () => {
    const { viewport, content } = mount(); viewport.scrollTop = 100; fireEvent.scroll(viewport);
    const jump = screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" }); jump.focus(); fireEvent.click(jump);
    expect(document.activeElement).toBe(viewport);
    scroll.mockClear(); resize(content); paint(); expect(scroll).toHaveBeenCalled();
  });
  it("honors reduced motion on the latest-message action", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
    const { viewport } = mount(); viewport.scrollTop = 100; fireEvent.scroll(viewport);
    fireEvent.click(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" }));
    expect(scroll).toHaveBeenLastCalledWith({ block: "end", behavior: "auto" });
  });
  it("supports focusing the transcript for keyboard scrolling", () => {
    const { viewport } = mount(); expect(viewport.tabIndex).toBe(0);
    viewport.focus(); expect(document.activeElement).toBe(viewport);
  });
  it("cleans up pending resize work when unmounted", () => {
    const { content, unmount } = mount(); resize(content); unmount(); paint();
    expect(scroll).not.toHaveBeenCalled();
    expect(observers.every(o => o.disconnected)).toBe(true);
  });
  it("starts a different same-length session at its own tail", () => {
    const { rerender, session } = mount();
    rerender(<NekoTranscript session={{ ...session, id: "second-session" }} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint(); expect(scroll).toHaveBeenCalled();
  });
});
