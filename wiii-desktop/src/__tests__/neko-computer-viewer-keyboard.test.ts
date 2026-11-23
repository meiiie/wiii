import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent } from "@testing-library/react";

const html = readFileSync("src-tauri/src/neko/computer/image/wiii.html", "utf8");
const fixture = new DOMParser().parseFromString(html, "text/html");
const script = fixture.querySelector('script[type="module"]')!.textContent!
  .replace(/import RFB from '[^']+';/, "");
fixture.querySelectorAll("script").forEach((element) => element.remove());

describe("Computer viewer keyboard entry", () => {
  const listeners = vi.spyOn(window, "addEventListener");

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, "postMessage").mockImplementation(() => undefined);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
      getImageData: () => ({ data: new Uint8ClampedArray(12).fill(255) }),
    } as unknown as CanvasRenderingContext2D);
  });

  afterEach(() => {
    for (const [type, listener, options] of listeners.mock.calls) {
      window.removeEventListener(type, listener as EventListener, options);
    }
    listeners.mockClear();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.mocked(window.postMessage).mockRestore();
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockRestore();
    document.body.replaceChildren();
  });

  function mount(viewOnly = "0") {
    history.replaceState(null, "", `/wiii.html?view_only=${viewOnly}`);
    // Trusted repository fixture, parsed inertly; scripts run only via the RFB stub below.
    document.body.replaceChildren(...Array.from(fixture.body.childNodes,
      (node) => document.importNode(node, true)));
    let rfb!: Viewer;
    class Viewer extends EventTarget {
      canvas = document.createElement("canvas");
      viewOnly = true;
      focus = vi.fn(() => this.canvas.focus());
      blur = vi.fn(() => this.canvas.blur());
      constructor(target: HTMLElement) {
        super();
        rfb = this;
        this.canvas.tabIndex = -1;
        target.append(this.canvas);
      }
    }
    // Run the actual shipped viewer script, replacing only the external RFB API.
    new Function("RFB", script)(Viewer);
    rfb.dispatchEvent(new Event("connect"));
    vi.advanceTimersByTime(250);
    return { rfb, region: document.getElementById("screen")! };
  }

  it("makes a ready controlled display reachable and focuses the RFB keyboard target", () => {
    const { rfb, region } = mount();
    expect(region.tabIndex).toBe(0);
    expect(region.getAttribute("aria-label")).toBeTruthy();
    region.focus();
    expect(rfb.focus).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(rfb.canvas);
    expect(rfb.viewOnly).toBe(false);
  });

  it.each(["1", "", "unexpected"])("never arms keyboard entry in observer mode %s", (mode) => {
    const { rfb, region } = mount(mode);
    expect(region.tabIndex).toBe(-1);
    region.focus();
    expect(rfb.focus).not.toHaveBeenCalled();
    expect(rfb.viewOnly).toBe(true);
  });

  it("reserves plain F8 for host return without stealing guest Tab, Escape or F10", () => {
    const { rfb, region } = mount();
    region.focus();
    const guestKey = vi.fn();
    rfb.canvas.addEventListener("keydown", guestKey);
    for (const key of ["Tab", "Escape", "F10"]) {
      expect(fireEvent.keyDown(rfb.canvas, { key })).toBe(true);
    }
    expect(fireEvent.keyDown(rfb.canvas, { key: "F8", shiftKey: true })).toBe(true);
    expect(guestKey).toHaveBeenCalledTimes(4);
    expect(fireEvent.keyDown(rfb.canvas, { key: "F8" })).toBe(false);
    expect(guestKey).toHaveBeenCalledTimes(4);
    expect(rfb.blur).toHaveBeenCalledOnce();
    expect(window.postMessage).toHaveBeenCalledWith(expect.objectContaining({
      source: "wiii-computer-viewer-v1", phase: "keyboard.release",
    }), "*");
    expect(rfb.viewOnly).toBe(false);
  });

  it("removes keyboard entry when the connection is lost", () => {
    const { rfb, region } = mount();
    rfb.dispatchEvent(new CustomEvent("disconnect", { detail: { clean: false } }));
    expect(region.tabIndex).toBe(-1);
    region.focus();
    expect(rfb.focus).not.toHaveBeenCalled();
  });
});
