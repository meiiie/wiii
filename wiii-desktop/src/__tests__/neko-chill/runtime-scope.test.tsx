import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const queue = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn() }));
vi.mock("@/neko-chill/stores/neko-outbox-store", () => ({ startNekoOutbox: queue.start }));
const runtime = vi.hoisted(() => ({ stop: vi.fn(), start: vi.fn(), dispose: vi.fn(async () => {}) }));
vi.mock("@/neko-chill/stores/neko-session-store", () => ({ startIdleReaper: runtime.start, disposeAllNekoRuntimes: runtime.dispose }));
import { NekoRuntimeScope } from "@/neko-chill/NekoRuntimeScope";
describe("local runtime lifetime", () => {
  beforeEach(() => { vi.clearAllMocks(); runtime.start.mockReturnValue(runtime.stop); queue.start.mockReturnValue(queue.stop); });
  afterEach(cleanup);
  it("owns cleanup once at the outer scope, never at screen navigation", () => {
    const view = render(<NekoRuntimeScope><NekoRuntimeScope><span>Neko</span></NekoRuntimeScope></NekoRuntimeScope>);
    expect(runtime.start).toHaveBeenCalledOnce();
    expect(queue.start).toHaveBeenCalledOnce();
    view.rerender(<NekoRuntimeScope><span>Work</span></NekoRuntimeScope>);
    expect(runtime.dispose).not.toHaveBeenCalled();
    expect(runtime.stop).not.toHaveBeenCalled();
    view.rerender(<NekoRuntimeScope><NekoRuntimeScope><span>Neko again</span></NekoRuntimeScope></NekoRuntimeScope>);
    expect(runtime.start).toHaveBeenCalledOnce();
    expect(queue.start).toHaveBeenCalledOnce();
    view.unmount();
    expect(runtime.stop).toHaveBeenCalledOnce();
    expect(runtime.dispose).toHaveBeenCalledOnce();
    expect(queue.stop).toHaveBeenCalledOnce();
  });
  it("cleans up a standalone preview when its owner unmounts", () => {
    const view = render(<NekoRuntimeScope><span>Standalone</span></NekoRuntimeScope>);
    view.unmount();
    expect(runtime.start).toHaveBeenCalledOnce();
    expect(queue.start).toHaveBeenCalledOnce();
    expect(runtime.stop).toHaveBeenCalledOnce();
    expect(runtime.dispose).toHaveBeenCalledOnce();
    expect(queue.stop).toHaveBeenCalledOnce();
  });
});
