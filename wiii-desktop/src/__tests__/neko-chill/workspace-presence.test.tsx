import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWorkspacePresence } from "@/neko-chill/hooks/useWorkspacePresence";

function Fixture({ open, identity = "project" }: { open: boolean; identity?: string }) {
  const presence = useWorkspacePresence(open, identity);
  return presence.present ? <div ref={presence.ref} data-testid="pane" aria-hidden={!open || undefined}>
    <input aria-label="Workspace draft" defaultValue="keep me" />
  </div> : null;
}

describe("workspace presentation lifecycle", () => {
  const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "animate");
  const motionListeners = new Set<() => void>();
  const motionPreference = {
    matches: false,
    addEventListener: (_type: string, listener: () => void) => motionListeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => motionListeners.delete(listener),
  };
  const animations: { onfinish: (() => void) | null; cancel: ReturnType<typeof vi.fn> }[] = [];
  const animate = vi.fn(() => {
    const animation = { onfinish: null as (() => void) | null, cancel: vi.fn() };
    animations.push(animation);
    return animation;
  });

  beforeEach(() => {
    animations.length = 0;
    animate.mockClear();
    motionListeners.clear();
    motionPreference.matches = false;
    Object.defineProperty(HTMLElement.prototype, "animate", { configurable: true, value: animate });
    vi.stubGlobal("matchMedia", vi.fn(() => motionPreference));
  });

  afterEach(() => {
    if (original) Object.defineProperty(HTMLElement.prototype, "animate", original);
    else Reflect.deleteProperty(HTMLElement.prototype, "animate");
    vi.unstubAllGlobals();
  });

  it("makes a closing pane inert immediately and removes it when the exit completes", () => {
    const view = render(<Fixture open />);
    act(() => animations.at(-1)?.onfinish?.());
    view.rerender(<Fixture open={false} />);
    const pane = screen.getByTestId("pane");
    expect(pane.inert).toBe(true);
    expect(pane.getAttribute("aria-hidden")).toBe("true");
    act(() => animations.at(-1)?.onfinish?.());
    expect(screen.queryByTestId("pane")).toBeNull();
  });

  it("reverses without remounting content and ignores an interrupted exit callback", () => {
    const view = render(<Fixture open />);
    const input = screen.getByRole("textbox");
    view.rerender(<Fixture open={false} />);
    const staleFinish = animations.at(-1)?.onfinish;
    view.rerender(<Fixture open />);
    act(() => staleFinish?.());
    expect(screen.getByRole("textbox")).toBe(input);
    expect(screen.getByTestId("pane").inert).toBe(false);
    expect(screen.getByTestId("pane").hasAttribute("aria-hidden")).toBe(false);
  });

  it("does not retain another project's closing surface", () => {
    const view = render(<Fixture open identity="a" />);
    view.rerender(<Fixture open={false} identity="b" />);
    expect(screen.queryByTestId("pane")).toBeNull();
    expect(animations[0].cancel).toHaveBeenCalled();
  });

  it("closes immediately for reduced motion", () => {
    motionPreference.matches = true;
    const view = render(<Fixture open />);
    view.rerender(<Fixture open={false} />);
    expect(screen.queryByTestId("pane")).toBeNull();
    expect(animate).not.toHaveBeenCalled();
  });

  it("finishes an active exit when reduced motion is enabled and removes its listener", () => {
    const view = render(<Fixture open />);
    view.rerender(<Fixture open={false} />);
    act(() => {
      motionPreference.matches = true;
      for (const listener of motionListeners) listener();
    });
    expect(screen.queryByTestId("pane")).toBeNull();
    expect(motionListeners.size).toBe(0);
  });

  it("closes immediately when animation is unavailable", () => {
    Reflect.deleteProperty(HTMLElement.prototype, "animate");
    const view = render(<Fixture open />);
    view.rerender(<Fixture open={false} />);
    expect(screen.queryByTestId("pane")).toBeNull();
  });

  it("uses static presentation when motion preferences cannot be queried", () => {
    vi.stubGlobal("matchMedia", undefined);
    const view = render(<Fixture open />);
    view.rerender(<Fixture open={false} />);
    expect(screen.queryByTestId("pane")).toBeNull();
    expect(animate).not.toHaveBeenCalled();
  });

  it("cancels its animation on unmount without a background timer", () => {
    const view = render(<Fixture open />);
    const animation = animations[0];
    view.unmount();
    expect(animation.cancel).toHaveBeenCalled();
    expect(animation.onfinish).toBeNull();
    expect(motionListeners.size).toBe(0);
  });
});
