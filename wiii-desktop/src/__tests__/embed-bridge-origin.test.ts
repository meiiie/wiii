import { afterEach, describe, expect, it, vi } from "vitest";
import {
  sendToParent,
  setParentOrigin,
  isEmbedded,
  onParentMessage,
} from "@/lib/embed-bridge";

describe("C3: PostMessage origin validation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("isEmbedded returns false when window.self === window.top (jsdom default)", () => {
    expect(isEmbedded()).toBe(false);
  });

  it("sendToParent does not call postMessage when not embedded", () => {
    const postMessageSpy = vi.spyOn(window.parent, "postMessage");

    // Default jsdom: window.self === window.top (not embedded)
    sendToParent("wiii:test", { data: "hello" });

    expect(postMessageSpy).not.toHaveBeenCalled();
  });

  it("onParentMessage rejects messages when no allowedOrigins configured", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const handler = vi.fn();

    const cleanup = onParentMessage(handler);

    // Simulate message from parent
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:auth", payload: {} },
        origin: "https://evil.com",
      }),
    );

    expect(handler).not.toHaveBeenCalled();
    warnSpy.mockRestore();
    cleanup();
  });

  it("onParentMessage rejects messages with empty allowedOrigins array", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, []);

    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:auth", payload: {} },
        origin: "https://evil.com",
      }),
    );

    expect(handler).not.toHaveBeenCalled();
    warnSpy.mockRestore();
    cleanup();
  });

  it("onParentMessage rejects messages from non-allowed origins", () => {
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, ["https://trusted.com"]);

    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:auth", payload: {} },
        origin: "https://evil.com",
      }),
    );

    expect(handler).not.toHaveBeenCalled();
    cleanup();
  });

  it("onParentMessage accepts messages from allowed origins with wiii: prefix", () => {
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, ["https://trusted.com"]);

    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:auth", payload: { token: "fresh" } },
        origin: "https://trusted.com",
      }),
    );

    expect(handler).toHaveBeenCalledWith({
      type: "wiii:auth",
      payload: { token: "fresh" },
    });
    cleanup();
  });

  it("onParentMessage ignores non-wiii: prefixed messages from allowed origin", () => {
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, ["https://trusted.com"]);

    // Message without wiii: prefix
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "other-system:event" },
        origin: "https://trusted.com",
      }),
    );

    expect(handler).not.toHaveBeenCalled();
    cleanup();
  });

  it("onParentMessage ignores non-object messages from allowed origin", () => {
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, ["https://trusted.com"]);

    window.dispatchEvent(
      new MessageEvent("message", {
        data: "just a string",
        origin: "https://trusted.com",
      }),
    );

    expect(handler).not.toHaveBeenCalled();
    cleanup();
  });

  it("cleanup function removes event listener", () => {
    const handler = vi.fn();

    const cleanup = onParentMessage(handler, ["https://trusted.com"]);

    // First message should be received
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:theme", payload: { theme: "dark" } },
        origin: "https://trusted.com",
      }),
    );
    expect(handler).toHaveBeenCalledTimes(1);

    // Cleanup
    cleanup();

    // Second message should NOT be received
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "wiii:theme", payload: { theme: "light" } },
        origin: "https://trusted.com",
      }),
    );
    expect(handler).toHaveBeenCalledTimes(1); // Still 1
  });

  it("setParentOrigin stores the origin for later use", () => {
    // setParentOrigin should not throw
    expect(() => setParentOrigin("https://example.com")).not.toThrow();
  });
});
