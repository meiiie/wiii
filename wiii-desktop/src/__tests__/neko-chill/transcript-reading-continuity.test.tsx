import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NekoTranscript } from "@/neko-chill/components/NekoTranscript";
import * as virtualization from "@tanstack/react-virtual";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { captureTranscriptReadingBookmark, restoreTranscriptReadingBookmark, type TranscriptReadingPosition } from "@/neko-chill/transcript-reading-anchor";

vi.mock("@tanstack/react-virtual", { spy: true });

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
function mount(session = makeSession(), readingPositions?: Map<string, TranscriptReadingPosition>) {
  const view = render(<NekoTranscript session={session} readingPositions={readingPositions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
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
  vi.mocked(virtualization.useVirtualizer).mockReset();
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
  it("isolates table columns per message/session through remounts and resize clamps", async () => {
    const session = makeSession();
    session.messages[1].blocks = [{ id: "answer-1", type: "answer", content: "| Lô | Hạn |\n| --- | --- |\n| GAMMA | 14:00 |" }];
    // Blocks need only be unique within their message, not the entire session.
    session.messages[3].blocks = [{ ...session.messages[1].blocks[0] }];
    const positions = new Map<string, TranscriptReadingPosition>();
    const view = mount(session, positions);
    const tables = await screen.findAllByRole("region", { name: "Bảng" });
    const table = tables[0];
    let width = 300;
    let extent = 900;
    let left = 0;
    Object.defineProperties(table, {
      clientWidth: { configurable: true, get: () => width },
      scrollWidth: { configurable: true, get: () => extent },
      scrollLeft: { configurable: true, get: () => left, set: v => { left = Math.max(0, Math.min(extent - width, v)); } },
    });
    resize(table);
    table.scrollLeft = 480; fireEvent.scroll(table);
    tables[1].scrollLeft = 96; fireEvent.scroll(tables[1]);
    // A native resize clamp is not the user choosing the first columns.
    width = 1000; table.scrollLeft = 0; fireEvent.scroll(table); resize(table);
    width = 300; resize(table);
    expect(table.scrollLeft).toBe(480);
    extent = 500; table.scrollLeft = 200; fireEvent.scroll(table); resize(table);
    extent = 900; resize(table);
    expect(table.scrollLeft).toBe(480);
    view.viewport.scrollTop = 100; fireEvent.scroll(view.viewport);
    const show = (current: NekoSession) => <NekoTranscript session={current} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />;
    // Same block IDs deliberately exercise isolation by session, not content.
    const other = { ...session, id: "session-B" };
    view.rerender(show(other));
    const tableB = screen.getAllByRole("region", { name: "Bảng" })[0];
    expect(tableB.scrollLeft).toBe(0);
    tableB.scrollLeft = 64; fireEvent.scroll(tableB);
    view.rerender(show(session));
    expect(screen.getAllByRole("region", { name: "Bảng" }).map(t => t.scrollLeft)).toEqual([480, 96]);
    view.rerender(show(other));
    expect(screen.getAllByRole("region", { name: "Bảng" }).map(t => t.scrollLeft)).toEqual([64, 0]);
    view.unmount();
    mount(session, positions);
    expect((await screen.findAllByRole("region", { name: "Bảng" })).map(t => t.scrollLeft)).toEqual([480, 96]);
  });

  function readingFixture(session = makeSession()) {
    const view = mount(session);
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

  it("keeps an older text anchor while virtual measurement scroll arrives before row layout", () => {
    const { viewport, content, paragraph, reflow } = readingFixture();
    resize(viewport); fireEvent.scroll(viewport);
    const hook = vi.mocked(virtualization.useVirtualizer);
    const options = hook.mock.calls[hook.mock.calls.length - 1][0];
    const instance = hook.mock.results[hook.mock.results.length - 1].value;
    instance.scrollElement = viewport;
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: (next: ScrollToOptions) => { viewport.scrollTop = next.top ?? viewport.scrollTop; } });

    // TanStack adjusts the offset immediately; React commits row transforms
    // afterward. That intermediate scroll must not pick a new reading anchor.
    act(() => options.scrollToFn?.(300, { adjustments: -100 }, instance));
    expect(viewport.scrollTop).toBe(200);
    fireEvent.scroll(viewport);
    reflow(500, 220); resize(content); paint();
    expect(viewport.scrollTop).toBe(200);
    expect(paragraph.getBoundingClientRect().top).toBe(120);

    // A later genuine scroll may revisit that old automatic offset. It must
    // own the anchor again, rather than being suppressed by a stale marker.
    viewport.scrollTop = 100; fireEvent.scroll(viewport);
    viewport.scrollTop = 200; fireEvent.scroll(viewport);
    reflow(500, 240); resize(content); paint();
    expect(viewport.scrollTop).toBe(220);
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
  });

  it.each([false, true])("keeps virtual question jumps as the new reading position (reduced motion: %s)", (reducedMotion) => {
    vi.stubGlobal("matchMedia", () => ({ matches: reducedMotion, addEventListener() {}, removeEventListener() {} }));
    const session = makeSession();
    session.messages = Array.from({ length: 52 }, (_, index) => ({ id: `question-${index}`, role: "user" as const, text: `Câu hỏi ${index + 1}` }));
    const fakeVirtualizer = {
      getTotalSize: () => 5200,
      getVirtualItems: () => session.messages.map((message, index) => ({ index, key: message.id, start: index * 100, size: 100, end: index * 100 + 100, lane: 0 })),
      getOffsetForIndex: (index: number) => [index * 100],
      measureElement: vi.fn(),
      scrollToIndex: vi.fn((index: number, next: { behavior?: ScrollBehavior }) => {
        const hook = vi.mocked(virtualization.useVirtualizer);
        const options = hook.mock.calls[hook.mock.calls.length - 1][0];
        const instance = { scrollElement: screen.getByRole("log"), options: { horizontal: false } } as ReturnType<typeof virtualization.useVirtualizer>;
        options.scrollToFn?.(300 + index * 5, { behavior: next.behavior }, instance);
      }),
    };
    vi.mocked(virtualization.useVirtualizer).mockReturnValue(fakeVirtualizer as unknown as ReturnType<typeof virtualization.useVirtualizer>);
    const { viewport, content } = readingFixture(session);
    resize(viewport); fireEvent.scroll(viewport);
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: (next: ScrollToOptions) => { viewport.scrollTop = next.top ?? viewport.scrollTop; } });
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 52" }));
    fireEvent.click(screen.getByRole("button", { name: /^Đi tới lời nhắn 3:/ }));
    expect(fakeVirtualizer.scrollToIndex).toHaveBeenLastCalledWith(2, { align: "start", behavior: "auto" });
    fireEvent.scroll(viewport);
    expect(viewport.scrollTop).toBe(310);
    resize(content); paint();
    expect(viewport.scrollTop).toBe(310);
    expect(document.activeElement).toBe(viewport.querySelector('[data-neko-message-id="question-2"]'));
  });
  it("rebinds a saved character to remounted DOM after its chat changed width", () => {
    const { viewport, paragraph, reflow } = readingFixture();
    viewport.querySelector("[data-neko-message-id]")!.append(paragraph);
    const bookmark = captureTranscriptReadingBookmark(viewport);
    expect(bookmark).not.toBeNull();
    const replacement = paragraph.cloneNode(true) as HTMLElement;
    paragraph.replaceWith(replacement);
    replacement.getBoundingClientRect = () => {
      const top = 340 - viewport.scrollTop;
      return { top, bottom: top + 30, height: 30 } as DOMRect;
    };
    reflow(750, 240);
    expect(restoreTranscriptReadingBookmark(viewport, bookmark!)).toBe(true);
    expect(viewport.scrollTop).toBe(220);
    replacement.textContent = "Nội dung đã thay đổi";
    expect(restoreTranscriptReadingBookmark(viewport, bookmark!)).toBe(false);
    expect(viewport.scrollTop).toBe(220);
    replacement.closest("[data-neko-message-id]")?.remove();
    expect(restoreTranscriptReadingBookmark(viewport, bookmark!)).toBe(false);
  });
  it("retains each chat's reading mode and position through unmounts without retaining its DOM", () => {
    const positions = new Map<string, TranscriptReadingPosition>();
    const first = mount(makeSession(), positions);
    first.viewport.scrollTop = 100; fireEvent.scroll(first.viewport);
    first.unmount();
    const secondSession = { ...makeSession(), id: "second-session" };
    const second = mount(secondSession, positions);
    second.viewport.scrollTop = 700; fireEvent.scroll(second.viewport);
    second.unmount(); scroll.mockClear();
    const back = render(<NekoTranscript session={first.session} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint();
    expect(screen.getByRole("log").scrollTop).toBe(100);
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
    expect(scroll).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" }));
    back.unmount(); scroll.mockClear();
    const other = render(<NekoTranscript session={secondSession} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint();
    expect(screen.getByRole("log").scrollTop).toBe(700);
    expect(scroll).not.toHaveBeenCalled();
    other.unmount();
    render(<NekoTranscript session={first.session} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint();
    expect(scroll).toHaveBeenCalledWith({ block: "end", behavior: "auto" });
    expect(screen.queryByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeNull();
  });
  it("still follows a newly sent user message after restoring older reading", () => {
    const positions = new Map<string, TranscriptReadingPosition>();
    const { viewport, session, rerender } = mount(makeSession(), positions);
    viewport.scrollTop = 100; fireEvent.scroll(viewport);
    rerender(<NekoTranscript session={{ ...session, messages: [...session.messages, { id: "new-user", role: "user", text: "Câu hỏi tiếp theo" }] }} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint();
    expect(scroll).toHaveBeenCalledWith({ block: "end", behavior: "auto" });
    expect(screen.queryByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeNull();
  });
  it("returns to the same older virtual row after remounting measured, unequal-height history", () => {
    const session = makeSession();
    session.messages = Array.from({ length: 56 }, (_, index) => index % 2
      ? { id: `history-${index}`, role: "assistant" as const, blocks: [{ id: `answer-${index}`, type: "answer" as const, content: `Mốc ${index}` }] }
      : { id: `history-${index}`, role: "user" as const, text: `Mốc ${index}` });
    const positions = new Map<string, TranscriptReadingPosition>([[session.id, { followingTail: false, scrollTop: 1500, bookmark: null }]]);
    const isViewport = (element: HTMLElement) => element.dataset.testid === "neko-transcript";
    const height = (element: HTMLElement) => isViewport(element) ? 400 : element.hasAttribute("data-index") ? Number(element.dataset.index) % 2 ? 44 : 72 : 0;
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(function () { return height(this); });
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(600);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(600);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function () { return isViewport(this) ? 400 : height(this); });
    vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function () {
      return isViewport(this) ? Number.parseFloat((this.firstElementChild?.firstElementChild as HTMLElement | null)?.style.height ?? "0") + 32 : height(this);
    });
    const originalScrollTo = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollTo");
    Object.defineProperty(HTMLElement.prototype, "scrollTo", { configurable: true, value: function (this: HTMLElement, options: ScrollToOptions) { this.scrollTop = options.top ?? this.scrollTop; } });
    const renderChat = () => render(<NekoTranscript session={session} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    const settle = (viewport: HTMLElement) => {
      for (let pass = 0; pass < 8; pass++) {
        paint(); fireEvent.scroll(viewport);
        act(() => {
          for (const observer of [...observers].filter((item) => !item.disconnected && item.elements.size > 0)) {
            const entries = [...observer.elements].map((target) => ({ target, borderBoxSize: [{ blockSize: height(target as HTMLElement), inlineSize: 600 }] })) as unknown as ResizeObserverEntry[];
            (observer.callback as ResizeObserverCallback)(entries, {} as ResizeObserver);
          }
        });
      }
    };
    const topRow = (viewport: HTMLElement) => [...viewport.querySelectorAll<HTMLElement>("[data-index]")].find((row) => {
      const start = Number(/translateY\(([-\d.]+)px\)/.exec(row.style.transform)?.[1] ?? 0);
      return start + height(row) > viewport.scrollTop;
    })?.dataset.index;
    try {
      const first = renderChat();
      const viewport = screen.getByRole("log"); settle(viewport);
      viewport.scrollTop = 1500; fireEvent.scroll(viewport); settle(viewport);
      const reference = topRow(viewport);
      expect(reference).toBeDefined();
      expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
      first.unmount();
      renderChat();
      const returned = screen.getByRole("log"); settle(returned);
      expect(topRow(returned)).toBe(reference);
      expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
    } finally {
      cleanup();
      if (originalScrollTo) Object.defineProperty(HTMLElement.prototype, "scrollTo", originalScrollTo);
      else Reflect.deleteProperty(HTMLElement.prototype, "scrollTo");
    }
  });

  it("keeps the cached pixel fallback when a virtual row mounts with changed bookmarked text", () => {
    const session = makeSession();
    session.messages = Array.from({ length: 52 }, (_, index) => ({ id: `message-${index}`, role: "user" as const, text: `Tin nhắn ${index}` }));
    const fakeVirtualizer = {
      getTotalSize: () => 5200,
      getVirtualItems: () => session.messages.map((message, index) => ({ index, key: message.id, start: index * 100, size: 100, end: index * 100 + 100, lane: 0 })),
      measureElement: vi.fn(),
      getOffsetForIndex: (index: number) => [index * 100],
      scrollToIndex: vi.fn(() => { screen.getByRole("log").scrollTop = 1000; }),
    };
    vi.mocked(virtualization.useVirtualizer).mockReturnValue(fakeVirtualizer as unknown as ReturnType<typeof virtualization.useVirtualizer>);
    const positions = new Map<string, TranscriptReadingPosition>([[session.id, {
      followingTail: false, scrollTop: 2400,
      bookmark: { messageId: "message-10", path: [], offset: 12, character: 0, sample: "Nội dung cũ" },
    }]]);
    render(<NekoTranscript session={session} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    paint();
    expect(fakeVirtualizer.scrollToIndex).toHaveBeenCalledWith(10, { align: "start" });
    expect(screen.getByRole("log").scrollTop).toBe(2400);
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
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
  it("ignores clipped tool lines even when their full range overlaps the answer below", () => {
    const { viewport, paragraph, textRects, reflow } = readingFixture();
    let expanded = false;
    const clip = document.createElement("div");
    clip.style.overflowY = "auto";
    Object.defineProperty(clip, "clientHeight", { value: 88 });
    clip.getBoundingClientRect = () => {
      const top = 320 - viewport.scrollTop;
      return { top, bottom: top + 88, height: 88 } as DOMRect;
    };
    const output = document.createElement("p");
    output.textContent = "ABC";
    output.getBoundingClientRect = () => {
      const top = 320 - viewport.scrollTop;
      return { top, bottom: top + 980, height: 980 } as DOMRect;
    };
    textRects.set(output.firstChild!, (range) => {
      if (range.endOffset - range.startOffset > 1) return output.getBoundingClientRect();
      const top = 100 + [220, expanded ? 500 : 320, 1180][range.startOffset] - viewport.scrollTop;
      return { top, bottom: top + 20, height: 20 } as DOMRect;
    });
    clip.append(output); paragraph.before(clip);
    resize(viewport); fireEvent.scroll(viewport);
    expanded = true; reflow(750, 240); resize(viewport); paint();
    expect(viewport.scrollTop).toBe(220);
    expect(paragraph.getBoundingClientRect().top).toBe(120);
  });
  it("keeps the same image region when an image-only paragraph fills the viewport", () => {
    const { viewport, content, paragraph, reflow } = readingFixture();
    paragraph.remove();
    const image = document.createElement("img");
    content.append(image);
    let imageTop = 250;
    let height = 1000;
    image.getBoundingClientRect = () => {
      const top = 100 + imageTop - viewport.scrollTop;
      return { top, bottom: top + height, left: 0, right: 500, width: 500, height } as DOMRect;
    };
    resize(viewport); fireEvent.scroll(viewport);
    const fraction = (112 - image.getBoundingClientRect().top) / height;
    imageTop = 170; height = 1200; reflow(750, 240); resize(viewport); paint();
    expect(viewport.scrollTop).toBeCloseTo(232.4);
    expect((112 - image.getBoundingClientRect().top) / height).toBeCloseTo(fraction);
    image.remove(); reflow(500, 320); resize(viewport);
    expect(viewport.scrollTop).toBeCloseTo(232.4);
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
  it.each([false, true])("follows a new send crossing 50 messages, including a reader previously away: %s", (readingOlder) => {
    const session = makeSession();
    session.messages = Array.from({ length: 50 }, (_, index) => ({ id: `old-${index}`, role: index % 2 ? "assistant" as const : "user" as const, text: `Mốc ${index}` }));
    const positions = new Map<string, TranscriptReadingPosition>([[session.id, { followingTail: true, scrollTop: 1000, bookmark: null }]]);
    const { viewport, rerender } = mount(session, positions);
    const scrollTo = vi.fn((options: ScrollToOptions) => { viewport.scrollTop = options.top ?? viewport.scrollTop; });
    Object.defineProperties(viewport, {
      offsetHeight: { configurable: true, value: 400 },
      offsetWidth: { configurable: true, value: 600 },
      scrollTo: { configurable: true, value: scrollTo },
    });
    if (readingOlder) { viewport.scrollTop = 800; fireEvent.scroll(viewport); }
    // Real TanStack bootstrap/measurements replace the non-virtual geometry.
    // Its queued scroll is NOT the reader leaving the newly submitted turn.
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 6400 });
    const next = { ...session, messages: [...session.messages, { id: "new-user", role: "user" as const, text: "Lời nhắn mới" }] };
    rerender(<NekoTranscript session={next} readingPositions={positions} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    fireEvent.scroll(viewport);
    paint();
    expect(screen.queryByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeNull();
    expect(scrollTo.mock.calls.some(([options]) => (options.top ?? 0) > 1200)).toBe(true);
    // An actual later reader scroll still cancels virtual tail-following.
    viewport.scrollTop = 600; fireEvent.scroll(viewport); scrollTo.mockClear();
    paint();
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
    expect(scrollTo).not.toHaveBeenCalled();
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
  it("keeps following when an automatic scroll arrives after more content rendered", () => {
    const { viewport, content } = mount();
    // The prior frame reached the tail. Its scroll event is delivered only
    // after another chunk has pushed the ending more than 96px further down.
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 2000 });
    fireEvent.scroll(viewport);
    resize(content); paint();
    expect(scroll).toHaveBeenCalledWith({ block: "end", behavior: "auto" });
    expect(screen.queryByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeNull();
  });
  it("still honors a reader scrolling away while the answer grows", () => {
    const { viewport, content } = mount();
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 2000 });
    viewport.scrollTop = 1000;
    fireEvent.scroll(viewport);
    resize(content); paint();
    expect(scroll).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeTruthy();
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
