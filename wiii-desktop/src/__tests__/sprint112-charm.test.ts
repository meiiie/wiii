/**
 * Sprint 112: Phase 2 Charm — tests for micro-interactions, suggestion labels,
 * welcome-back toast, StatusBar presence, dead CSS cleanup, DomainSelector spring.
 */
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// 1) SuggestedQuestions — "Mình gợi ý:" label
// ---------------------------------------------------------------------------
describe("SuggestedQuestions — suggestion label", () => {
  it("should have 'Mình gợi ý:' label above pills", async () => {
    const src = await import("@/components/chat/SuggestedQuestions?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mình gợi ý:");
  });
});

// ---------------------------------------------------------------------------
// 2) ChatView — welcome-back toast on conversation switch
// ---------------------------------------------------------------------------
describe("ChatView — welcome-back toast", () => {
  it("should track previous conversation ID with useRef", async () => {
    const src = await import("@/components/chat/ChatView?raw");
    const code = (src as any).default || src;
    expect(code).toContain("prevConvIdRef");
    expect(code).toContain("useRef");
  });

  it("should show welcome-back message when switching conversations", async () => {
    const src = await import("@/components/chat/ChatView?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Tiếp tục nào! Mình nhớ cuộc trò chuyện này.");
  });
});

// ---------------------------------------------------------------------------
// 3) MessageBubble — motion.button micro-interactions
// ---------------------------------------------------------------------------
describe("MessageActions — hover micro-interactions", () => {
  it("should use motion.button instead of plain button for actions", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    // MessageActions should have motion.button elements
    expect(code).toContain("motion.button");
    expect(code).toContain("whileHover");
    expect(code).toContain("whileTap");
  });

  it("should have scale animations on hover/tap", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("scale: 1.15");
    expect(code).toContain("scale: 0.9");
  });

  it("should have directional lift on thumbs (up lifts, down pushes)", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("y: -2");
    expect(code).toContain("y: 2");
  });

  it("should have rotate on regenerate button hover", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("rotate: 15");
  });
});

// ---------------------------------------------------------------------------
// 4) StatusBar — Wiii mini-avatar
// ---------------------------------------------------------------------------
describe("StatusBar — Wiii presence", () => {
  it("should import and render WiiiAvatar", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    expect(code).toContain("size={14}");
  });

  it("should derive avatar state from streaming + input focus", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    // Sprint 117: 4-state derived avatar (idle/listening/thinking/speaking)
    expect(code).toContain("deriveAvatarState");
    expect(code).toContain("avatarState");
  });

  it("should have animated context badge with pulse for warning states", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("motion.button");
    expect(code).toContain("shouldPulse");
  });
});

// ---------------------------------------------------------------------------
// 5) Dead CSS cleanup — welcome-sparkle removed from WelcomeScreen source
// ---------------------------------------------------------------------------
describe("WelcomeScreen — dead CSS cleanup", () => {
  it("should NOT reference welcome-sparkle class", async () => {
    const src = await import("@/components/chat/WelcomeScreen?raw");
    const code = (src as any).default || src;
    expect(code).not.toContain("welcome-sparkle");
  });

  it("should NOT reference SparkleIcon", async () => {
    const src = await import("@/components/chat/WelcomeScreen?raw");
    const code = (src as any).default || src;
    expect(code).not.toContain("SparkleIcon");
  });
});

// ---------------------------------------------------------------------------
// 6) DomainSelector — spring animation on caret
// ---------------------------------------------------------------------------
describe("DomainSelector — spring animation", () => {
  it("should use motion.span for caret with spring transition", async () => {
    const src = await import("@/components/chat/DomainSelector?raw");
    const code = (src as any).default || src;
    expect(code).toContain("motion.span");
    expect(code).toContain('"spring"');
    expect(code).toContain("stiffness");
    expect(code).toContain("damping");
  });

  it("should not use CSS transition-transform for caret rotation", async () => {
    const src = await import("@/components/chat/DomainSelector?raw");
    const code = (src as any).default || src;
    // Old pattern was: className with transition-transform + rotate-180
    expect(code).not.toContain("transition-transform");
  });
});

// ---------------------------------------------------------------------------
// 7) MessageBubble — feedback persistence
// ---------------------------------------------------------------------------
describe("MessageBubble — feedback integration", () => {
  it("should import submitFeedback and use persisted feedback from message", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("submitFeedback");
    expect(code).toContain("message.feedback");
  });
});
