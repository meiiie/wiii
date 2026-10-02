import type { PermissionOption, PermissionRequest } from "../drivers/types";
import type { NekoSession } from "../stores/neko-session-store";

export type PermissionPreviewSession = Pick<NekoSession, "events" | "messages" | "runtime">;

export interface PermissionPreview {
  source: "activity" | "linked-tool" | "missing";
  toolName: string | null;
  title: string | null;
  operation: string | null;
  targets: Array<{ path: string; line?: number }>;
  detail: string | null;
  truncated: boolean;
}

const LIMITS = { name: 120, title: 300, path: 320, detail: 600, targets: 5 };
const OPERATIONS: Record<string, string> = {
  read: "Đọc tệp", create: "Tạo tệp", update: "Sửa tệp", delete: "Xoá tệp", move: "Di chuyển tệp",
};

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

const CONTROL_CHAR = /[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u2028-\u202E\u2060-\u206F\uFEFF]/u;

function formattedText(value: unknown, limit: number): { text: string | null; truncated: boolean } {
  if (typeof value !== "string") return { text: null, truncated: false };
  let text = "";
  let truncated = false;
  for (const char of value) {
    const visible = CONTROL_CHAR.test(char)
      ? "[U+" + char.codePointAt(0)!.toString(16).toUpperCase().padStart(4, "0") + "]"
      : char;
    if (text.length + visible.length > limit) { truncated = true; break; }
    text += visible;
  }
  text = text.trim();
  return { text: text ? text + (truncated ? "…" : "") : null, truncated };
}

export function permissionPreviewText(value: unknown, limit = LIMITS.title): string | null {
  return formattedText(value, limit).text;
}

export function permissionPreviewIsTruncated(value: unknown, limit = LIMITS.title): boolean {
  return formattedText(value, limit).truncated;
}

function missing(): PermissionPreview {
  return { source: "missing", toolName: null, title: null, operation: null, targets: [], detail: null, truncated: false };
}

/** Display facts only: IDs link evidence; titles and raw arguments never define targets. */
export function buildPermissionPreview(
  request: PermissionRequest,
  session?: PermissionPreviewSession,
): PermissionPreview {
  const activityId = request.activityId;
  const runtimeId = session?.runtime?.instanceId;
  if (!session || typeof activityId !== "string" || !activityId || activityId.length > 512
    || typeof runtimeId !== "string" || !runtimeId || !Array.isArray(session?.events)) return missing();

  let activity: Record<string, unknown> | null = null;
  let inputMessageId: string | null = null;
  let boundaryIndex = -1;
  const events = session.events;
  // Tool IDs are only unique within a turn. Never borrow a match from earlier history.
  for (let i = events.length - 1; i >= 0; i--) {
    const data = record(record(events[i])?.data);
    if (!data) continue;
    if (data.type === "model-input") {
      if (data.providerInstanceId !== runtimeId) return missing();
      inputMessageId = typeof data.messageId === "string" ? data.messageId : null;
      boundaryIndex = i;
      break;
    }
    if (data.type === "runtime-attached") {
      if (record(data.provider)?.instanceId !== runtimeId) return missing();
      boundaryIndex = i;
      break;
    }
    if (data.type === "runtime-detached") return missing();
    if (!activity && data.type === "workspace-activity" && data.activityId === activityId) activity = data;
  }
  if (boundaryIndex < 0) return missing();
  // A current turn alone cannot prove the provider was not replaced.
  let currentAttachment = false;
  for (let i = events.length - 1; i >= 0; i--) {
    const data = record(record(events[i])?.data);
    if (data?.type === "runtime-detached") return missing();
    if (data?.type === "runtime-attached") {
      currentAttachment = record(data.provider)?.instanceId === runtimeId;
      break;
    }
  }
  if (!currentAttachment) return missing();

  // ACP caches activity updates by ID. Reuse may carry old metadata forward.
  for (let i = 0; i < boundaryIndex; i++) {
    const data = record(record(events[i])?.data);
    if (data?.type === "workspace-activity" && data.activityId === activityId) return missing();
  }
  const messages = Array.isArray(session.messages) ? session.messages : [];
  let inputIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (record(messages[i])?.id === inputMessageId) { inputIndex = i; break; }
  }
  for (let i = 0; i < inputIndex; i++) {
    const blocks = record(messages[i])?.blocks;
    if (Array.isArray(blocks) && blocks.some((value) => {
      const block = record(value);
      return block?.type === "tool_execution" && block.id === activityId;
    })) return missing();
  }

  if (activity) {
    if (activity.status !== "pending" && activity.status !== "in_progress") return missing();
    const targets: PermissionPreview["targets"] = [];
    const locations = Array.isArray(activity.locations) ? activity.locations : [];
    let truncated = locations.length > LIMITS.targets;
    for (const location of locations.slice(0, LIMITS.targets)) {
      const item = record(location);
      const path = permissionPreviewText(item?.path, LIMITS.path);
      if (!path) continue;
      truncated ||= formattedText(item?.path, LIMITS.path).truncated;
      const line = typeof item?.line === "number" && Number.isSafeInteger(item.line) && item.line > 0
        ? item.line
        : undefined;
      targets.push({ path, ...(line ? { line } : {}) });
    }
    for (const [value, limit] of [[activity.toolName, LIMITS.name], [activity.title, LIMITS.title], [activity.detail, LIMITS.detail]] as const) {
      truncated ||= formattedText(value, limit).truncated;
    }
    return {
      source: "activity",
      toolName: permissionPreviewText(activity.toolName, LIMITS.name),
      title: permissionPreviewText(activity.title),
      operation: typeof activity.operation === "string" && Object.prototype.hasOwnProperty.call(OPERATIONS, activity.operation)
        ? OPERATIONS[activity.operation] : null,
      targets,
      detail: permissionPreviewText(activity.detail, LIMITS.detail),
      truncated,
    };
  }

  // Legacy tool blocks keep display names, not structured args or targets.
  // Only the assistant message following this exact current input is eligible.
  const assistant = record(messages[messages.length - 1]);
  const input = record(messages[messages.length - 2]);
  if (!inputMessageId || input?.role !== "user" || input.id !== inputMessageId
    || assistant?.role !== "assistant" || !Array.isArray(assistant.blocks)) return missing();
  for (const value of assistant.blocks.slice(-200)) {
    const block = record(value);
    if (block?.type !== "tool_execution" || block.id !== activityId) continue;
    const tool = record(block.tool);
    if (block.status !== "pending" || block.outcome || tool?.id !== activityId) return missing();
    const title = permissionPreviewText(tool.name);
    if (!title) return missing();
    return { ...missing(), source: "linked-tool", title, truncated: formattedText(tool.name, LIMITS.title).truncated };
  }
  return missing();
}

export function permissionOptionScope(kind: PermissionOption["kind"]): string {
  if (kind === "allow_once" || kind === "reject_once") return "Chỉ áp dụng cho yêu cầu này.";
  if (kind === "allow_always" || kind === "reject_always") {
    return "Lựa chọn lâu dài. Phạm vi áp dụng cụ thể chưa được agent cung cấp.";
  }
  return "Phạm vi áp dụng chưa được agent cung cấp.";
}
