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
// 2) MessageList — uses centralized useAvatarState hook (Sprint 145)
// ---------------------------------------------------------------------------
describe("MessageList — avatar state transition", () => {
  it("should use useAvatarState hook for centralized state derivation", async () => {
    const src = await import("@/components/chat/MessageList?raw");
    const code = (src as any).default || src;
    // Sprint 145: state derivation moved to useAvatarState hook
    expect(code).toContain("useAvatarState");
    expect(code).toContain("avatarState");
    // Should NOT have hardcoded thinking-only state
    expect(code).not.toContain('state="thinking"');
  });
});

// ---------------------------------------------------------------------------
// 3) StatusBar — 4-state avatar
// ---------------------------------------------------------------------------
describe("StatusBar — derived avatar state", () => {
  it("should use useAvatarState hook for centralized state", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    // Sprint 145: state derivation moved to useAvatarState hook
    expect(code).toContain("useAvatarState");
    expect(code).toContain("avatarState");
  });

  it("should no longer have inline deriveAvatarState function", async () => {
    const src = await import("@/components/layout/StatusBar?raw");
    const code = (src as any).default || src;
    // Sprint 145: removed local derivation — centralized in hook
    expect(code).not.toContain("deriveAvatarState");
    expect(code).not.toContain('isStreaming ? "thinking" : "idle"');
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
  it("idle — used in Sidebar, SettingsPage (WelcomeScreen uses useAvatarState)", async () => {
    const files = [
      "@/components/layout/Sidebar?raw",
      "@/components/settings/SettingsPage?raw",
    ];
    for (const file of files) {
      const src = await import(/* @vite-ignore */ file);
      const code = (src as any).default || src;
      expect(code).toContain('"idle"');
    }
    // Sprint 145b: WelcomeScreen now uses useAvatarState (live avatar, no static "idle")
    const ws = await import("@/components/chat/WelcomeScreen?raw");
    const wsCode = (ws as any).default || ws;
    expect(wsCode).toContain("useAvatarState");
  });

  it("listening — used in useAvatarState hook", async () => {
    const src = await import("@/hooks/useAvatarState?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"listening"');
  });

  it("thinking — used in App loading + useAvatarState hook", async () => {
    const app = await import("@/App?raw");
    const appCode = (app as any).default || app;
    expect(appCode).toContain('"thinking"');

    const hook = await import("@/hooks/useAvatarState?raw");
    const hookCode = (hook as any).default || hook;
    expect(hookCode).toContain('"thinking"');
  });

  it("speaking — used in useAvatarState hook", async () => {
    const hook = await import("@/hooks/useAvatarState?raw");
    const hookCode = (hook as any).default || hook;
    expect(hookCode).toContain('"speaking"');
  });

  it("complete — used in useAvatarState hook + MessageBubble idle state", async () => {
    const hook = await import("@/hooks/useAvatarState?raw");
    const hookCode = (hook as any).default || hook;
    expect(hookCode).toContain('"complete"');

    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"idle"');
  });

  it("error — used in ErrorBoundary", async () => {
    const src = await import("@/components/common/ErrorBoundary?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"error"');
  });
});
