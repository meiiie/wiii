import type { PermissionRequest } from "../types";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

/** ACP request-local evidence only. Do not fill gaps from cached activities. */
export function acpPermissionPreview(value: unknown): PermissionRequest["toolPreview"] {
  const tool = record(value);
  if (!tool) return undefined;
  let budget = 16_000;
  let truncated = false;
  const bounded = (text: string, limit = budget): string => {
    const size = Math.min(limit, budget);
    truncated ||= text.length > size;
    let end = Math.min(text.length, size);
    // Avoid splitting a surrogate pair at the display boundary.
    if (end && /[\uD800-\uDBFF]/u.test(text[end - 1])) end--;
    budget -= end;
    return text.slice(0, end);
  };
  const toolName = typeof tool.name === "string" ? bounded(tool.name, 120) : undefined;
  const locations: NonNullable<PermissionRequest["toolPreview"]>["locations"] = [];
  if (Array.isArray(tool.locations)) {
    truncated ||= tool.locations.length > 5;
    for (const entry of tool.locations.slice(0, 5)) {
      const item = record(entry);
      if (typeof item?.path === "string") locations.push({ path: bounded(item.path, 320) });
    }
  }
  const changes: NonNullable<PermissionRequest["toolPreview"]>["changes"] = [];
  const add = (after: string, before?: string, path?: string) => {
    if (changes.length >= 5) { truncated = true; return; }
    const displayPath = path !== undefined ? bounded(path, 320) : undefined;
    // Reserve space for the proposed replacement, even when old text is huge.
    const displayBefore = before !== undefined ? bounded(before, Math.floor(budget / 2)) : undefined;
    const displayAfter = bounded(after);
    changes.push({ ...(displayPath !== undefined ? { path: displayPath } : {}),
      ...(displayBefore !== undefined ? { before: displayBefore } : {}), after: displayAfter,
      ...(before !== undefined && displayBefore!.length < before.length ? { beforeTruncated: true } : {}),
      ...(displayAfter.length < after.length ? { afterTruncated: true } : {}),
    });
  };
  // Standard ACP diff blocks take precedence over provider-specific rawInput.
  if (Array.isArray(tool.content)) {
    for (const entry of tool.content.slice(0, 100)) {
      const item = record(entry);
      if (item?.type === "diff" && typeof item.newText === "string") {
        add(item.newText, typeof item.oldText === "string" ? item.oldText : undefined,
          typeof item.path === "string" ? item.path : undefined);
      }
    }
    truncated ||= tool.content.length > 100;
  }
  const args = record(tool.rawInput);
  if (!changes.length && args) {
    if (toolName === "write_file" && typeof args.content === "string") add(args.content);
    if (toolName === "edit" && typeof args.old_string === "string" && typeof args.new_string === "string") {
      add(args.new_string, args.old_string);
    }
    if (toolName === "multi_edit" && Array.isArray(args.edits)) {
      truncated ||= args.edits.length > 5;
      for (const entry of args.edits.slice(0, 5)) {
        const edit = record(entry);
        if (typeof edit?.old_string === "string" && typeof edit.new_string === "string") add(edit.new_string, edit.old_string);
      }
    }
  }
  return { toolName, locations, changes, truncated };
}
