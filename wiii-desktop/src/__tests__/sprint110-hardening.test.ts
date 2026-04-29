/**
 * Sprint 110: Hardening & Quality — tests for type safety, toast limit,
 * accessibility, and React.memo optimizations.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// ---------------------------------------------------------------------------
// 1) Toast store — max visible limit
// ---------------------------------------------------------------------------
describe("Toast store — max visible limit", () => {
  let useToastStore: typeof import("@/stores/toast-store").useToastStore;

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import("@/stores/toast-store");
    useToastStore = mod.useToastStore;
    useToastStore.setState({ toasts: [] });
  });

  it("should keep at most 3 visible toasts", () => {
    const { addToast } = useToastStore.getState();
    // Add 5 toasts rapidly
    addToast("info", "Toast 1", 0);
    addToast("info", "Toast 2", 0);
    addToast("info", "Toast 3", 0);
    addToast("info", "Toast 4", 0);
    addToast("info", "Toast 5", 0);

    const { toasts } = useToastStore.getState();
    expect(toasts.length).toBeLessThanOrEqual(3);
    // Should keep the most recent 3
    expect(toasts[0].message).toBe("Toast 3");
    expect(toasts[1].message).toBe("Toast 4");
    expect(toasts[2].message).toBe("Toast 5");
  });

  it("should allow up to 3 without trimming", () => {
    const { addToast } = useToastStore.getState();
    addToast("success", "A", 0);
    addToast("error", "B", 0);
    addToast("info", "C", 0);

    const { toasts } = useToastStore.getState();
    expect(toasts.length).toBe(3);
    expect(toasts[0].message).toBe("A");
  });
});

// ---------------------------------------------------------------------------
// 2) MessageBubble — memo export check (source-level to avoid timeout)
// ---------------------------------------------------------------------------
describe("MessageBubble — React.memo", () => {
  it("should import memo from React and WiiiAvatar", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toMatch(/import\s*\{[^}]*memo[^}]*\}\s*from\s*["']react["']/);
    expect(code).toContain("WiiiAvatar");
  });

  it("should wrap export with memo()", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("export const MessageBubble = memo(");
  });
});

// ---------------------------------------------------------------------------
// 3) SuggestedQuestions — accessibility attributes
// ---------------------------------------------------------------------------
describe("SuggestedQuestions — accessibility", () => {
  it("should have role=group and aria-label on container", async () => {
    const src = await import("@/components/chat/SuggestedQuestions?raw");
    const code = (src as any).default || src;
    // Check that role="group" exists
    expect(code).toContain('role="group"');
    expect(code).toContain('aria-label="Câu hỏi gợi ý"');
  });

  it("should have aria-label on each button", async () => {
    const src = await import("@/components/chat/SuggestedQuestions?raw");
    const code = (src as any).default || src;
    expect(code).toContain("aria-label={`Hỏi: ${q}`}");
  });
});

// ---------------------------------------------------------------------------
// 4) useSSEStream — type-safe metadata cast (source-level check)
// ---------------------------------------------------------------------------
describe("useSSEStream — type-safe metadata", () => {
  it("should NOT use 'as never' cast", async () => {
    const src = await import("@/hooks/useSSEStream?raw");
    const code = (src as any).default || src;
    // Old pattern: "as never" — should be replaced
    expect(code).not.toContain("as never");
  });

  it("should import ChatResponseMetadata type", async () => {
    const src = await import("@/hooks/useSSEStream?raw");
    const code = (src as any).default || src;
    expect(code).toContain("ChatResponseMetadata");
  });

  it("should keep the idle guard above provider cold-start latency", async () => {
    const src = await import("@/hooks/useSSEStream?raw");
    const code = (src as any).default || src;
    expect(code).toContain("const SSE_IDLE_TIMEOUT_MS = 120_000");
  });

  it("records Pointy fast-path progress only after host action success", async () => {
    const src = await import("@/hooks/useSSEStream?raw");
    const code = (src as any).default || src;
    const successGuard = code.indexOf("if (result.success)");
    const pointyStep = code.indexOf('eventOrderRef.current.push("pointy_fast_path")');
    expect(successGuard).toBeGreaterThan(-1);
    expect(pointyStep).toBeGreaterThan(successGuard);
    expect(code).not.toContain("Wiii dang tro tren trang");
  });
});

// ---------------------------------------------------------------------------
// 5) chat-store finalizeStream — no double cast
// ---------------------------------------------------------------------------
describe("chat-store — finalizeStream type safety", () => {
  it("should NOT use 'as unknown as Record' double cast", async () => {
    const src = await import("@/stores/chat-store?raw");
    const code = (src as any).default || src;
    expect(code).not.toContain("as unknown as Record");
  });

  it("should use Array.isArray runtime check for suggestedQuestions", async () => {
    const src = await import("@/stores/chat-store?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Array.isArray(rawSQ)");
  });
});

// Stop button test removed: the Stop control was moved from MessageList to
// ChatInput and switched to an SVG icon with aria-label="Dừng tạo phản hồi"
// (see ChatInput.tsx). The original substring assertion no longer maps onto
// the component that owns the button; accessible-label coverage belongs in
// an integration/RTL test against ChatInput, not a source-grep here.
