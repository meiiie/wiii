import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NativeTabBoundary } from "@/neko-chill/components/NativeTabBoundary";

describe("native shell Tab boundary", () => {
  beforeEach(() => {
    // jsdom has no layout; model rendered controls for tabbable's visibility check.
    vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(function (this: HTMLElement) {
      return (this.closest("[hidden]") ? [] : [new DOMRect(0, 0, 30, 20)]) as unknown as DOMRectList;
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("wraps the forward edge to a visible enabled control without changing a draft", () => {
    const { container } = render(<NativeTabBoundary enabled>
      <button disabled>Unavailable</button><button hidden>Hidden</button><button>Sidebar</button>
      <input aria-label="Draft" defaultValue="Keep this draft" />
    </NativeTabBoundary>);
    const draft = screen.getByRole<HTMLInputElement>("textbox", { name: "Draft" });
    draft.focus();
    container.querySelector<HTMLElement>("[data-neko-native-tab-relay]")!.focus();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Sidebar" }));
    expect(draft.value).toBe("Keep this draft");
  });

  it("relays backward without preventing the browser's traversal, then resets forward wrapping", () => {
    const { container } = render(<NativeTabBoundary enabled><button>First</button><button>Last</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "First" });
    const last = screen.getByRole("button", { name: "Last" });
    const relay = container.querySelector<HTMLElement>("[data-neko-native-tab-relay]")!;
    first.focus();
    const backward = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    fireEvent(first, backward);
    expect(document.activeElement).toBe(relay);
    expect(backward.defaultPrevented).toBe(false);
    // jsdom does not execute Tab's native default. Real backward traversal is
    // checked on Tauri; here, only check that the forward relay resets afterward.
    last.focus();
    relay.focus();
    expect(document.activeElement).toBe(first);
  });

  it("uses the current first control when a notification appears before the chrome", () => {
    const { container, rerender } = render(<NativeTabBoundary enabled><button>Sidebar</button></NativeTabBoundary>);
    rerender(<NativeTabBoundary enabled><button>Open result</button><button>Sidebar</button></NativeTabBoundary>);
    screen.getByRole("button", { name: "Sidebar" }).focus();
    container.querySelector<HTMLElement>("[data-neko-native-tab-relay]")!.focus();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open result" }));
  });

  it.each([
    { key: "Tab" }, { key: "Tab", shiftKey: true, ctrlKey: true },
    { key: "Tab", shiftKey: true, altKey: true }, { key: "Tab", shiftKey: true, metaKey: true },
    { key: "Tab", shiftKey: true, isComposing: true }, { key: "Escape", shiftKey: true },
  ])("leaves ordinary and modified key handling unchanged: %j", (keys) => {
    render(<NativeTabBoundary enabled><button>First</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "First" });
    first.focus();
    const event = new KeyboardEvent("keydown", { ...keys, bubbles: true, cancelable: true });
    fireEvent(first, event);
    expect(document.activeElement).toBe(first);
    expect(event.defaultPrevented).toBe(false);
  });

  it("respects a child's existing focus trap", () => {
    render(<NativeTabBoundary enabled><button onKeyDown={(event) => event.preventDefault()}>Dialog first</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "Dialog first" });
    first.focus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(first);
  });

  it("does not add a relay or intercept traversal when disabled for browser/inactive surfaces", () => {
    const { container } = render(<NativeTabBoundary enabled={false}><button>First</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "First" });
    first.focus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(container.querySelector("[data-neko-native-tab-relay]")).toBeNull();
    expect(document.activeElement).toBe(first);
  });
});
