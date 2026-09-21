import { describe, expect, it } from "vitest";
import {
  COWORKER_CHILL_SEPARATION_VI,
  coworkerGrantsCard,
  coworkerOpenProjectCard,
} from "@/neko-coworker/coworker-project-honesty";
import type { NekoProject } from "@/workbench/contracts";

const wiiiProject: NekoProject = {
  id: "proj-1",
  name: "wiii-real-linux-session",
  roots: [{ path: "/tmp/wiii-real-linux-session", name: "wiii-real-linux-session" }],
  preferredHarnessId: "neko",
  createdAt: 1,
  updatedAt: 1,
};

describe("coworker project honesty", () => {
  it("does not claim Không có when Wiii already has an open project folder", () => {
    const card = coworkerOpenProjectCard({
      environmentProjectName: null,
      environmentProjectPath: null,
      wiiiProjects: [wiiiProject],
    });
    expect(card.value).toBe("wiii-real-linux-session");
    expect(card.detail).toContain("/tmp/wiii-real-linux-session");
    expect(card.detail).toMatch(/chưa gắn vào máy Neko/);
    expect(card.needsCoworkerGrant).toBe(true);
    expect(card.value).not.toBe("Không có");
  });

  it("prefers coworker-mounted project when present", () => {
    const card = coworkerOpenProjectCard({
      environmentProjectName: "Mounted",
      environmentProjectPath: "/mnt/neko/Mounted",
      wiiiProjects: [wiiiProject],
    });
    expect(card).toEqual({
      value: "Mounted",
      detail: "/mnt/neko/Mounted",
      needsCoworkerGrant: false,
    });
  });

  it("keeps empty copy only when neither coworker nor Wiii has a project", () => {
    expect(coworkerOpenProjectCard({
      environmentProjectName: null,
      environmentProjectPath: null,
      wiiiProjects: [],
    })).toEqual({
      value: "Không có",
      detail: "Neko chưa nhận thư mục nào",
      needsCoworkerGrant: false,
    });
  });

  it("explains 0 coworker grants without erasing Wiii project presence", () => {
    const card = coworkerGrantsCard({ grantCount: 0, wiiiProjectCount: 1 });
    expect(card.value).toBe("0 quyền máy Neko");
    expect(card.detail).toMatch(/1 Project Wiii/);
    expect(card.detail).toMatch(/khác phiên Chill/);
    expect(card.needsCoworkerGrant).toBe(true);
  });

  it("does not invent auto-grant language", () => {
    expect(COWORKER_CHILL_SEPARATION_VI).toMatch(/không tự cấp quyền/i);
    expect(COWORKER_CHILL_SEPARATION_VI).toMatch(/Cấp quyền/);
    expect(COWORKER_CHILL_SEPARATION_VI.toLowerCase()).not.toContain("tự động cấp");
  });
});
