/**
 * Sprint 114: Phase 4 Final Polish — keyboard hints, sources panel,
 * context panel header, confirm dialog active scale, settings reset title.
 */
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// 1) ChatInput — warm keyboard hints
// ---------------------------------------------------------------------------
describe("ChatInput — keyboard hints", () => {
  it("should have warm keyboard shortcut hints", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Enter gửi");
    // Should NOT have old cold hints
    expect(code).not.toContain("Enter để gửi");
  });
});

// ---------------------------------------------------------------------------
// 2) SourcesPanel — warm empty state
// ---------------------------------------------------------------------------
describe("SourcesPanel — warm empty state", () => {
  it("should have warm empty message", async () => {
    const src = await import("@/components/layout/SourcesPanel?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mình chưa tìm được nguồn");
    expect(code).not.toContain("Chưa có nguồn tham khảo.");
  });
});

// ---------------------------------------------------------------------------
// 3) ContextPanel — Vietnamese header
// ---------------------------------------------------------------------------
describe("ContextPanel — Vietnamese header", () => {
  it("should use Vietnamese header instead of English", async () => {
    const src = await import("@/components/layout/ContextPanel?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Bộ nhớ hội thoại");
    expect(code).not.toContain('"Context Window"');
  });
});

// ---------------------------------------------------------------------------
// 4) ConfirmDialog — active scale on buttons
// ---------------------------------------------------------------------------
describe("ConfirmDialog — button polish", () => {
  it("should have active:scale on both buttons", async () => {
    const src = await import("@/components/common/ConfirmDialog?raw");
    const code = (src as any).default || src;
    // Both confirm and cancel buttons should have active:scale
    const matches = code.match(/active:scale-\[0\.98\]/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 5) Settings reset — personal title
// ---------------------------------------------------------------------------
describe("Settings reset — personal title", () => {
  it("should use personal reset title", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii sẽ quên bạn?");
  });
});
