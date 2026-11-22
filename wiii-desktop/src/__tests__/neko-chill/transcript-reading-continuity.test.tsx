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
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("Neko transcript reading continuity", () => {
  function readingFixture() {
    const view = mount();
    const textRects = new WeakMap<Node, (range: Range) => DOMRect>();
    const createRange = document.createRange.bind(document);
    vi.spyOn(document, "createRange").mockImplementation(() => {
      const range = createRange();
      range.getBoundingClientRect = () => {
        const node = range.startContainer;
        const custom = textRects.get(node);
        if (custom) return custom(range);
        const rect = node.parentElement?.getBoundingClientRect() ?? new DOMRect();
        if (node.nodeType === Node.TEXT_NODE && range.endOffset - range.startOffset === 1
          && range.startOffset === (node.textContent?.length ?? 0) - 1) {
          const height = Math.min(20, rect.height);
          return { ...rect, top: rect.bottom - height, bottom: rect.bottom, height } as DOMRect;
        }
        return rect;
      };
      return range;
    });
    let width = 500;
    let paragraphTop = 320;
    const paragraph = document.createElement("p");
    paragraph.textContent = "7. Đoạn đang đọc trong câu trả lời dài";
    view.content.append(paragraph);
    Object.defineProperty(view.viewport, "clientWidth", { configurable: true, get: () => width });
    view.viewport.getBoundingClientRect = () => ({ top: 100, bottom: 500, left: 0, width, height: 400 }) as DOMRect;
    paragraph.getBoundingClientRect = () => {
      const top = 100 + paragraphTop - view.viewport.scrollTop;
      return { top, bottom: top + 30, height: 30 } as DOMRect;
    };
    view.viewport.scrollTop = 300;
    fireEvent.scroll(view.viewport);
    return { ...view, paragraph, textRects, reflow: (nextWidth: number, nextTop: number) => { width = nextWidth; paragraphTop = nextTop; } };
  }
  it("keeps the visible paragraph through wider and narrower transcript reflow", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    // Initial observer delivery establishes measured width before manual scroll.
    resize(viewport); fireEvent.scroll(viewport);
    reflow(750, 240); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(220);
    expect(paragraph.getBoundingClientRect().top).toBe(120);
    reflow(500, 320); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(300);
    expect(paragraph.getBoundingClientRect().top).toBe(120);
    expect(scroll).not.toHaveBeenCalled();
  });
  it("does not replace the anchor with a scroll event emitted by the reflow", () => {
    const { viewport, reflow } = readingFixture();
    resize(viewport); fireEvent.scroll(viewport);
    reflow(750, 240); fireEvent.scroll(viewport); resize(viewport);
    expect(viewport.scrollTop).toBe(220);
  });
  it("anchors the tall paragraph crossing the reading line, not the next closer heading", () => {
    const { viewport, content, paragraph, textRects, reflow } = readingFixture();
    let expanded = false;
    paragraph.textContent = "x".repeat(119);
    paragraph.getBoundingClientRect = () => {
      const top = 200 - viewport.scrollTop;
      const height = expanded ? 680 : 600;
      return { top, bottom: top + height, height } as DOMRect;
    };
    textRects.set(paragraph.firstChild!, (range) => {
      if (range.endOffset - range.startOffset > 1) return paragraph.getBoundingClientRect();
      const offset = range.startOffset;
      const line = expanded ? Math.floor(offset / 7) * 2 + (offset % 7 >= 4 ? 1 : 0) : Math.floor(offset / 4);
      const top = paragraph.getBoundingClientRect().top + line * 20;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    });
    const next = document.createElement("h2");
    next.textContent = "Đoạn tiếp theo";
    next.getBoundingClientRect = () => {
      const top = 100 + (expanded ? 800 : 720) - viewport.scrollTop;
      return { top, bottom: top + 30, height: 30 } as DOMRect;
    };
    content.append(next);
    resize(viewport);
    viewport.scrollTop = 600; fireEvent.scroll(viewport);
    expanded = true; reflow(750, 100); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(660); // same character; the heading moved 80px
    expect(paragraph.getBoundingClientRect().top).toBe(-460);
    expect(scroll).not.toHaveBeenCalled();
  });
  it("does not restore a reading node removed by replacement or virtualization", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    resize(viewport); fireEvent.scroll(viewport);
    paragraph.remove(); reflow(750, 240); resize(viewport);
    expect(viewport.scrollTop).toBe(300);
  });
  it("keeps a nearby paragraph edge in place when the reading line falls in a gap", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    const message = document.createElement("div");
    message.dataset.nekoMessageIndex = "99";
    paragraph.replaceWith(message);
    let expanded = false;
    message.getBoundingClientRect = () => {
      const top = 100 - viewport.scrollTop;
      return { top, bottom: top + 1000, height: 1000 } as DOMRect;
    };
    paragraph.getBoundingClientRect = () => {
      const top = 200 - viewport.scrollTop;
      const height = expanded ? 285 : 205;
      return { top, bottom: top + height, height } as DOMRect;
    };
    const next = document.createElement("p");
    next.textContent = "Đoạn đang đến gần";
    next.getBoundingClientRect = () => {
      const top = 100 + (expanded ? 410 : 330) - viewport.scrollTop;
      return { top, bottom: top + 30, height: 30 } as DOMRect;
    };
    message.append(paragraph, next);
    resize(viewport); fireEvent.scroll(viewport);
    expanded = true; reflow(750, 320); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(380);
    expect(next.getBoundingClientRect().top).toBe(130);
  });
  it("keeps direct parent-list text even with a visible nested bullet", () => {
    const { viewport, paragraph, textRects, reflow } = readingFixture();
    const list = document.createElement("ul");
    const parent = document.createElement("li");
    const ownText = paragraph.firstChild!;
    const nestedList = document.createElement("ul");
    const nested = document.createElement("li");
    nested.textContent = "Mục con";
    nestedList.append(nested); parent.append(ownText, nestedList); list.append(parent);
    paragraph.replaceWith(list);
    let expanded = false;
    parent.getBoundingClientRect = () => {
      const top = 100 + (expanded ? 240 : 320) - viewport.scrollTop;
      return { top, bottom: top + 300, height: 300 } as DOMRect;
    };
    textRects.set(ownText, () => {
      const top = parent.getBoundingClientRect().top;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    });
    nested.getBoundingClientRect = () => {
      const top = 100 + (expanded ? 300 : 450) - viewport.scrollTop;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    };
    resize(viewport); fireEvent.scroll(viewport);
    expanded = true; reflow(750, 240); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(220);
    expect(parent.getBoundingClientRect().top).toBe(120);
  });
  it("does not mistake reflow clamping for choosing to follow the tail", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    resize(viewport); fireEvent.scroll(viewport);
    reflow(750, 240);
    viewport.scrollTop = 1200; // browser clamped to the new bottom during reflow
    fireEvent.scroll(viewport); resize(viewport); paint();
    expect(paragraph.getBoundingClientRect().top).toBe(120);
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
    expect(scroll).not.toHaveBeenCalled();
  });
  it("anchors the same character across text-node streaming updates and repeated reflow", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    const original = Object.getOwnPropertyDescriptor(document, "caretRangeFromPoint");
    const range = document.createRange();
    range.setStart(paragraph.firstChild!, 12); range.collapse(true);
    let lineTop = 360;
    range.getBoundingClientRect = () => {
      if (range.startOffset === 0) return paragraph.getBoundingClientRect();
      const top = 100 + lineTop - viewport.scrollTop;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    };
    const otherCharacter = document.createRange();
    otherCharacter.setStart(paragraph.firstChild!, 22); otherCharacter.collapse(true);
    let otherLineTop = 380;
    otherCharacter.getBoundingClientRect = () => {
      const top = 100 + otherLineTop - viewport.scrollTop;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    };
    let probes = 0;
    Object.defineProperty(document, "caretRangeFromPoint", { configurable: true, value: () => ++probes === 1 ? range : otherCharacter });
    try {
      resize(viewport); fireEvent.scroll(viewport);
      paragraph.firstChild!.nodeValue += " · Nội dung đang được bổ sung";
      expect(range.startOffset).toBe(0); // native live Range reset by Text.data replacement
      reflow(750, 240); lineTop = 260; otherLineTop = 300; resize(viewport);
      expect(viewport.scrollTop).toBe(200); // character moved 100px, paragraph only 80px
      fireEvent.scroll(viewport); // own restore notification must not choose another character
      reflow(650, 260); lineTop = 280; otherLineTop = 340; resize(viewport);
      expect(viewport.scrollTop).toBe(220);
      expect(range.startOffset).toBe(12);
      paragraph.firstChild!.nodeValue = "Ngắn";
      reflow(500, 320);
      expect(() => resize(viewport)).not.toThrow(); // old offsets no longer exist
      expect(viewport.scrollTop).toBe(220);
    } finally {
      if (original) Object.defineProperty(document, "caretRangeFromPoint", original);
      else Reflect.deleteProperty(document, "caretRangeFromPoint");
    }
  });
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
