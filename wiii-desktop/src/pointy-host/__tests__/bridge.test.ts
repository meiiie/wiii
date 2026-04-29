/**
 * Tests for the PostMessage bridge — protocol validation, origin filtering,
 * action dispatch, and reply targeting.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  _testing,
  createBridge,
  describeTarget,
  handleHighlight,
  handleNavigate,
  handleScrollTo,
  resolveSelector,
  type BridgeHandle,
} from "../bridge";
import { destroy } from "../index";

const liveBridges: BridgeHandle[] = [];

function makeBridge(...args: Parameters<typeof createBridge>): BridgeHandle {
  const h = createBridge(...args);
  liveBridges.push(h);
  return h;
}

afterEach(() => {
  while (liveBridges.length) {
    liveBridges.pop()?.dispose();
  }
  destroy();
  document.body.innerHTML = "";
});

describe("isPointyRequest", () => {
  it("accepts a well-formed request", () => {
    expect(
      _testing.isPointyRequest({
        type: "wiii:action-request",
        id: "abc",
        action: "ui.highlight",
        params: { selector: "#x" },
      }),
    ).toBe(true);
  });

  it("rejects messages of other types", () => {
    expect(
      _testing.isPointyRequest({
        type: "wiii:capabilities",
        id: "abc",
        action: "ui.highlight",
        params: {},
      }),
    ).toBe(false);
    expect(_testing.isPointyRequest("not-an-object")).toBe(false);
    expect(_testing.isPointyRequest(null)).toBe(false);
  });
});

describe("isSafeUrl", () => {
  it("accepts public https URLs", () => {
    expect(_testing.isSafeUrl("https://holilihu.online/courses/1")).toBe(true);
  });
  it("rejects loopback and internal hosts", () => {
    expect(_testing.isSafeUrl("http://localhost:8000/")).toBe(false);
    expect(_testing.isSafeUrl("http://127.0.0.1/")).toBe(false);
    expect(_testing.isSafeUrl("https://foo.local/")).toBe(false);
  });
  it("rejects non-http schemes", () => {
    expect(_testing.isSafeUrl("file:///etc/passwd")).toBe(false);
    expect(_testing.isSafeUrl("javascript:alert(1)")).toBe(false);
  });
});

describe("resolveSelector", () => {
  it("returns null for empty or non-string input", () => {
    expect(resolveSelector("")).toBeNull();
    expect(resolveSelector("   ")).toBeNull();
    expect(resolveSelector(undefined)).toBeNull();
    expect(resolveSelector(123)).toBeNull();
  });
  it("returns null for invalid CSS", () => {
    expect(resolveSelector(">>>not-valid")).toBeNull();
  });
  it("resolves data-wiii-id and id selectors", () => {
    document.body.innerHTML = `<button id="b1" data-wiii-id="login-btn">Login</button>`;
    expect(resolveSelector("#b1")?.tagName).toBe("BUTTON");
    expect(resolveSelector('[data-wiii-id="login-btn"]')?.tagName).toBe("BUTTON");
  });
});

describe("describeTarget", () => {
  it("prefers data-wiii-id, then id, then aria, then text", () => {
    document.body.innerHTML = `
      <button id="ok" data-wiii-id="submit">Gửi</button>
      <button id="x" aria-label="Đóng"></button>
      <button id="y">Mở</button>
      <button>Khám phá</button>
    `;
    expect(describeTarget(document.querySelector("[data-wiii-id]")!)).toContain("#submit");
    expect(describeTarget(document.querySelector('[aria-label="Đóng"]')!)).toContain('"Đóng"');
    expect(describeTarget(document.querySelector("#y")!)).toContain("#y");
    // Element with neither id nor aria falls back to its text content.
    const buttons = document.querySelectorAll("button");
    expect(describeTarget(buttons[buttons.length - 1])).toContain('"Khám phá"');
  });
});

describe("handleHighlight", () => {
  it("returns success when selector resolves", async () => {
    document.body.innerHTML = `<button data-wiii-id="login">Login</button>`;
    const result = await handleHighlight({ selector: '[data-wiii-id="login"]' });
    expect(result.success).toBe(true);
    expect(result.data?.summary).toContain("login");
  });
  it("returns failure when selector missing", async () => {
    const result = await handleHighlight({ selector: "#nope" });
    expect(result.success).toBe(false);
    expect(result.error).toContain("selector_not_found");
  });
});

describe("handleScrollTo", () => {
  it("succeeds for present target", async () => {
    document.body.innerHTML = `<section id="ch1">Chapter 1</section>`;
    const result = await handleScrollTo({ selector: "#ch1" });
    expect(result.success).toBe(true);
  });
});

describe("handleNavigate", () => {
  it("rejects when no route or url provided", async () => {
    const result = await handleNavigate({}, { iframeOrigin: "https://x" });
    expect(result.success).toBe(false);
    expect(result.error).toBe("missing_target");
  });
  it("invokes onNavigate callback when route is given", async () => {
    const onNavigate = vi.fn().mockResolvedValue(undefined);
    const result = await handleNavigate(
      { route: "/courses/123" },
      { iframeOrigin: "https://x", onNavigate },
    );
    expect(onNavigate).toHaveBeenCalledWith("/courses/123");
    expect(result.success).toBe(true);
  });
  it("rejects unsafe absolute URLs", async () => {
    const result = await handleNavigate(
      { url: "http://localhost/internal" },
      { iframeOrigin: "https://x" },
    );
    expect(result.success).toBe(false);
    expect(result.error).toBe("unsafe_url");
  });
});

describe("createBridge", () => {
  it("ignores messages from other origins", async () => {
    const onNavigate = vi.fn();
    makeBridge({ iframeOrigin: "https://wiii.example", onNavigate });
    const evil = new MessageEvent("message", {
      data: {
        type: "wiii:action-request",
        id: "1",
        action: "ui.navigate",
        params: { route: "/x" },
      },
      origin: "https://attacker.example",
    });
    window.dispatchEvent(evil);
    await Promise.resolve();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("dispatches and replies with matching id when origin matches", async () => {
    document.body.innerHTML = `<button data-wiii-id="login"></button>`;
    const replies: unknown[] = [];
    const fakeSource = {
      postMessage: (msg: unknown) => replies.push(msg),
    } as unknown as Window;
    makeBridge({ iframeOrigin: "https://wiii.example" });
    const event = new MessageEvent("message", {
      data: {
        type: "wiii:action-request",
        id: "req-42",
        action: "ui.highlight",
        params: { selector: '[data-wiii-id="login"]', message: "Đây" },
      },
      origin: "https://wiii.example",
    });
    Object.defineProperty(event, "source", { value: fakeSource });
    window.dispatchEvent(event);
    await new Promise((r) => setTimeout(r, 10));
    expect(replies).toHaveLength(1);
    const reply = replies[0] as { type: string; id: string; result: { success: boolean } };
    expect(reply.type).toBe("wiii:action-response");
    expect(reply.id).toBe("req-42");
    expect(reply.result.success).toBe(true);
  });

  it("replies with failure for unsupported action", async () => {
    const replies: unknown[] = [];
    const fakeSource = {
      postMessage: (msg: unknown) => replies.push(msg),
    } as unknown as Window;
    makeBridge({ iframeOrigin: "https://wiii.example" });
    const event = new MessageEvent("message", {
      data: {
        type: "wiii:action-request",
        id: "req-99",
        action: "ui.delete_universe",
        params: {},
      },
      origin: "https://wiii.example",
    });
    Object.defineProperty(event, "source", { value: fakeSource });
    window.dispatchEvent(event);
    await new Promise((r) => setTimeout(r, 5));
    const reply = replies[0] as { result: { success: boolean; error?: string } };
    expect(reply.result.success).toBe(false);
    expect(reply.result.error).toContain("unsupported_action");
  });
});
