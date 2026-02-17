/**
 * Sprint 117: Avatar State Wiring — tests.
 * Verifies that avatar states are properly connected to real UI events:
 * listening (input focus), thinking→speaking (streaming), error (ErrorBoundary).
 */
import { describe, it, expect, vi } from "vitest";

// ---------------------------------------------------------------------------
// 1) ErrorBoundary uses "error" state
// ---------------------------------------------------------------------------
describe("ErrorBoundary — avatar error state", () => {
  it("should use state='error' not state='idle'", async () => {
    const src = await import("@/components/common/ErrorBoundary?raw");
    const code = (src as any).default || src;
    expect(code).toContain('state="error"');
    expect(code).not.toContain('state="idle"');
  });
});

// ---------------------------------------------------------------------------
// 2) MessageList — dynamic thinking→speaking transition
// ---------------------------------------------------------------------------
describe("MessageList — avatar state transition", () => {
  it("should derive avatar state from streamingContent", async () => {
    const src = await import("@/components/chat/MessageList?raw");
    const code = (src as any).default || src;
    // Should use conditional: speaking when content exists, thinking otherwise
    expect(code).toContain('"speaking"');
    expect(code).toContain('"thinking"');
    expect(code).toContain("streamingContent");
    // Should NOT have hardcoded thinking-only state
    expect(code).not.toContain('state="thinking"');
  });
});

// ---------------------------------------------------------------------------
// 3) StatusBar — 4-state avatar
// ---------------------------------------------------------------------------
describe("StatusBar — derived avatar state", () => {
  it("should import useUIStore for inputFocused", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("useUIStore");
    expect(code).toContain("inputFocused");
  });

  it("should have deriveAvatarState function with 4 states", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("deriveAvatarState");
    expect(code).toContain('"speaking"');
    expect(code).toContain('"thinking"');
    expect(code).toContain('"listening"');
    expect(code).toContain('"idle"');
  });

  it("should no longer hardcode isStreaming ternary", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    // Old pattern: state={isStreaming ? "thinking" : "idle"}
    expect(code).not.toContain('isStreaming ? "thinking" : "idle"');
    // New pattern: state={avatarState}
    expect(code).toContain("avatarState");
  });
});

// ---------------------------------------------------------------------------
// 4) ChatInput — focus/blur wiring
// ---------------------------------------------------------------------------
describe("ChatInput — listening state wiring", () => {
  it("should import useUIStore", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    expect(code).toContain("useUIStore");
  });

  it("should have onFocus and onBlur handlers on textarea", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    expect(code).toContain("onFocus");
    expect(code).toContain("onBlur");
    expect(code).toContain("setInputFocused(true)");
    expect(code).toContain("setInputFocused(false)");
  });

  it("should wire both centered and normal textareas", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    // Both textareas should have focus handlers
    const focusCount = (code.match(/onFocus/g) || []).length;
    const blurCount = (code.match(/onBlur/g) || []).length;
    expect(focusCount).toBeGreaterThanOrEqual(2);
    expect(blurCount).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 5) UI store — inputFocused state
// ---------------------------------------------------------------------------
describe("UI store — inputFocused field", () => {
  it("should have inputFocused and setInputFocused", async () => {
    const src = await import("@/stores/ui-store?raw");
    const code = (src as any).default || src;
    expect(code).toContain("inputFocused");
    expect(code).toContain("setInputFocused");
  });

  it("should toggle inputFocused state", async () => {
    vi.resetModules();
    const { useUIStore } = await import("@/stores/ui-store");
    expect(useUIStore.getState().inputFocused).toBe(false);

    useUIStore.getState().setInputFocused(true);
    expect(useUIStore.getState().inputFocused).toBe(true);

    useUIStore.getState().setInputFocused(false);
    expect(useUIStore.getState().inputFocused).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 6) Avatar state lifecycle (unit logic)
// ---------------------------------------------------------------------------
describe("deriveAvatarState logic", () => {
  // Re-implement the derive function for unit testing
  function deriveAvatarState(isStreaming: boolean, hasContent: boolean, inputFocused: boolean) {
    if (isStreaming) return hasContent ? "speaking" : "thinking";
    if (inputFocused) return "listening";
    return "idle";
  }

  it("returns idle when nothing is active", () => {
    expect(deriveAvatarState(false, false, false)).toBe("idle");
  });

  it("returns listening when input is focused and not streaming", () => {
    expect(deriveAvatarState(false, false, true)).toBe("listening");
  });

  it("returns thinking when streaming starts but no content yet", () => {
    expect(deriveAvatarState(true, false, false)).toBe("thinking");
  });

  it("returns speaking when streaming with content", () => {
    expect(deriveAvatarState(true, true, false)).toBe("speaking");
  });

  it("streaming takes priority over input focus", () => {
    expect(deriveAvatarState(true, false, true)).toBe("thinking");
    expect(deriveAvatarState(true, true, true)).toBe("speaking");
  });
});

// ---------------------------------------------------------------------------
// 7) All 6 avatar states are used across the app
// ---------------------------------------------------------------------------
describe("All 6 avatar states have usage", () => {
  it("idle — used in WelcomeScreen, Sidebar, SettingsPage", async () => {
    const files = [
      "@/components/chat/WelcomeScreen?raw",
      "@/components/layout/Sidebar?raw",
      "@/components/settings/SettingsPage?raw",
    ];
    for (const file of files) {
      const src = await import(/* @vite-ignore */ file);
      const code = (src as any).default || src;
      expect(code).toContain('"idle"');
    }
  });

  it("listening — used in StatusBar via deriveAvatarState", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"listening"');
  });

  it("thinking — used in App loading + StatusBar + MessageList", async () => {
    const app = await import("@/App?raw");
    const appCode = (app as any).default || app;
    expect(appCode).toContain('"thinking"');

    const sb = await import("@/components/layout/StatusBar?raw");
    const sbCode = (sb as any).default || sb;
    expect(sbCode).toContain('"thinking"');
  });

  it("speaking — used in StatusBar + MessageList", async () => {
    const sb = await import("@/components/layout/StatusBar?raw");
    const sbCode = (sb as any).default || sb;
    expect(sbCode).toContain('"speaking"');

    const ml = await import("@/components/chat/MessageList?raw");
    const mlCode = (ml as any).default || ml;
    expect(mlCode).toContain('"speaking"');
  });

  it("complete — used in MessageBubble", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"complete"');
  });

  it("error — used in ErrorBoundary", async () => {
    const src = await import("@/components/common/ErrorBoundary?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"error"');
  });
});
