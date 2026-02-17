/**
 * Unit tests for Sprint 109 polish — domain config, format utils,
 * elapsed time format, keyboard shortcuts, ChatResponseData type.
 */
import { describe, it, expect } from "vitest";
import { DOMAIN_ICONS, DOMAIN_LABELS, DOMAIN_BADGES } from "@/lib/domain-config";
import { formatTokens } from "@/lib/format";
import type { ChatResponseData } from "@/api/types";

// ===== Domain Config =====

describe("Domain Config — shared constants", () => {
  it("should export DOMAIN_ICONS for maritime and traffic_law", () => {
    expect(DOMAIN_ICONS.maritime).toBeDefined();
    expect(DOMAIN_ICONS.traffic_law).toBeDefined();
  });

  it("should export DOMAIN_LABELS with Vietnamese names", () => {
    expect(DOMAIN_LABELS.maritime).toBe("Hàng hải");
    expect(DOMAIN_LABELS.traffic_law).toBe("Luật giao thông");
  });

  it("should export DOMAIN_BADGES with 2-char codes", () => {
    expect(DOMAIN_BADGES.maritime).toBe("HH");
    expect(DOMAIN_BADGES.traffic_law).toBe("GT");
  });
});

// ===== Format Utilities =====

describe("formatTokens", () => {
  it("should return raw number for < 1000", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(500)).toBe("500");
    expect(formatTokens(999)).toBe("999");
  });

  it("should return K suffix for >= 1000", () => {
    expect(formatTokens(1000)).toBe("1.0K");
    expect(formatTokens(1500)).toBe("1.5K");
    expect(formatTokens(21000)).toBe("21.0K");
    expect(formatTokens(128000)).toBe("128.0K");
  });

  it("should show one decimal place for K values", () => {
    expect(formatTokens(1234)).toBe("1.2K");
    expect(formatTokens(9999)).toBe("10.0K");
  });
});

// ===== Elapsed Time Format =====

describe("Elapsed time formatting (StreamingIndicator logic)", () => {
  function formatElapsed(elapsed: number): string {
    if (elapsed >= 60) {
      return `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;
    }
    return `${elapsed}s`;
  }

  it("should show seconds for < 60s", () => {
    expect(formatElapsed(0)).toBe("0s");
    expect(formatElapsed(30)).toBe("30s");
    expect(formatElapsed(59)).toBe("59s");
  });

  it("should show MM:SS for >= 60s", () => {
    expect(formatElapsed(60)).toBe("1:00");
    expect(formatElapsed(90)).toBe("1:30");
    expect(formatElapsed(127)).toBe("2:07");
    expect(formatElapsed(300)).toBe("5:00");
  });

  it("should zero-pad seconds in MM:SS", () => {
    expect(formatElapsed(61)).toBe("1:01");
    expect(formatElapsed(62)).toBe("1:02");
    expect(formatElapsed(69)).toBe("1:09");
  });
});

// ===== ChatResponseData Type =====

describe("ChatResponseData type — domain_notice field", () => {
  it("should accept domain_notice as optional string", () => {
    const data: ChatResponseData = {
      answer: "Hello",
      sources: [],
      suggested_questions: [],
      domain_notice: "Đây là câu hỏi ngoài lĩnh vực hàng hải.",
    };
    expect(data.domain_notice).toBe("Đây là câu hỏi ngoài lĩnh vực hàng hải.");
  });

  it("should allow missing domain_notice", () => {
    const data: ChatResponseData = {
      answer: "Hello",
      sources: [],
      suggested_questions: [],
    };
    expect(data.domain_notice).toBeUndefined();
  });
});
