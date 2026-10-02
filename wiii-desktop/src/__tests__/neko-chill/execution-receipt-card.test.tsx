import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExecutionReceiptCard } from "@/neko-chill/components/ExecutionReceiptCard";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import type { NekoExecutionProjection } from "@/neko-chill/drivers/types";
const known = { status: "reported", version: 1, taskId: "task-a", root: "e:\\task-a",
  activationEpoch: 1, activationId: "activation-a", bashTarget: "host", bashExecutor: "local-process",
  approvalMode: "auto", yolo: true, nativeBackendSandbox: null } as const;
function session(value: NekoExecutionProjection = known): NekoSession {
  return { agentId: "neko", runtime: { instanceId: "runtime-a" }, closePending: false, deletePending: false,
    taskScope: { version: 1, mode: "fixed-active-task", state: "bound", threadId: "thread-a",
      execution: { taskId: "work-a", runId: "run-a", environmentId: "env-a" }, projectId: null,
      workspacePath: known.root, authorizedRoot: known.root, label: "Tác vụ A", backendSessionId: "backend-a",
      receipt: { version: 1, mode: "fixed-active-task", id: known.taskId, label: "Tác vụ A", root: known.root,
        activationEpoch: 1, activationId: "activation-a" } },
    executionProjection: { providerInstanceId: "runtime-a", value } } as NekoSession;
}
afterEach(cleanup);
describe("read-only execution receipt card", () => {
  it("separates host placement, approval and logical root without grant controls", () => {
    const { container } = render(<ExecutionReceiptCard session={session()} />);
    expect(screen.getByText(/Host · tiến trình cục bộ/)).toBeTruthy();
    expect(screen.getByText("Auto — tự động theo policy")).toBeTruthy();
    expect(screen.getByText("YOLO bật")).toBeTruthy();
    expect(screen.getByText("Thư mục tác vụ (logic)")).toBeTruthy();
    expect(container.querySelector('bdi[dir="ltr"]')?.textContent).toBe(known.root);
    expect(container.querySelectorAll("button,input,select")).toHaveLength(0);
  });
  it("requested sandbox and auto remain independent, unsupported backend is readable", () => {
    render(<ExecutionReceiptCard session={session({ ...known, bashTarget: "sandbox",
      bashExecutor: "native-backend", nativeBackendSandbox: "unsupported" })} />);
    expect(screen.getByText(/Sandbox được yêu cầu · backend native/)).toBeTruthy();
    expect(screen.getByText(/Backend báo chưa hỗ trợ sandbox/)).toBeTruthy();
    expect(screen.getByText("Auto — tự động theo policy")).toBeTruthy();
  });
  it.each(["unknown", "unsupported", "unverified"] as const)("%s never shows known placement or root", status => {
    render(<ExecutionReceiptCard session={session({ status })} />);
    expect(screen.queryByText(known.root)).toBeNull();
    expect(screen.queryByText(/Host ·/)).toBeNull();
    expect(screen.queryByText("YOLO bật")).toBeNull();
  });
  it.each(["detached", "replacement", "closing", "deleting"])("clears visible live facts on %s", state => {
    const item = session();
    if (state === "detached") item.runtime = null;
    if (state === "replacement") item.executionProjection!.providerInstanceId = "retired-runtime";
    if (state === "closing") item.closePending = true;
    if (state === "deleting") item.deletePending = true;
    render(<ExecutionReceiptCard session={item} />);
    expect(screen.queryByText(known.root)).toBeNull();
  });
  it("manual/legacy choice remains explicit, selected workspace is not a receipt", () => {
    const item = session(); item.taskScope = undefined;
    render(<ExecutionReceiptCard session={item} />);
    expect(screen.getByText(/Phiên thủ công\/cũ/)).toBeTruthy();
    expect(screen.queryByText(known.root)).toBeNull();
  });
  it("escapes bidi controls in visible root and tooltip without modifying identity", () => {
    const value = { ...known, root: "e:\\task-a\\file\u202etxt" };
    const item = session(value);
    const { container } = render(<ExecutionReceiptCard session={item} />);
    expect(container.querySelector("bdi")?.textContent).toBe("e:\\task-a\\file\\u202etxt");
    expect(container.querySelector("dd[title]")?.getAttribute("title")).toBe("e:\\task-a\\file\\u202etxt");
    expect(item.executionProjection!.value).toEqual(value);
  });
  it("does not project Neko-specific metadata for another provider", () => {
    const item = session(); item.agentId = "claude";
    render(<ExecutionReceiptCard session={item} />);
    expect(screen.queryByTestId("execution-receipt-card")).toBeNull();
  });
});
