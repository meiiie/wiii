import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NekoTranscript } from "@/neko-chill/components/NekoTranscript";
import {
  activePromptIdAtScroll,
  buildPromptLandmarks,
  promptRailPosition,
  promptWavePath,
  promptWaveWidth,
  viewportScrollProgress,
} from "@/neko-chill/components/NekoPromptRail";
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

describe("Neko prompt rail", () => {
  it("forms a tapered wave around the current scroll position", () => {
    const focused = promptWaveWidth(2, 2);
    const neighbor = promptWaveWidth(1, 2);
    const distant = promptWaveWidth(0, 2);
    expect(focused).toBeCloseTo(34);
    expect(focused).toBeGreaterThan(neighbor);
    expect(neighbor).toBeGreaterThan(distant);
    expect(distant).toBeGreaterThanOrEqual(2);
    expect(promptWavePath(2).split("M ")).toHaveLength(45);
  });

  it("uses the complete scroll range and keeps the final prompt active at the bottom", () => {
    expect(viewportScrollProgress(0, 1_000, 100)).toBe(0);
    expect(viewportScrollProgress(450, 1_000, 100)).toBe(0.5);
    expect(viewportScrollProgress(900, 1_000, 100)).toBe(1);
    expect(promptRailPosition(0, 900)).toBeCloseTo(0.03);
    expect(promptRailPosition(900, 900)).toBeCloseTo(0.97);

    const offsets = [
      { id: "first", offset: 20 },
      { id: "second", offset: 640 },
      { id: "last", offset: 900 },
    ];
    expect(activePromptIdAtScroll(400, 100, offsets)).toBe("first");
    expect(activePromptIdAtScroll(900, 100, offsets)).toBe("last");
  });

  it("indexes only user turns and attaches the next complete assistant answer", () => {
    const landmarks = buildPromptLandmarks(makeSession().messages);
    expect(landmarks).toHaveLength(2);
    expect(landmarks[0]).toMatchObject({
      id: "user-1",
      messageIndex: 0,
      title: "Phân tích luồng đăng nhập hiện tại",
      preview: "Đã xác định dữ liệu cũ vẫn còn trong IndexedDB.",
      position: 0.03,
    });
    expect(landmarks[1]?.position).toBeCloseTo(2 / 3);
  });

  it("previews a prompt on hover and jumps to the exact user turn", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    render(
      <div style={{ height: 400 }}>
        <NekoTranscript
          session={makeSession()}
          onResolvePermission={vi.fn()}
          onInsertPrompt={vi.fn()}
        />
      </div>,
    );

    const rail = screen.getByRole("navigation", { name: "Điều hướng các lời nhắn của bạn" });
    expect(rail.className).toContain("left-[18px]");
    expect(screen.getByTestId("neko-wave-path")).toBeTruthy();
    const promptMarkers = screen.getAllByTestId("neko-prompt-marker");
    expect(promptMarkers).toHaveLength(2);
    expect(promptMarkers.filter((segment) => segment.dataset.active === "true")).toHaveLength(1);
    const marker = screen.getByRole("button", { name: "Đi tới lời nhắn: Bật cho tôi xem được chứ?" });
    fireEvent.mouseEnter(marker);
    expect(screen.getByRole("tooltip").textContent).toContain("Đã mở bản xem trước trên Chrome.");
    expect(screen.getAllByTestId("neko-prompt-marker")
      .filter((segment) => segment.dataset.preview === "true")).toHaveLength(1);
    fireEvent.click(marker);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start", behavior: "smooth" });
    expect(marker.getAttribute("aria-current")).toBe("location");
  });
});
