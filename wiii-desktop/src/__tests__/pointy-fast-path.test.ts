import { describe, expect, it } from "vitest";
import type { HostContext } from "@/stores/host-context-store";
import {
  buildPointyFastPathAction,
  getPointyTargetsFromContext,
  normalizePointyText,
} from "@/lib/pointy-fast-path";

function makeHostContext(targets: unknown[]): HostContext {
  return {
    host_type: "lms",
    page: {
      type: "course_list",
      title: "Khoa hoc cua toi",
      metadata: {
        available_targets: targets,
      },
    },
  };
}

describe("pointy fast path", () => {
  it("normalizes Vietnamese UI prompts for local matching", () => {
    expect(normalizePointyText("Wiii oi, nut Kham pha khoa hoc o dau?")).toContain(
      "kham pha khoa hoc o dau",
    );
    expect(normalizePointyText("Wiii ơi, Khám phá khóa học ở đâu?")).toContain(
      "kham pha khoa hoc o dau",
    );
  });

  it("extracts valid Pointy targets from host context metadata", () => {
    const ctx = makeHostContext([
      { id: "browse-courses", selector: "[data-wiii-id=\"browse-courses\"]", label: "Kham pha" },
      { id: "", selector: "#bad" },
      "noise",
    ]);

    expect(getPointyTargetsFromContext(ctx)).toEqual([
      expect.objectContaining({ id: "browse-courses", label: "Kham pha" }),
    ]);
  });

  it("highlights the matching target immediately for where-is prompts", () => {
    const ctx = makeHostContext([
      {
        id: "browse-courses",
        selector: "[data-wiii-id=\"browse-courses\"]",
        label: "Kham pha khoa hoc",
        click_safe: true,
      },
    ]);

    const action = buildPointyFastPathAction("Wiii oi, nut Kham pha khoa hoc o dau?", ctx);

    expect(action).toMatchObject({
      action: "ui.highlight",
      target: expect.objectContaining({ id: "browse-courses" }),
      params: expect.objectContaining({ selector: "browse-courses" }),
      reason: "locate",
    });
  });

  it("highlights accented where-is prompts even when the user does not say button", () => {
    const ctx = makeHostContext([
      {
        id: "browse-courses-link",
        selector: "[data-wiii-id=\"browse-courses-link\"]",
        label: "Khám phá khóa học",
        click_safe: true,
      },
    ]);

    const action = buildPointyFastPathAction("Wiii ơi, Khám phá khóa học ở đâu?", ctx);

    expect(action).toMatchObject({
      action: "ui.highlight",
      target: expect.objectContaining({ id: "browse-courses-link" }),
      params: expect.objectContaining({ selector: "browse-courses-link" }),
      reason: "locate",
    });
  });

  it("clicks only explicitly safe navigation targets for open prompts", () => {
    const ctx = makeHostContext([
      {
        id: "browse-courses-link",
        selector: "[data-wiii-id=\"browse-courses-link\"]",
        label: "Kham pha khoa hoc",
        click_safe: true,
        click_kind: "navigation",
      },
    ]);

    const action = buildPointyFastPathAction("Wiii mo Kham pha khoa hoc giup toi", ctx);

    expect(action).toMatchObject({
      action: "ui.click",
      params: expect.objectContaining({ selector: "browse-courses-link" }),
      reason: "click",
    });
  });

  it("demotes unsafe click intents to highlight instead of clicking", () => {
    const ctx = makeHostContext([
      {
        id: "submit-quiz",
        selector: "[data-wiii-id=\"submit-quiz\"]",
        label: "Nop bai",
        click_safe: false,
      },
    ]);

    const action = buildPointyFastPathAction("Wiii bam nut Nop bai giup toi", ctx);

    expect(action).toMatchObject({
      action: "ui.highlight",
      reason: "unsafe_click_demoted",
    });
  });

  it("does nothing when no visible target matches", () => {
    const ctx = makeHostContext([
      { id: "profile-link", selector: "[data-wiii-id=\"profile-link\"]", label: "Ho so" },
    ]);

    expect(buildPointyFastPathAction("Wiii oi hom nay sao roi?", ctx)).toBeNull();
  });
});
