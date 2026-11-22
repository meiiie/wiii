import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NekoTranscript } from "@/neko-chill/components/NekoTranscript";
import {
  activePromptIdAtScroll,
  buildPromptLandmarks,
  NekoPromptRail,
} from "@/neko-chill/components/NekoPromptRail";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

const virtual = vi.hoisted(() => ({
  rows: [] as Array<{ index: number; start: number }>,
  scrollToIndex: vi.fn(),
  getTotalSize: () => 10000,
  getVirtualItems: () => virtual.rows,
  getOffsetForIndex: (index: number) => [index * 180],
  measureElement: vi.fn(),
}));
vi.mock("@tanstack/react-virtual", () => ({ useVirtualizer: () => virtual }));

beforeEach(() => {
  virtual.rows = [];
  virtual.scrollToIndex.mockClear();
});

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

describe("Neko question navigation", () => {
  it("indexes user turns without exposing assistant text in navigation", () => {
    expect(buildPromptLandmarks(makeSession().messages)).toEqual([
      { id: "user-1", messageIndex: 0, title: "Phân tích luồng đăng nhập hiện tại" },
      { id: "user-2", messageIndex: 2, title: "Bật cho tôi xem được chứ?" },
    ]);
    expect(buildPromptLandmarks([{ id: "code", role: "user", text: "```ts\nconst x = 1;\n```" }])[0].title).toBe("Đoạn mã");
  });

  it("tracks the reading line and final prompt, including an empty history", () => {
    const offsets = [{ id: "first", offset: 20 }, { id: "second", offset: 640 }, { id: "last", offset: 900 }];
    expect(activePromptIdAtScroll(400, 100, offsets)).toBe("first");
    expect(activePromptIdAtScroll(900, 100, offsets)).toBe("last");
    expect(activePromptIdAtScroll(0, 100, [])).toBeNull();
  });

  function mount(session = makeSession()) {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const props = { session, onResolvePermission: vi.fn(), onInsertPrompt: vi.fn() };
    return { ...render(<div style={{ height: 400 }}><NekoTranscript {...props} /></div>), props, scrollIntoView };
  }

  it("closes the index and anchors keyboard navigation at the selected message, not the transcript start", () => {
    const { scrollIntoView, props } = mount();
    const trigger = screen.getByRole("button", { name: "Câu hỏi 2" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("button", { name: /Đi tới lời nhắn 2/ })).toBeNull();
    fireEvent.click(trigger);
    const destination = screen.getByRole("button", { name: "Đi tới lời nhắn 2: Bật cho tôi xem được chứ?" });
    fireEvent.click(destination);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start", behavior: "smooth" });
    expect(scrollIntoView.mock.contexts.at(-1)).toBe(document.querySelector('[data-neko-message-index="2"]'));
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("tooltip")).toBeNull();
    const anchor = document.querySelector<HTMLDivElement>('[data-neko-message-index="2"]');
    expect(document.activeElement).toBe(anchor);
    expect(anchor?.tabIndex).toBe(-1);
    expect(props.onResolvePermission).not.toHaveBeenCalled();
    expect(props.onInsertPrompt).not.toHaveBeenCalled();
  });

  it("supports keyboard choice and Escape without activating or obscuring a prompt", async () => {
    const { scrollIntoView } = mount();
    const trigger = screen.getByRole("button", { name: "Câu hỏi 2" });
    act(() => trigger.focus());
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    await act(async () => { await new Promise(requestAnimationFrame); });
    expect(screen.getAllByRole("button", { name: /Đi tới lời nhắn/ })).toContain(document.activeElement);
    scrollIntoView.mockClear();
    fireEvent.keyDown(document.activeElement!, { key: "Home" });
    const first = screen.getByRole("button", { name: /Đi tới lời nhắn 1:/ });
    const last = screen.getByRole("button", { name: /Đi tới lời nhắn 2:/ });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "End" });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(last, { key: "ArrowUp" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Escape" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("keeps every dense-history question reachable even when all measured offsets coincide", () => {
    const session = makeSession();
    session.messages = Array.from({ length: 80 }, (_, i) => ({ id: `user-${i}`, role: "user", text: `Câu hỏi số ${i + 1}` }));
    const onJump = vi.fn();
    const viewport = document.createElement("div");
    const resolveMessageOffset = vi.fn(() => 0);
    render(<NekoPromptRail messages={session.messages} scrollRef={{ current: viewport }}
      resolveMessageOffset={resolveMessageOffset} onJump={onJump} />);
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 80" }));
    expect(screen.getAllByRole("button", { name: /Đi tới lời nhắn/ })).toHaveLength(80);
    fireEvent.click(screen.getByRole("button", { name: "Đi tới lời nhắn 37: Câu hỏi số 37" }));
    expect(resolveMessageOffset).toHaveBeenCalledTimes(80);
    expect(onJump).toHaveBeenCalledExactlyOnceWith({ id: "user-36", messageIndex: 36, title: "Câu hỏi số 37" });
    expect(screen.queryByRole("button", { name: /Đi tới lời nhắn/ })).toBeNull();
  });

  it("dismisses on outside input and does not carry an open index to another conversation", () => {
    const view = mount();
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 2" }));
    fireEvent.pointerDown(screen.getByTestId("neko-transcript"));
    expect(screen.queryByRole("button", { name: /Đi tới lời nhắn/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 2" }));
    const next = makeSession();
    next.id = "different-session";
    next.messages = next.messages.map(message => ({ ...message, id: "next-" + message.id }));
    view.rerender(<div style={{ height: 400 }}><NekoTranscript {...view.props} session={next} /></div>);
    expect(screen.getByRole("button", { name: "Câu hỏi 2" }).getAttribute("aria-expanded")).toBe("false");
    expect(view.scrollIntoView).not.toHaveBeenCalled();
  });

  it("does not add navigation chrome for a one-turn chat", () => {
    mount({ ...makeSession(), messages: makeSession().messages.slice(0, 2) });
    expect(screen.queryByRole("navigation", { name: "Điều hướng các lời nhắn của bạn" })).toBeNull();
  });

  it("focuses an offscreen virtual destination when it mounts", () => {
    const session = makeSession();
    session.messages = Array.from({ length: 60 }, (_, index) => ({
      id: `long-${index}`, role: "user", text: `Câu hỏi dài ${index + 1}`,
    }));
    virtual.rows = [{ index: 0, start: 0 }];
    const view = mount(session);
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 60" }));
    fireEvent.click(screen.getByRole("button", { name: "Đi tới lời nhắn 58: Câu hỏi dài 58" }));
    expect(virtual.scrollToIndex).toHaveBeenCalledWith(57, { align: "start", behavior: "smooth" });
    expect(document.querySelector('[data-neko-message-index="57"]')).toBeNull();

    virtual.rows = [{ index: 57, start: 10260 }];
    view.rerender(<div style={{ height: 400 }}><NekoTranscript {...view.props} /></div>);
    expect(document.activeElement).toBe(document.querySelector('[data-neko-message-index="57"]'));
    expect(view.scrollIntoView).not.toHaveBeenCalled();
  });

  it("does not carry a pending virtual focus into another conversation", () => {
    const session = makeSession();
    session.messages = Array.from({ length: 60 }, (_, index) => ({
      id: `shared-${index}`, role: "user", text: `Câu hỏi dài ${index + 1}`,
    }));
    virtual.rows = [{ index: 0, start: 0 }];
    const view = mount(session);
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi 60" }));
    fireEvent.click(screen.getByRole("button", { name: "Đi tới lời nhắn 58: Câu hỏi dài 58" }));
    const outside = document.createElement("button");
    document.body.append(outside);
    act(() => outside.focus());
    virtual.rows = [{ index: 57, start: 10260 }];
    view.rerender(<div style={{ height: 400 }}><NekoTranscript {...view.props} session={{ ...session, id: "other-conversation" }} /></div>);
    expect(document.activeElement).toBe(outside);
    outside.remove();
  });
});
