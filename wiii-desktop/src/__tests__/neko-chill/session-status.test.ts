import { describe, expect, it } from "vitest";
import {
  providerProcessExitDetail,
  sessionHasVisibleModelOutput,
} from "@/neko-chill/session-status";
import type { NekoSessionEvent } from "@/neko-chill/session-events";
import type { NekoMessage } from "@/neko-chill/stores/neko-session-store";

describe("providerProcessExitDetail", () => {
  it("distinguishes signal death (null) from clean exit 0", () => {
    expect(providerProcessExitDetail(null)).toContain("tín hiệu");
    expect(providerProcessExitDetail(null)).toContain("không có mã thoát");
    expect(providerProcessExitDetail(0)).toContain("mã 0");
    expect(providerProcessExitDetail(0)).not.toContain("tín hiệu");
  });

  it("keeps nonzero exit codes explicit", () => {
    expect(providerProcessExitDetail(1)).toContain("mã lỗi 1");
    expect(providerProcessExitDetail(137)).toContain("mã lỗi 137");
  });

  it("appends empty-reply honesty when the turn produced no model output", () => {
    expect(providerProcessExitDetail(null, { emptyModelReply: true })).toContain(
      "Chưa có phản hồi từ model",
    );
    expect(providerProcessExitDetail(0, { emptyModelReply: false })).not.toContain(
      "Chưa có phản hồi từ model",
    );
  });
});

describe("sessionHasVisibleModelOutput", () => {
  it("is false for empty assistant shells", () => {
    const messages: NekoMessage[] = [
      { id: "u", role: "user", text: "hi" },
      { id: "a", role: "assistant", blocks: [] },
    ];
    expect(sessionHasVisibleModelOutput(messages)).toBe(false);
  });

  it("detects answer text, tool blocks, and workspace activity events", () => {
    expect(
      sessionHasVisibleModelOutput([
        { id: "a", role: "assistant", blocks: [{ type: "answer", id: "1", content: "xin chào" }] },
      ]),
    ).toBe(true);
    expect(
      sessionHasVisibleModelOutput([
        {
          id: "a",
          role: "assistant",
          blocks: [
            {
              type: "tool_execution",
              id: "t",
              status: "completed",
              tool: { id: "t", name: "write_file", status: "completed" },
            },
          ],
        },
      ]),
    ).toBe(true);
    const events = [
      {
        eventId: "e",
        seq: 1,
        at: 1,
        v: 1,
        visibility: "model",
        data: {
          type: "workspace-activity",
          activityId: "a1",
          title: "Write",
          status: "completed",
          operation: "update",
          toolName: "write_file",
          locations: [],
        },
      },
    ] as NekoSessionEvent[];
    expect(sessionHasVisibleModelOutput([{ id: "a", role: "assistant", blocks: [] }], events)).toBe(
      true,
    );
  });
});
