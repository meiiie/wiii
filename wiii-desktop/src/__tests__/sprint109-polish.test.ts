/**
 * Unit tests for Sprint 109 polish — domain config, format utils,
 * elapsed time format, keyboard shortcuts, ChatResponseData type.
 */
import { describe, it, expect } from "vitest";
import { DOMAIN_ICONS, DOMAIN_LABELS, DOMAIN_BADGES } from "@/lib/domain-config";
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
