import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getGreeting,
  getTimeOfDay,
  getWelcomePlaceholder,
  getWiiiSubtitle,
} from "@/lib/greeting";

describe("Vietnamese greeting behavior", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("classifies every time-of-day boundary", () => {
    const cases = [
      [0, "evening"],
      [4, "evening"],
      [5, "morning"],
      [11, "morning"],
      [12, "afternoon"],
      [17, "afternoon"],
      [18, "evening"],
      [23, "evening"],
    ] as const;

    for (const [hour, expected] of cases) {
      expect(getTimeOfDay(hour), `hour ${hour}`).toBe(expected);
    }
  });

  it("uses the selected time bucket for greetings and placeholders", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);

    expect(getGreeting(undefined, 5)).toBe("Chào buổi sáng!");
    expect(getGreeting(undefined, 12)).toBe("Chào buổi chiều!");
    expect(getGreeting(undefined, 18)).toBe("Chào buổi tối!");
    expect(getWelcomePlaceholder(5)).toBe("Sáng nay mình tìm hiểu gì nhỉ?");
    expect(getWelcomePlaceholder(12)).toBe("Chiều nay mình cùng tìm hiểu nhé!");
    expect(getWelcomePlaceholder(18)).toBe("Tối nay mình cùng tìm hiểu nhé!");
  });

  it("personalizes real names but filters generic desktop identities", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);

    expect(getGreeting("Meiiie", 8)).toBe("Chào buổi sáng, Meiiie!");
    expect(getGreeting("  Meiiie  ", 8)).toBe("Chào buổi sáng, Meiiie!");
    for (const genericName of ["User", "desktop-user", "Desktop User", "anonymous", "guest"]) {
      expect(getGreeting(genericName, 8), genericName).toBe("Chào buổi sáng!");
    }
  });

  it("selects subtitle variants through a deterministic random contract", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    expect(getWiiiSubtitle()).toBe("Mình ở đây, sẵn sàng giúp bạn!");

    vi.mocked(Math.random).mockReturnValue(0.999);
    expect(getWiiiSubtitle()).toBe("Bạn cần gì, mình nghe đây!");
  });
});
