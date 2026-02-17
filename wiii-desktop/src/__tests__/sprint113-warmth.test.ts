/**
 * Sprint 113: Phase 3 Warmth — tests for settings personality, error states,
 * sidebar warmth, toast messages, time-aware placeholders.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// 1) Settings — Wiii personality
// ---------------------------------------------------------------------------
describe("Settings — Wiii personality", () => {
  it("should have WiiiAvatar in header", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    expect(code).toContain("Cài đặt cho Wiii");
  });

  it("should have warm reset confirm dialog", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii sẽ quên bạn?");
    expect(code).toContain("Quên tất cả");
    // Old cold label should be gone
    expect(code).not.toContain("Khôi phục mặc định");
  });

  it("should have warm field hints in User tab", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Bảo mình tên bạn để nhớ nhé");
    expect(code).toContain('placeholder="Bạn tên gì?"');
  });

  it("should have warm memory subtitle", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mình ghi nhớ để hiểu bạn hơn");
    expect(code).toContain("Mình chưa nhớ gì về bạn");
  });

  it("should have warm context tab header", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mình đang theo dõi cuộc trò chuyện này");
  });

  it("should have FieldGroup with hint prop", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("hint?:");
    expect(code).toContain("{hint && (");
  });
});

// ---------------------------------------------------------------------------
// 2) Settings — Wiii toast messages
// ---------------------------------------------------------------------------
describe("Settings — warm toast messages", () => {
  it("should use Wiii voice in connection save toast", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii ghi nhớ cài đặt rồi!");
    expect(code).not.toContain('"Đã lưu cài đặt kết nối"');
  });

  it("should use Wiii voice in test connection result", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii nghe thấy bạn rồi!");
    expect(code).not.toContain('"Kết nối thành công!"');
  });

  it("should use Wiii voice in memory operations", async () => {
    const src = await import("@/components/settings/SettingsPage?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii quên hết rồi, bắt đầu lại nha!");
    expect(code).toContain("Wiii đã quên điều này");
  });
});

// ---------------------------------------------------------------------------
// 3) ErrorBoundary — Wiii avatar
// ---------------------------------------------------------------------------
describe("ErrorBoundary — Wiii avatar", () => {
  it("should use WiiiAvatar instead of AlertTriangle", async () => {
    const src = await import("@/components/common/ErrorBoundary?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    // AlertTriangle should not be imported
    expect(code).not.toContain("AlertTriangle");
  });
});

// ---------------------------------------------------------------------------
// 4) Sidebar — warm actions
// ---------------------------------------------------------------------------
describe("Sidebar — warm personality", () => {
  it("should use emotional delete dialog", async () => {
    const src = await import("@/components/layout/Sidebar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Quên cuộc trò chuyện này?");
    expect(code).toContain("Wiii sẽ quên cuộc trò chuyện này");
    expect(code).toContain('"Quên đi"');
    expect(code).toContain('"Thôi, giữ lại"');
  });

  it("should have warm rename and delete tooltips", async () => {
    const src = await import("@/components/layout/Sidebar?raw");
    const code = (src as any).default || src;
    expect(code).toContain('title="Đặt tên mới"');
    expect(code).toContain('title="Quên cuộc trò chuyện này"');
  });

  it("should have WiiiAvatar in empty state", async () => {
    const src = await import("@/components/layout/Sidebar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    // WiiiAvatar should appear in empty state (when no search)
    expect(code).toContain("!searchQuery && <WiiiAvatar");
  });

  it("should have warm toast messages", async () => {
    const src = await import("@/components/layout/Sidebar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii đã quên cuộc trò chuyện này");
    expect(code).toContain("Wiii nhớ tên mới rồi!");
  });
});

// ---------------------------------------------------------------------------
// 5) ChatView — warm compaction banner
// ---------------------------------------------------------------------------
describe("ChatView — warm compaction", () => {
  it("should have warm compaction message", async () => {
    const src = await import("@/components/chat/ChatView?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mình cần tóm tắt lại cuộc trò chuyện");
    expect(code).toContain("Wiii đã tóm tắt xong");
  });
});

// ---------------------------------------------------------------------------
// 6) ChatInput — time-aware welcome placeholder
// ---------------------------------------------------------------------------
describe("ChatInput — time-aware placeholder", () => {
  it("should import getWelcomePlaceholder", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    expect(code).toContain("getWelcomePlaceholder");
    expect(code).toContain("welcomePlaceholder");
  });

  it("should use dynamic placeholder in centered mode", async () => {
    const src = await import("@/components/chat/ChatInput?raw");
    const code = (src as any).default || src;
    // Should use variable, not hardcoded string
    expect(code).toContain("placeholder={welcomePlaceholder}");
    expect(code).not.toContain('placeholder="Hôm nay mình tìm hiểu gì nhỉ?"');
  });
});

// ---------------------------------------------------------------------------
// 7) greeting.ts — getWelcomePlaceholder
// ---------------------------------------------------------------------------
describe("getWelcomePlaceholder", () => {
  let getWelcomePlaceholder: typeof import("@/lib/greeting").getWelcomePlaceholder;

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import("@/lib/greeting");
    getWelcomePlaceholder = mod.getWelcomePlaceholder;
  });

  it("should return morning variants for morning hours", () => {
    const result = getWelcomePlaceholder(8);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("should return afternoon variants for afternoon hours", () => {
    const result = getWelcomePlaceholder(14);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("should return evening variants for evening hours", () => {
    const result = getWelcomePlaceholder(21);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("should return varied results (randomness)", () => {
    const results = new Set<string>();
    for (let i = 0; i < 30; i++) {
      results.add(getWelcomePlaceholder(10));
    }
    // Should have at least 2 variants
    expect(results.size).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 8) ContextPanel — warm toasts
// ---------------------------------------------------------------------------
describe("ContextPanel — warm toasts", () => {
  it("should use Wiii voice in toast messages", async () => {
    const src = await import("@/components/layout/ContextPanel?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Wiii tóm tắt xong rồi!");
    expect(code).toContain("Wiii quên cuộc trò chuyện này rồi");
  });
});

// ---------------------------------------------------------------------------
// 9) MessageBubble — warm copy toast
// ---------------------------------------------------------------------------
describe("MessageBubble — warm copy toast", () => {
  it("should have warm copy success message", async () => {
    const src = await import("@/components/chat/MessageBubble?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Đã sao chép tin nhắn!");
  });
});
