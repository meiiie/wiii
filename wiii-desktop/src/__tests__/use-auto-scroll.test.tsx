import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoScroll } from "@/hooks/useAutoScroll";

let resize: () => void;
let frameId: number;
let frames: Map<number, FrameRequestCallback>;
const disconnect = vi.fn();

function Transcript() {
  const { containerRef, isAtBottom } = useAutoScroll("unchanged-source");
  return <div ref={containerRef} data-testid="transcript" data-follow={isAtBottom}>
    <div>Deferred Markdown content</div>
  </div>;
}

function paint() {
  act(() => {
    const pending = [...frames.values()];
    frames.clear();
    for (const callback of pending) callback(0);
  });
}

beforeEach(() => {
  frames = new Map();
  frameId = 0;
  disconnect.mockClear();
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.set(++frameId, callback);
    return frameId;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback: () => void) { resize = callback; }
    observe() {}
    disconnect = disconnect;
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("auto-follow after rendered layout changes", () => {
  it("cancels a queued follow when the user scrolls before its frame", () => {
    render(<Transcript />);
    const container = screen.getByTestId("transcript");
    Object.defineProperties(container, {
      scrollHeight: { value: 1200 }, clientHeight: { value: 400 },
    });
    container.scrollTo = vi.fn();
    paint();
    vi.mocked(container.scrollTo).mockClear();
    act(() => resize());
    container.scrollTop = 100;
    fireEvent.scroll(container);
    paint();
    expect(container.scrollTo).not.toHaveBeenCalled();
    expect(container.dataset.follow).toBe("false");
  });

  it("follows deferred growth without another source update and coalesces resize events", () => {
    const view = render(<Transcript />);
    const container = screen.getByTestId("transcript");
    let height = 800;
    Object.defineProperty(container, "scrollHeight", { get: () => height });
    container.scrollTo = vi.fn();
    paint();
    height = 1200;
    act(() => { resize(); resize(); });
    expect(frames.size).toBe(1);
    paint();
    expect(container.scrollTo).toHaveBeenLastCalledWith({ top: 1200, behavior: "auto" });
    act(() => resize());
    view.unmount();
    expect(frames.size).toBe(0);
    expect(disconnect).toHaveBeenCalled();
  });

  it("does not pull the user back down when a deferred render finishes", () => {
    render(<Transcript />);
    const container = screen.getByTestId("transcript");
    Object.defineProperties(container, {
      scrollHeight: { value: 1200 }, clientHeight: { value: 400 }, scrollTop: { value: 100 },
    });
    container.scrollTo = vi.fn();
    paint();
    fireEvent.scroll(container);
    paint();
    expect(container.dataset.follow).toBe("false");
    vi.mocked(container.scrollTo).mockClear();
    act(() => resize());
    paint();
    expect(container.scrollTo).not.toHaveBeenCalled();
  });
});
