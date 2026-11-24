import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NativeTabBoundary, nativeTabBoundaryEnabled } from "@/neko-chill/components/NativeTabBoundary";

describe("native shell Tab boundary", () => {
  beforeEach(() => {
    // jsdom has no layout; model rendered controls for tabbable's visibility check.
    vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(function (this: HTMLElement) {
      return (this.closest("[hidden]") ? [] : [new DOMRect(0, 0, 30, 20)]) as unknown as DOMRectList;
    });
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it.each([
    { platform: "Linux x86_64", enabled: true }, { platform: "Linux aarch64", enabled: true },
    { platform: "MacIntel", enabled: false }, { platform: "Win32", enabled: false },
  ])("limits the workaround to active Linux Tauri, not $platform's native keyboard policy", ({ platform, enabled }) => {
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue(platform);
    expect(nativeTabBoundaryEnabled(true)).toBe(enabled);
    expect(nativeTabBoundaryEnabled(false)).toBe(false);
  });

  it("leaves Linux browsers outside the native workaround", () => {
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("Linux x86_64");
    expect(nativeTabBoundaryEnabled(true)).toBe(false);
  });

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

  it("leaves reverse document entry to the browser, excluding only the forward relay", async () => {
    const { container } = render(<NativeTabBoundary enabled><button>First</button><button>Last</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "First" });
    first.focus();
    first.blur();
    expect(document.activeElement).toBe(document.body);
    const backward = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    fireEvent(document.body, backward);
    const relay = container.querySelector<HTMLElement>("[data-neko-native-tab-relay]")!;
    expect(document.activeElement).toBe(document.body);
    expect(relay.tabIndex).toBe(-1);
    expect(backward.defaultPrevented).toBe(false);
    // Do not replace the native starting point (which can follow a text click)
    // with a guessed last control. jsdom cannot prove native default traversal.
    await waitFor(() => expect(relay.tabIndex).toBe(0));
    expect(document.activeElement).toBe(document.body);
  });

  it("wraps a passive pointer anchor before the first control, such as a completion title", () => {
    const { container } = render(<NativeTabBoundary enabled>
      <h2>Completed chat</h2><button>Open result</button><button>Last</button>
    </NativeTabBoundary>);
    fireEvent.pointerDown(screen.getByRole("heading", { name: "Completed chat" }));
    const event = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    fireEvent(document.body, event);
    expect(document.activeElement).toBe(container.querySelector("[data-neko-native-tab-relay]"));
    expect(event.defaultPrevented).toBe(false);
  });

  it("does not turn a mid-page passive text anchor into a reverse boundary", () => {
    render(<NativeTabBoundary enabled><button>First</button><p>Reading here</p><button>Last</button></NativeTabBoundary>);
    fireEvent.pointerDown(screen.getByText("Reading here"));
    fireEvent.keyDown(document.body, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(document.body);
  });

  it("drops an old pointer anchor after real control focus", () => {
    render(<NativeTabBoundary enabled><h2>Old title</h2><button>First</button><input aria-label="Draft" /></NativeTabBoundary>);
    fireEvent.pointerDown(screen.getByRole("heading", { name: "Old title" }));
    const draft = screen.getByRole("textbox", { name: "Draft" });
    draft.focus();
    draft.blur();
    fireEvent.keyDown(document.body, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(document.body);
  });

  it.each([
    { key: "Tab" }, { key: "Tab", shiftKey: true, ctrlKey: true },
    { key: "Tab", shiftKey: true, altKey: true }, { key: "Tab", shiftKey: true, metaKey: true },
    { key: "Tab", shiftKey: true, isComposing: true }, { key: "Escape", shiftKey: true },
  ])("does not claim unfocused-document input for ordinary/modified keys: %j", (keys) => {
    render(<NativeTabBoundary enabled><button>First</button></NativeTabBoundary>);
    const first = screen.getByRole("button", { name: "First" });
    first.focus();
    first.blur();
    const event = new KeyboardEvent("keydown", { ...keys, bubbles: true, cancelable: true });
    fireEvent(document.body, event);
    expect(document.activeElement).toBe(document.body);
    expect(event.defaultPrevented).toBe(false);
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
