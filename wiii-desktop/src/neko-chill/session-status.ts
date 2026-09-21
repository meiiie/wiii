import type { ContentBlock } from "@/api/types";
import type { NekoSessionEvent } from "./session-events";
import type { NekoMessage, NekoSessionStatus } from "./stores/neko-session-store";

export const NEKO_SESSION_STATUS_LABELS = {
  connecting: "đang kết nối",
  stopping: "đang dừng",
  dispatching: "đang lưu & gửi",
  idle: "sẵn sàng",
  streaming: "đang làm việc",
  exited: "runtime đã dừng",
  error: "có lỗi",
} satisfies Record<NekoSessionStatus, string>;

/**
 * Honest VI banner for provider process exit.
 *
 * Unix signal death reports `code === null` (not 0). Collapsing null with 0 to
 * bare "Agent đã thoát." hid the TURN2 empty-transcript signal kill.
 */
export function providerProcessExitDetail(
  code: number | null,
  options?: { emptyModelReply?: boolean },
): string {
  const base =
    code === null
      ? "Agent đã bị dừng bởi tín hiệu hệ thống (không có mã thoát)."
      : code === 0
        ? "Agent đã thoát sạch (mã 0)."
        : `Agent thoát với mã lỗi ${code}.`;
  if (options?.emptyModelReply) {
    return `${base} Chưa có phản hồi từ model trong lượt này.`;
  }
  return base;
}

/** True when the transcript shows any assistant text, thinking, tool, or workspace activity. */
export function sessionHasVisibleModelOutput(
  messages: NekoMessage[],
  events: NekoSessionEvent[] = [],
): boolean {
  for (const message of messages) {
    if (message.role !== "assistant") continue;
    if (message.text?.trim()) return true;
    if ((message.blocks ?? []).some(blockHasVisibleModelOutput)) return true;
  }
  return events.some((event) => event.data.type === "workspace-activity");
}

function blockHasVisibleModelOutput(block: ContentBlock): boolean {
  switch (block.type) {
    case "answer":
    case "thinking":
      return Boolean(block.content?.trim());
    case "tool_execution":
      return true;
    default:
      return false;
  }
}
