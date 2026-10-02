import { describe, expect, it, vi } from "vitest";
import { projectNekoExecutionReceipt, executionCapability } from "@/neko-chill/drivers/acp/execution-projection";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";
const task: NekoTaskReceipt = { version: 1, mode: "fixed-active-task", id: "task-a",
  label: "Tác vụ A", root: "e:\\work\\a", activationEpoch: 1, activationId: "activation-a" };
const capability = { version: 1 };
const receipt = () => ({ version: 1, taskId: task.id, root: task.root,
  activationEpoch: task.activationEpoch, activationId: task.activationId,
  authorityId: null, policyId: "a".repeat(64), bashTarget: "host", bashExecutor: "local-process",
  nativeBackend: null, confinement: "none", osAuthority: "not-attested",
  approval: { mode: "default", yolo: false } });
function project(value: unknown, advertised: unknown = capability) {
  return projectNekoExecutionReceipt({ _meta: { "neko.execution": value } }, task, advertised);
}
describe("passive execution receipt display codec", () => {
  it.each(["default", "accept-edits", "plan", "auto"])("reports host/%s independently of placement", mode => {
    expect(project({ ...receipt(), approval: { mode, yolo: mode === "auto" } })).toMatchObject({
      status: "reported", bashTarget: "host", approvalMode: mode, yolo: mode === "auto" });
  });
  it.each(["default", "auto"])("reports requested sandbox/%s without OS attestation", mode => {
    expect(project({ ...receipt(), bashTarget: "sandbox", confinement: "required-not-attested",
      approval: { mode, yolo: false } })).toMatchObject({ status: "reported", bashTarget: "sandbox", approvalMode: mode });
  });
  it("accepts native unsupported sandbox as a reported requirement, not health", () => {
    expect(project({ ...receipt(), bashTarget: "sandbox", bashExecutor: "native-backend",
      confinement: "required-not-attested", nativeBackend: { protocol: "neko-native-posix-v1",
        root: "/different-machine/root", bashSandbox: "unsupported" } })).toMatchObject({
      status: "reported", nativeBackendSandbox: "unsupported", root: task.root });
  });
  it("local Bash may have another tool backend with a different root", () => {
    expect(project({ ...receipt(), nativeBackend: { protocol: "neko-native-posix-v1", root: "/native/root",
      bashSandbox: "backend-enforced" } })).toMatchObject({ status: "reported", bashExecutor: "local-process" });
  });
  it.each([
    { taskId: "task-b" }, { root: "e:\\work\\b" }, { activationEpoch: 2 },
    { activationEpoch: Number.MAX_SAFE_INTEGER + 1 }, { activationId: "retired" },
    { authorityId: "secret-token" }, { policyId: "not-a-digest" },
    { osAuthority: "granted" }, { confinement: "enforced" },
    { bashExecutor: "native-backend", nativeBackend: null },
    { approval: { mode: "default", yolo: true } }, { approval: { mode: "auto", yolo: "yes" } },
    { root: "e:\\work\\a\nunsafe" },
  ])("does not project mismatched/malformed known facts: %j", patch => {
    expect(project({ ...receipt(), ...patch })).toEqual({ status: "unverified" });
  });
  it.each([{ version: 2 }, { bashTarget: "remote" }, { bashExecutor: "anything" },
    { approval: { mode: "future", yolo: false } },
    { nativeBackend: { protocol: "future", root: "/root", bashSandbox: "backend-enforced" } },
  ])("does not map unsupported data to a safer known value: %j", patch => {
    expect(project({ ...receipt(), ...patch })).toEqual({ status: "unsupported" });
  });
  it("keeps missing and unadvertised data explicit", () => {
    expect(project(undefined)).toEqual({ status: "unknown" });
    expect(projectNekoExecutionReceipt({ _meta: { "neko.execution": receipt() } }, task, undefined)).toEqual({ status: "unverified" });
    expect(project(receipt(), { version: 2 })).toEqual({ status: "unsupported" });
    expect(executionCapability({ _meta: { "neko.executionProtocol": capability } })).toEqual(capability);
  });
  it("normalizes Windows root identity without granting access", () => {
    expect(project({ ...receipt(), root: "E:/WORK/A/" })).toMatchObject({ status: "reported" });
  });
  it("ignores unknown extensions and never retains raw capabilities or interaction", () => {
    const value = project({ ...receipt(), secret: "never-display", interaction: { policy: "claimed-safe" },
      capabilities: { arbitrary: "secret" } });
    expect(JSON.stringify(value)).not.toMatch(/secret|claimed-safe|interaction|capabilities|policyId|authorityId/);
  });
  it("does not invoke own/inherited getters", () => {
    const getter = vi.fn(() => receipt());
    const meta = Object.defineProperty({}, "neko.execution", { get: getter });
    expect(projectNekoExecutionReceipt({ _meta: meta }, task, capability)).toEqual({ status: "unknown" });
    expect(getter).not.toHaveBeenCalled();
    expect(project(Object.create(receipt()))).toEqual({ status: "unsupported" });
  });
  it("rejects oversized UTF8 backend paths without retaining payload", () => {
    expect(project({ ...receipt(), nativeBackend: { protocol: "neko-native-posix-v1",
      root: "中".repeat(12000), bashSandbox: "backend-enforced" } })).toEqual({ status: "unverified" });
  });
});
