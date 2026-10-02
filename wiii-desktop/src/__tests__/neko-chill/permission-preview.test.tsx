import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PermissionCard } from "@/neko-chill/components/PermissionCard";
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
const noData = "Chưa có dữ liệu công cụ hoặc mục tiêu được liên kết cho yêu cầu này.";

describe("permission preview evidence", () => {
  it("keeps an unlinked request honest instead of inferring command or target from its title", () => {
    render(<PermissionCard request={{ ...request, activityId: undefined, title: "rm C:/private/secrets.json" }} onResolve={vi.fn()} session={session()} />);
    expect(screen.getByTestId("permission-preview").textContent).toBe(noData);
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual(["Từ chối", "Cho phép"]);
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
    expect(within(preview).getByText("Chưa có mục tiêu được cung cấp.")).toBeTruthy();
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
    expect(within(preview).getByText("Thông tin dài đã được rút gọn để xem trước.")).toBeTruthy();
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
    expect(screen.getByText("Thông tin dài đã được rút gọn để xem trước.")).toBeTruthy();
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent!.length)).toEqual([7, 161]);
    fireEvent.click(buttons[1]);
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
  it("describes once versus persistent choices from kind, preserves opaque IDs and deny-first order", () => {
    const onResolve = vi.fn();
    const scopedRequest: PermissionRequest = { ...request, options: [
      { optionId: "allow-persistent-id", label: "Một lần", kind: "allow_always" },
      { optionId: "deny-once-id", label: "Từ chối", kind: "reject_once" },
      { optionId: "allow-once-id", label: "Cho phép lâu dài", kind: "allow_once" },
      { optionId: "deny-persistent-id", label: "Không cho phép nữa", kind: "reject_always" },
      { optionId: "unknown-option-id", label: "Khác", kind: "other" },
    ] };
    render(<PermissionCard request={scopedRequest} onResolve={onResolve} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent)).toEqual(["Từ chối", "Không cho phép nữa", "Khác", "Một lần", "Cho phép lâu dài"]);
    const description = (button: HTMLElement) => document.getElementById(button.getAttribute("aria-describedby")!)?.textContent;
    expect(description(screen.getByRole("button", { name: "Cho phép lâu dài" }))).toBe("Chỉ áp dụng cho yêu cầu này.");
    expect(description(screen.getByRole("button", { name: "Một lần" }))).toContain("Phạm vi áp dụng cụ thể chưa được agent cung cấp.");
    expect(description(screen.getByRole("button", { name: "Khác" }))).toBe("Phạm vi áp dụng chưa được agent cung cấp.");
    fireEvent.click(screen.getByRole("button", { name: "Một lần" }));
    expect(onResolve).toHaveBeenCalledWith("allow-persistent-id");
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
    for (const id of ids) expect(document.getElementById(id!)?.textContent).toBe("Chỉ áp dụng cho yêu cầu này.");
  });
});
