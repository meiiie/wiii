/** Fixtures for the missing baseline scoped deletion warning; reviewer did not run.
 * Existing deletion semantics and focus guards must remain unchanged.
 */
import { useRef, useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionDeleteDialog } from "@/neko-chill/components/SessionDeleteDialog";
import { useNekoSessionStore, type NekoSession } from "@/neko-chill/stores/neko-session-store";
import { createPendingNekoTaskMapping, bindNekoTaskMapping, markNekoTaskRecovery,
  type NekoTaskScopeState } from "@/neko-chill/task-scope-mapping";

const originalDelete = useNekoSessionStore.getState().deleteSession;
const ID = "delete-recovery-target";
const TITLE = "Phiên cần đối soát";
const ROOT = "E:\\MeiiieGroup\\integration-tests\\scope-delete-fixture";
const EXECUTION = { taskId: "delete-work-item", runId: "delete-run", environmentId: "delete-environment" };
function pending() {
  return createPendingNekoTaskMapping({ threadId: ID, providerId: "neko", projectId: null,
    execution: EXECUTION, workspacePath: ROOT }, TITLE)!;
}
function bound() {
  return bindNekoTaskMapping(pending(), { version: 1, mode: "fixed-active-task", id: "delete-canonical-task",
    label: TITLE, root: ROOT.toLowerCase(), activationEpoch: 1, activationId: "delete-activation" },
  "delete-coordinator", ROOT);
}
function scoped(state: "bound" | "pending-new" | "recovery-known" | "recovery-unknown" | "invalid"): NekoTaskScopeState {
  if (state === "bound") return bound();
  if (state === "pending-new") return pending();
  if (state === "recovery-known") return markNekoTaskRecovery(bound(), "load-response-uncertain");
  if (state === "recovery-unknown") return markNekoTaskRecovery(pending(), "new-response-uncertain");
  return { state: "invalid", reason: "invalid-mapping" };
}
function session(taskScope?: NekoTaskScopeState): NekoSession {
  return { id: ID, title: TITLE, agentId: "neko", agentName: "Neko Core",
    workspace: { path: ROOT, name: "scope-delete-fixture" }, launchProfile: null,
    kind: taskScope ? "worker" : "scratch", projectId: null, execution: taskScope ? EXECUTION : null,
    backendSessionId: taskScope && "backendSessionId" in taskScope ? taskScope.backendSessionId : null,
    controls: [], commands: [], pendingControlId: null, createdAt: 1, updatedAt: 1, lastActivityAt: 1,
    status: taskScope ? "error" : "exited", statusDetail: "Đã lưu", messages: [], events: [],
    eventHighWaterMark: 0, runtime: null, pendingPermission: null, resolvingPermissionId: null,
    cancelPending: false, closePending: false, deletePending: false, ...(taskScope ? { taskScope } : {}) };
}
function remove(id: string) {
  useNekoSessionStore.setState(state => {
    const sessions = { ...state.sessions }; delete sessions[id];
    return { sessions, activeSessionId: state.activeSessionId === id ? null : state.activeSessionId };
  });
}
function Fixture() {
  const opener = useRef<HTMLButtonElement>(null);
  const fallback = useRef<HTMLButtonElement>(null);
  const [show, setShow] = useState(false);
  return <>
    <button ref={opener} onClick={() => setShow(true)}>Xóa phiên thử nghiệm</button>
    <button ref={fallback}>Tạo phiên mới</button>
    {show ? <SessionDeleteDialog target={{ id: ID, title: TITLE }} opener={opener.current}
      fallbackFocusRef={fallback} onCancel={() => setShow(false)} onDeleted={() => setShow(false)} /> : null}
  </>;
}
function open() {
  render(<Fixture />);
  const opener = screen.getByRole("button", { name: "Xóa phiên thử nghiệm" });
  opener.focus(); fireEvent.click(opener);
  return { opener, dialog: screen.getByRole("dialog", { name: "Xóa lịch sử phiên?" }) };
}
beforeEach(() => {
  useNekoSessionStore.setState({ sessions: { [ID]: session() }, activeSessionId: ID, deleteSession: vi.fn(async () => {}) });
});
afterEach(() => {
  cleanup(); useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, deleteSession: originalDelete });
});

describe("Scoped deletion consequence and actual deletion semantics", () => {
  it.each(["bound", "pending-new", "recovery-known", "recovery-unknown", "invalid"] as const)("%s explains loss of Wiii linkage and leaves Neko checkpoint/lock ownership explicit", (state) => {
    useNekoSessionStore.setState({ sessions: { [ID]: session(scoped(state)) } });
    const { dialog } = open();
    const warning = within(dialog).getByTestId("session-delete-task-scope-warning");
    expect(warning.getAttribute("role")).toBe("note");
    expect(warning.textContent).toMatch(/liên kết/i);
    expect(warning.textContent).toMatch(/đối soát/i);
    expect(warning.textContent).toMatch(/không xóa.*checkpoint/i);
    expect(warning.textContent).toMatch(/writer lock/i);
    expect(warning.id).not.toBe("");
    expect(dialog.getAttribute("aria-describedby")?.split(/\s+/)).toContain(warning.id);
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Hủy" }));
  });

  it("legacy deletion retains the usual explanation without a scoped receipt claim", async () => {
    const deleteSession = vi.fn(async (id: string) => remove(id));
    useNekoSessionStore.setState({ deleteSession });
    const { dialog } = open();
    expect(within(dialog).queryByTestId("session-delete-task-scope-warning")).toBeNull();
    expect(within(dialog).getByText(/Tệp trong thư mục dự án vẫn được giữ nguyên/)).toBeTruthy();
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(ID);
    expect(useNekoSessionStore.getState().sessions[ID]).toBeUndefined();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it.each(["cancel", "escape"] as const)("%s preserves both recovery history and receipt and restores focus", async (method) => {
    const receipt = scoped("recovery-known");
    useNekoSessionStore.setState({ sessions: { [ID]: session(receipt) } });
    const { dialog, opener } = open();
    if (method === "cancel") fireEvent.click(within(dialog).getByRole("button", { name: "Hủy" }));
    else fireEvent.keyDown(dialog, { key: "Escape" });
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
    expect(useNekoSessionStore.getState().sessions[ID].taskScope).toEqual(receipt);
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("confirmed recovery deletion removes Wiii content/mapping rather than retaining a hidden tombstone", async () => {
    const deleteSession = vi.fn(async (id: string) => remove(id));
    useNekoSessionStore.setState({ sessions: { [ID]: session(scoped("recovery-known")) }, deleteSession });
    const { dialog } = open();
    expect(within(dialog).getByTestId("session-delete-task-scope-warning")).toBeTruthy();
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(ID);
    expect(useNekoSessionStore.getState().sessions[ID]).toBeUndefined();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
