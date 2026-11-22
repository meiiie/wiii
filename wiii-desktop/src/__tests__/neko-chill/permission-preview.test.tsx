import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PermissionCard } from "@/neko-chill/components/PermissionCard";
import { acpPermissionPreview } from "@/neko-chill/drivers/acp/permission-preview";
import {
  buildPermissionPreview,
  type PermissionPreviewSession,
} from "@/neko-chill/components/permission-preview";
import type { PermissionRequest } from "@/neko-chill/drivers/types";
import type { NekoSessionEvent } from "@/neko-chill/session-events";

const runtime: NonNullable<PermissionPreviewSession["runtime"]> = {
  sessionId: "session-a", providerId: "neko", instanceId: "runtime-a", kind: "acp",
  backendSessionId: null, capabilities: ["prompt", "permission-resolution"],
  contextContinuity: "process", workspaceIsolation: "advisory",
};
const request: PermissionRequest = {
  requestId: "permission-a", title: "Agent muốn sửa cấu hình", activityId: "tool-a",
  options: [
    { optionId: "opaque-allow", label: "Cho phép", kind: "allow_once" },
    { optionId: "opaque-deny", label: "Từ chối", kind: "reject_once" },
  ],
};

function event(data: NekoSessionEvent["data"], seq: number): NekoSessionEvent {
  return { v: 1, seq, at: seq, visibility: "runtime", data };
}
function input(messageId = "input-a", instanceId = runtime.instanceId): NekoSessionEvent["data"] {
  return { type: "model-input", source: "live", messageId, text: "Sửa cấu hình", providerInstanceId: instanceId };
}
function activity(overrides: Record<string, unknown> = {}): NekoSessionEvent["data"] {
  return {
    type: "workspace-activity", activityId: "tool-a", title: "Sửa cấu hình",
    status: "in_progress", toolName: "write_file", operation: "update",
    locations: [{ path: "C:/project/config.json", line: 12 }], detail: "Thay cấu hình của dự án.",
    ...overrides,
  } as NekoSessionEvent["data"];
}
function session(overrides: Partial<PermissionPreviewSession> = {}): PermissionPreviewSession {
  return {
    runtime,
    events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2), event(activity(), 3)],
    messages: [{ id: "input-a", role: "user", text: "Sửa cấu hình" }, { id: "answer-a", role: "assistant", blocks: [] }],
    ...overrides,
  };
}
const noData = "Chưa có thông tin thao tác.";

describe("pending request content", () => {
  const pending = (tool: unknown): PermissionRequest => ({ ...request, toolPreview: acpPermissionPreview(tool) });
  it("shows the exact request's write, not cached activity arguments, with Vietnamese choices", () => {
    const onResolve = vi.fn();
    render(<PermissionCard request={{ ...pending({ name: "write_file", locations: [{ path: "/project/new.txt" }],
      rawInput: { content: "First line\n  indented\n", api_key: "NOT_DISPLAYED" } }), options: [
      { optionId: "opaque-allow", label: "Allow once", kind: "allow_once" },
      { optionId: "opaque-session", label: "Always allow write_file in this session", kind: "allow_always" },
      { optionId: "opaque-deny", label: "Reject once", kind: "reject_once" },
      { optionId: "opaque-block", label: "Always reject write_file in this session", kind: "reject_always" },
    ] }} session={session()} onResolve={onResolve} />);
    expect(screen.getByLabelText("Nội dung mới").textContent).toBe("First line\n  indented\n");
    expect(screen.getByTestId("permission-preview").textContent).not.toContain("config.json");
    expect(screen.getByTestId("permission-preview").textContent).not.toContain("NOT_DISPLAYED");
    expect(within(screen.getByRole("group", { name: "Quyết định" })).getAllByRole("button").map(button => button.textContent)).toEqual(["Cho phép", "Từ chối"]);
    expect(screen.getByText("Thêm lựa chọn").closest("details")!.open).toBe(false);
    fireEvent.click(screen.getByText("Thêm lựa chọn"));
    expect(screen.getAllByRole("button").map(button => button.textContent)).toEqual([
      "Cho phép", "Từ chối", "Cho phép ghi tệp cả phiên", "Chặn ghi tệp cả phiên",
    ]);
    fireEvent.click(screen.getByRole("button", { name: "Cho phép ghi tệp cả phiên" }));
    expect(onResolve).toHaveBeenCalledWith("opaque-session");
  });

  it("renders empty writes and provider markup as literal code", () => {
    const { container, rerender } = render(<PermissionCard request={pending({ name: "write_file", rawInput: { content: "" } })} onResolve={vi.fn()} />);
    expect(screen.getByLabelText("Nội dung mới").textContent).toBe("(Tệp trống)");
    rerender(<PermissionCard request={pending({ name: "write_file", rawInput: { content: '<script>alert(1)</script>\n\u202Efake' } })} onResolve={vi.fn()} />);
    expect(screen.getByLabelText("Nội dung mới").textContent).toBe('<script>alert(1)</script>\n[U+202E]fake');
    expect(container.querySelector("script")).toBeNull();
  });

  it("supports Neko edits and standard ACP diffs without inferring paths from rawInput", () => {
    const edit = acpPermissionPreview({ name: "edit", rawInput: { path: "not-a-structured-target", old_string: "before", new_string: "after" } })!;
    expect(edit.locations).toEqual([]);
    expect(edit.changes).toEqual([{ before: "before", after: "after" }]);
    const multi = acpPermissionPreview({ name: "multi_edit", rawInput: { edits: [{ old_string: "a", new_string: "b" }, { old_string: "c", new_string: "" }] } })!;
    expect(multi.changes).toEqual([{ before: "a", after: "b" }, { before: "c", after: "" }]);
    render(<PermissionCard request={pending({ content: [{ type: "diff", path: "/real.txt", oldText: "old", newText: "new" }] })} onResolve={vi.fn()} />);
    expect(screen.getByLabelText("Nội dung cũ").textContent).toBe("old");
    expect(screen.getByLabelText("Nội dung mới").textContent).toBe("new");
  });

  it("does not reuse previous content when a subsequent request omits it", () => {
    const { rerender } = render(<PermissionCard request={pending({ name: "write_file", rawInput: { content: "CURRENT" } })} onResolve={vi.fn()} />);
    rerender(<PermissionCard request={{ ...pending({ name: "write_file" }), requestId: "next-request" }} session={session()} onResolve={vi.fn()} />);
    expect(screen.queryByText("CURRENT")).toBeNull();
    expect(screen.getByText("Agent chưa gửi nội dung thay đổi.")).toBeTruthy();
  });

  it("bounds large content and explicitly signals an incomplete preview", () => {
    const snapshot = acpPermissionPreview({ name: "write_file", locations: [{ path: "/large.txt" }], rawInput: { content: "x".repeat(100_000) } })!;
    expect(snapshot.changes[0].after.length).toBeLessThanOrEqual(16_000);
    expect(snapshot.truncated).toBe(true);
    render(<PermissionCard request={{ ...request, toolPreview: snapshot }} onResolve={vi.fn()} />);
    expect(screen.getByText("Bản xem trước đã rút gọn.")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Nội dung sắp ghi" }).className).toContain("max-h-52");
  });

  it("distinguishes deleting an edit snippet from writing an empty file", () => {
    render(<PermissionCard request={pending({ name: "edit", rawInput: { old_string: "remove this snippet", new_string: "" } })} onResolve={vi.fn()} />);
    expect(screen.getByLabelText("Nội dung mới").textContent).toBe("(Xoá đoạn này)");
    expect(screen.queryByText("(Tệp trống)")).toBeNull();
  });

  it("keeps replacement text visible when the old snippet is huge and marks omitted content honestly", () => {
    const large = pending({ name: "multi_edit", rawInput: { edits: [
      { old_string: "old".repeat(20_000), new_string: "REPLACEMENT".repeat(2000) },
      { old_string: "a", new_string: "STILL_NONEMPTY" },
    ] } });
    render(<PermissionCard request={large} onResolve={vi.fn()} />);
    expect(screen.getAllByLabelText("Nội dung mới")[0].textContent).toContain("REPLACEMENT");
    expect(screen.getAllByLabelText("Nội dung mới")[1].textContent).toBe("(Đã rút gọn)");
    expect(screen.queryByText("(Tệp trống)")).toBeNull();
    expect(screen.queryByText("(Xoá đoạn này)")).toBeNull();
  });
});

describe("permission preview evidence", () => {
  it("keeps an unlinked request honest instead of inferring command or target from its title", () => {
    render(<PermissionCard request={{ ...request, activityId: undefined, title: "rm C:/private/secrets.json" }} onResolve={vi.fn()} session={session()} />);
    expect(screen.getByTestId("permission-preview").textContent).toBe(noData);
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual(["Cho phép", "Từ chối"]);
  });

  it("shows only structured facts from the exact current activity", () => {
    const state = session();
    state.events.push(event(activity({ activityId: "unrelated", toolName: "delete_file", operation: "delete", locations: [{ path: "C:/other/secret.txt" }] }), 4));
    render(<PermissionCard request={request} onResolve={vi.fn()} session={state} />);
    const preview = screen.getByTestId("permission-preview");
    expect(within(preview).getByText("write_file")).toBeTruthy();
    expect(within(preview).getByText("Sửa tệp")).toBeTruthy();
    expect(within(preview).getByText("C:/project/config.json · dòng 12")).toBeTruthy();
    expect(within(preview).getByText("Thay cấu hình của dự án.")).toBeTruthy();
    expect(preview.textContent).not.toContain("secret.txt");
  });

  it("does not borrow another activity when the exact ID is missing", () => {
    render(<PermissionCard request={{ ...request, activityId: "tool-missing" }} onResolve={vi.fn()} session={session()} />);
    expect(screen.getByTestId("permission-preview").textContent).toBe(noData);
  });

  it("does not reuse a matching activity from an earlier turn", () => {
    const state = session();
    state.events.push(event(input("input-new"), 4));
    state.messages.push({ id: "input-new", role: "user", text: "Công việc khác" }, { id: "answer-new", role: "assistant", blocks: [] });
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("rejects recycled IDs even when a new event carries possibly cached old metadata", () => {
    const state = session();
    state.events.push(event(input("input-new"), 4), event(activity({ detail: "Metadata có thể được cache" }), 5));
    state.messages.push({ id: "input-new", role: "user", text: "Công việc khác" }, { id: "answer-new", role: "assistant", blocks: [] });
    render(<PermissionCard request={request} onResolve={vi.fn()} session={state} />);
    expect(screen.getByTestId("permission-preview").textContent).toBe(noData);
  });

  it("rejects an old activity after runtime replacement", () => {
    const nextRuntime = { ...runtime, instanceId: "runtime-b" };
    const state = session({ runtime: nextRuntime });
    state.events.push(event({ type: "runtime-attached", provider: nextRuntime }, 4), event(input("input-new", "runtime-b"), 5));
    state.messages.push({ id: "input-new", role: "user", text: "Tiếp tục" }, { id: "answer-new", role: "assistant", blocks: [] });
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("requires the latest runtime attachment to match even if the input claims the live instance", () => {
    const state = session({ events: [
      event({ type: "runtime-attached", provider: { ...runtime, instanceId: "old-runtime" } }, 1),
      event(input(), 2), event(activity(), 3),
    ] });
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it.each(["completed", "cancelled", "failed"])("does not resurrect a %s activity from a prior pending update", (status) => {
    const state = session();
    state.events.push(event(activity({ status }), 4));
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("falls back to only the exact current pending tool display name, never its arguments or result", () => {
    const state = session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2)],
      messages: [
        { id: "input-a", role: "user", text: "Làm việc" },
        { id: "answer-a", role: "assistant", blocks: [{
          type: "tool_execution", id: "tool-a", status: "pending",
          tool: { id: "tool-a", name: "Run dangerous-looking-title C:/fake-target", args: { command: "secret-command" }, result: "secret-result" },
        }] },
      ],
    });
    render(<PermissionCard request={request} onResolve={vi.fn()} session={state} />);
    const preview = screen.getByTestId("permission-preview");
    expect(within(preview).getByText("Run dangerous-looking-title C:/fake-target")).toBeTruthy();
    expect(within(preview).getByText("Chưa có mục tiêu.")).toBeTruthy();
    expect(preview.textContent).not.toContain("secret-command");
    expect(preview.textContent).not.toContain("secret-result");
    expect(within(preview).queryByText("Thao tác")).toBeNull();
  });

  it("does not use a historical assistant block after attachment or a mismatched tool identity", () => {
    const state = session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2)],
      messages: [
        { id: "input-a", role: "user", text: "Làm việc" },
        { id: "answer-a", role: "assistant", blocks: [{
          type: "tool_execution", id: "tool-a", status: "pending", tool: { id: "different-id", name: "Other tool" },
        }] },
      ],
    });
    expect(buildPermissionPreview(request, state).source).toBe("missing");
    state.events.push(event({ type: "runtime-attached", provider: runtime }, 3));
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("does not use a current block whose ID existed in an earlier assistant message", () => {
    const block = { type: "tool_execution" as const, id: "tool-a", status: "pending" as const, tool: { id: "tool-a", name: "Cached activity" } };
    const state = session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2)],
      messages: [
        { id: "old-user", role: "user", text: "Cũ" }, { id: "old-answer", role: "assistant", blocks: [block] },
        { id: "input-a", role: "user", text: "Mới" }, { id: "answer-a", role: "assistant", blocks: [block] },
      ],
    });
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("reports missing context for null runtime, missing session, malformed arrays and detached runtime", () => {
    expect(buildPermissionPreview(request).source).toBe("missing");
    expect(buildPermissionPreview(request, session({ runtime: null })).source).toBe("missing");
    expect(buildPermissionPreview(request, { runtime, events: null, messages: null } as unknown as PermissionPreviewSession).source).toBe("missing");
    const state = session();
    state.events.push(event({ type: "runtime-detached", providerId: "neko", instanceId: runtime.instanceId, kind: "acp", reason: "close" }, 4));
    expect(buildPermissionPreview(request, state).source).toBe("missing");
  });

  it("escapes provider markup as text in the title and linked preview", () => {
    const markup = '<img src=x onerror="window.previewExecuted=true"><script>window.previewExecuted=true</script>';
    const { container } = render(<PermissionCard request={{ ...request, title: markup }} onResolve={vi.fn()} session={session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2), event(activity({
        toolName: markup, detail: markup, locations: [{ path: markup }],
      }), 3)],
    })} />);
    expect(screen.getByTestId("permission-preview").textContent).toContain("<img");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect((window as unknown as Record<string, unknown>).previewExecuted).toBeUndefined();
  });

  it("bounds huge text and target lists, signals truncation, and keeps narrow content wrap-safe", () => {
    const huge = "x".repeat(20_000);
    const { container } = render(<PermissionCard request={{ ...request, title: huge }} onResolve={vi.fn()} session={session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2), event(activity({
        toolName: huge, title: huge, detail: huge,
        locations: Array.from({ length: 5000 }, (_, index) => ({ path: "/workspace/" + huge + index, line: index + 1 })),
      }), 3)],
    })} />);
    const preview = screen.getByTestId("permission-preview");
    expect(preview.querySelectorAll("li")).toHaveLength(5);
    expect(preview.textContent!.length).toBeLessThan(2800);
    expect(within(preview).getByText("Bản xem trước đã rút gọn.")).toBeTruthy();
    expect(screen.getByTestId("permission-card").className).toContain("[overflow-wrap:anywhere]");
    expect(container.querySelectorAll("button")).toHaveLength(2);
  });

  it("makes invisible controls and bidi instructions visible in provider text", () => {
    const controlledPath = "C:/report/" + String.fromCharCode(0x202e) + "cod.exe\nnext.txt";
    const controlledLabel = "Cho phép" + String.fromCharCode(0x2066) + "x";
    const onResolve = vi.fn();
    render(<PermissionCard request={{ ...request, options: [{ ...request.options[0], label: controlledLabel }] }} onResolve={onResolve} session={session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(input(), 2), event(activity({
        locations: [{ path: controlledPath }], detail: "run" + String.fromCharCode(0) + "ok",
      }), 3)],
    })} />);
    const preview = screen.getByTestId("permission-preview");
    expect(preview.textContent).toContain("C:/report/[U+202E]cod.exe[U+000A]next.txt");
    expect(preview.textContent).toContain("run[U+0000]ok");
    expect(preview.textContent).not.toContain(String.fromCharCode(0x202e));
    const allow = screen.getByRole("button", { name: "Cho phép[U+2066]x" });
    fireEvent.click(allow);
    expect(onResolve).toHaveBeenCalledWith("opaque-allow");
  });

  it("signals truncation for huge unlinked titles and labels while retaining choices", () => {
    const onResolve = vi.fn();
    const huge = "long".repeat(5000);
    render(<PermissionCard request={{
      ...request, activityId: undefined, title: huge,
      options: [{ ...request.options[0], label: huge }, request.options[1]],
    }} onResolve={onResolve} />);
    expect(screen.getByText(noData)).toBeTruthy();
    expect(screen.getByText("Bản xem trước đã rút gọn.")).toBeTruthy();
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent!.length)).toEqual([161, 7]);
    fireEvent.click(buttons[0]);
    expect(onResolve).toHaveBeenCalledWith("opaque-allow");
  });

  it("can preview fresh structured initialization activity after the current attachment without a prompt", () => {
    render(<PermissionCard request={request} onResolve={vi.fn()} session={session({
      events: [event({ type: "runtime-attached", provider: runtime }, 1), event(activity(), 2)],
      messages: [],
    })} />);
    const preview = screen.getByTestId("permission-preview");
    expect(within(preview).getByText("write_file")).toBeTruthy();
    expect(within(preview).getByText("C:/project/config.json · dòng 12")).toBeTruthy();
  });

  it("ignores malformed facts and prototype-looking operation names without inventing targets", () => {
    const state = session();
    state.events.push(null as unknown as NekoSessionEvent, event(activity({
      toolName: 42, detail: { rawInput: "not-preview" }, operation: "__proto__",
      locations: [null, { path: 9 }, { path: "C:/valid.txt", line: Number.NaN }],
    }), 4));
    render(<PermissionCard request={request} onResolve={vi.fn()} session={state} />);
    const preview = screen.getByTestId("permission-preview");
    expect(within(preview).getByText("C:/valid.txt")).toBeTruthy();
    expect(within(preview).queryByText("Thao tác")).toBeNull();
    expect(preview.textContent).not.toContain("not-preview");
    expect(preview.textContent).not.toContain("NaN");
  });

  it("recomputes evidence when a new permission request has a different activity link", () => {
    const state = session();
    const { rerender } = render(<PermissionCard request={request} onResolve={vi.fn()} session={state} />);
    expect(screen.getByTestId("permission-preview").textContent).toContain("config.json");
    rerender(<PermissionCard request={{ ...request, requestId: "permission-b", activityId: "missing-b" }} onResolve={vi.fn()} session={state} />);
    expect(screen.getByTestId("permission-preview").textContent).toBe(noData);
  });
});

describe("permission option scope and dispatch compatibility", () => {
  it("discloses persistent choices separately while preserving opaque IDs and scope", () => {
    const onResolve = vi.fn();
    const scopedRequest: PermissionRequest = { ...request, options: [
      { optionId: "allow-persistent-id", label: "Một lần", kind: "allow_always" },
      { optionId: "deny-once-id", label: "Từ chối", kind: "reject_once" },
      { optionId: "allow-once-id", label: "Cho phép lâu dài", kind: "allow_once" },
      { optionId: "deny-persistent-id", label: "Không cho phép nữa", kind: "reject_always" },
      { optionId: "unknown-option-id", label: "Khác", kind: "other" },
    ] };
    render(<PermissionCard request={scopedRequest} onResolve={onResolve} />);
    expect(within(screen.getByRole("group", { name: "Quyết định" })).getAllByRole("button").map(button => button.textContent)).toEqual(["Cho phép lâu dài", "Từ chối"]);
    fireEvent.click(screen.getByText("Thêm lựa chọn"));
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent)).toEqual(["Cho phép lâu dài", "Từ chối", "Một lần", "Không cho phép nữa", "Khác"]);
    const description = (button: HTMLElement) => document.getElementById(button.getAttribute("aria-describedby")!)?.textContent;
    expect(description(screen.getByRole("button", { name: "Cho phép lâu dài" }))).toBe("Chỉ lần này");
    expect(description(screen.getByRole("button", { name: "Một lần" }))).toBe("Phạm vi do agent quyết định");
    expect(description(screen.getByRole("button", { name: "Khác" }))).toBe("Chưa rõ phạm vi");
    fireEvent.click(screen.getByRole("button", { name: "Một lần" }));
    expect(onResolve).toHaveBeenCalledWith("allow-persistent-id");
  });

  it("keeps a new request's persistent choices collapsed and never auto-selects", () => {
    const onResolve = vi.fn();
    const options: PermissionRequest["options"] = [...request.options, { optionId: "session", label: "Always allow write_file in this session", kind: "allow_always" }];
    const { rerender } = render(<PermissionCard request={{ ...request, options }} onResolve={onResolve} />);
    fireEvent.click(screen.getByText("Thêm lựa chọn"));
    expect(screen.getByRole("button", { name: "Cho phép ghi tệp cả phiên" })).toBeTruthy();
    rerender(<PermissionCard request={{ ...request, requestId: "next", options }} onResolve={onResolve} />);
    expect(screen.getByText("Thêm lựa chọn").closest("details")!.open).toBe(false);
    expect(onResolve).not.toHaveBeenCalled();
  });

  it.each([
    ["resolution", { resolving: true }, "Đang lưu quyết định…"],
    ["cancellation", { blockedByCancel: true }, "Đang lưu yêu cầu dừng…"],
  ] as const)("keeps deny/allow focusable but blocks repeated clicks during %s", (_name, flags, label) => {
    const onResolve = vi.fn();
    render(<PermissionCard request={request} onResolve={onResolve} {...flags} />);
    const allow = screen.getByRole("button", { name: "Cho phép" }) as HTMLButtonElement;
    const deny = screen.getByRole("button", { name: "Từ chối" }) as HTMLButtonElement;
    allow.focus();
    for (let i = 0; i < 3; i++) { fireEvent.click(allow); fireEvent.click(deny); }
    expect(onResolve).not.toHaveBeenCalled();
    expect(allow.disabled).toBe(false);
    expect(deny.disabled).toBe(false);
    expect(allow.getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByTestId("permission-card").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("status").textContent).toBe(label);
    expect(document.activeElement).toBe(allow);
  });

  it.each(["Cho phép", "Từ chối"])("dispatches %s once when its parent crosses the existing resolving barrier", (label) => {
    const onResolve = vi.fn();
    function Parent() {
      const [resolving, setResolving] = useState(false);
      return <PermissionCard request={request} resolving={resolving} onResolve={(id) => { onResolve(id); setResolving(true); }} />;
    }
    render(<Parent />);
    const button = screen.getByRole("button", { name: label });
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(screen.getByRole("button", { name: label === "Cho phép" ? "Từ chối" : "Cho phép" }));
    expect(onResolve).toHaveBeenCalledTimes(1);
    expect(onResolve).toHaveBeenCalledWith(label === "Cho phép" ? "opaque-allow" : "opaque-deny");
  });

  it("assigns independent accessible scope descriptions to multiple cards", () => {
    render(<><PermissionCard request={request} onResolve={vi.fn()} /><PermissionCard request={{ ...request, requestId: "permission-b" }} onResolve={vi.fn()} /></>);
    const ids = screen.getAllByRole("button").map((button) => button.getAttribute("aria-describedby"));
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(document.getElementById(id!)?.textContent).toBe("Chỉ lần này");
  });
});
