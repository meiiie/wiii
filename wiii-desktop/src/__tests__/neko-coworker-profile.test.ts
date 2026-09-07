import { describe, expect, it } from "vitest";
import {
  DEFAULT_NEKO_COWORKER,
  LOCAL_WIII_OPERATOR_ID,
  coworkerWorkstationTitle,
  describeCoworkerSeat,
  localUserControlsSeat,
} from "@/neko-coworker/profile";

describe("AI coworker workstation identity", () => {
  it("keeps the coworker identity independent from a session or harness", () => {
    expect(coworkerWorkstationTitle(DEFAULT_NEKO_COWORKER)).toBe(
      "Máy tính công việc của Neko",
    );
    expect(DEFAULT_NEKO_COWORKER).not.toHaveProperty("harnessId");
    expect(DEFAULT_NEKO_COWORKER).not.toHaveProperty("sessionId");
    expect(LOCAL_WIII_OPERATOR_ID).toBe("user:wiii-desktop");
    expect(localUserControlsSeat("user_controlled")).toBe(true);
    expect(localUserControlsSeat("agent_controlled")).toBe(false);
  });

  it("describes input ownership without claiming control that does not exist", () => {
    expect(describeCoworkerSeat(DEFAULT_NEKO_COWORKER, "user_controlled", true)).toBe(
      "Bạn đang điều khiển máy của Neko",
    );
    expect(describeCoworkerSeat(DEFAULT_NEKO_COWORKER, "agent_controlled", false)).toBe(
      "Neko đang làm việc · Bạn đang quan sát",
    );
    expect(describeCoworkerSeat(DEFAULT_NEKO_COWORKER, "user_controlled", false)).toBe(
      "Một phiên người dùng khác đang điều khiển",
    );
    expect(describeCoworkerSeat(DEFAULT_NEKO_COWORKER, "available", false)).toBe(
      "Đang quan sát · Chưa có ai điều khiển",
    );
  });
});
