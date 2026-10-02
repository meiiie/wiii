import { describe, expect, it, vi } from "vitest";
import {
  NEKO_TASK_PROTOCOL, NekoTaskProtocolError,
  assertNekoTaskCapability, assertNekoTaskCurrentReceipt, assertNekoTaskEventBinding,
  buildNekoTaskEchoMeta, buildNekoTaskLoadMeta, buildNekoTaskNewMeta,
  canonicalRootIdentity, canonicalRootsEqual,
  classifyFixedTaskCommand, parseNekoTaskReceipt, parseNekoTaskRecoveryError,
  validateNekoTaskLoadReceipt, validateNekoTaskNewReceipt,
  type NekoTaskReceipt, type NekoTaskProtocolFailure,
} from "@/neko-chill/drivers/acp/task-protocol";

const root = "E:\\MeiiieGroup\\integration-tests\\scope-fixture";
const sessionId = "canonical-session";
const receipt: NekoTaskReceipt = Object.freeze({ version: 1, mode: "fixed-active-task",
  id: "canonical-task", label: "Sửa lỗi riêng", root, activationEpoch: 1, activationId: "activation-one" });
function envelope(value: unknown = receipt, ...ids: unknown[]) {
  return { sessionId: ids.length ? ids[0] : sessionId, _meta: { "neko.task": value } };
}
function loaded(overrides: Partial<NekoTaskReceipt> = {}) {
  return envelope({ ...receipt, activationEpoch: 2, activationId: "activation-two", ...overrides });
}
const loadExpected = { sessionId, authorizedRoot: root, expected: receipt };
function fails(run: () => unknown, reason: NekoTaskProtocolFailure) {
  try { run(); throw new Error("Expected a task protocol failure"); }
  catch (error) {
    expect(error).toBeInstanceOf(NekoTaskProtocolError);
    expect((error as NekoTaskProtocolError).reason).toBe(reason);
  }
}

describe("Neko task protocol v1 capability and metadata", () => {
  it("requires negotiated ACP v1 plus the explicit extension capability", () => {
    expect(assertNekoTaskCapability({ protocolVersion: 1, _meta: {
      "neko.taskProtocol": { ...NEKO_TASK_PROTOCOL, future: "ignored" },
    } })).toBe(NEKO_TASK_PROTOCOL);
  });
  it.each([{}, { protocolVersion: 1 }, { protocolVersion: 1, _meta: {} },
    { protocolVersion: 1, agentCapabilities: { "neko.taskProtocol": NEKO_TASK_PROTOCOL } }])(
    "does not infer capability from absent/misplaced fields: %j", result => {
      fails(() => assertNekoTaskCapability(result), "missing-capability");
    });
  it.each([null, [], { version: 2, mode: "fixed-active-task" }, { version: 1, mode: "switchable" },
    { version: "1", mode: "fixed-active-task" }])("rejects unsupported advertised capability: %j", capability => {
    fails(() => assertNekoTaskCapability({ protocolVersion: 1, _meta: { "neko.taskProtocol": capability } }), "unsupported-capability");
  });
  it("rejects a different ACP version even if the extension is v1", () => {
    fails(() => assertNekoTaskCapability({ protocolVersion: 2, _meta: { "neko.taskProtocol": NEKO_TASK_PROTOCOL } }), "unsupported-capability");
  });
  it("uses exactly the new/load/turn opt-in shapes without copying receipts into turn echoes", () => {
    expect(buildNekoTaskNewMeta(receipt.label)).toEqual({
      "neko.taskProtocol": NEKO_TASK_PROTOCOL, "neko.taskLabel": receipt.label,
    });
    expect(buildNekoTaskLoadMeta(receipt)).toEqual({ "neko.taskProtocol": NEKO_TASK_PROTOCOL, "neko.taskExpected": {
      id: receipt.id, root, activationEpoch: 1, activationId: receipt.activationId,
    } });
    expect(buildNekoTaskEchoMeta(receipt)).toEqual({ "neko.task": {
      version: 1, id: receipt.id, activationEpoch: 1, activationId: receipt.activationId,
    } });
  });
  it("bounds labels by UTF-8 bytes while preserving Vietnamese/CJK and exact display text", () => {
    expect(buildNekoTaskNewMeta("  Sửa lỗi 日本語  ")["neko.taskLabel"]).toBe("  Sửa lỗi 日本語  ");
    expect(buildNekoTaskNewMeta("a".repeat(256))["neko.taskLabel"]).toHaveLength(256);
    expect(buildNekoTaskNewMeta("界".repeat(85))["neko.taskLabel"]).toHaveLength(85);
    for (const label of ["", "   ", "a\nlabel", "label\u0000", "a".repeat(257), "界".repeat(86)]) {
      fails(() => buildNekoTaskNewMeta(label), "invalid-label");
    }
  });
});

describe("Neko full task receipt parsing and new admission", () => {
  it("returns a copied frozen receipt and ignores unrelated extension fields", () => {
    const wire = { ...receipt, secretUnrecognizedField: { neverRetained: "opaque" } };
    const parsed = parseNekoTaskReceipt(envelope(wire));
    expect(parsed).toEqual(receipt);
    expect(parsed).not.toBe(wire);
    expect(Object.isFrozen(parsed)).toBe(true);
    expect(Object.keys(parsed)).not.toContain("secretUnrecognizedField");
  });
  it.each([undefined, null, [], {}, { _meta: {} }, { "neko.task": receipt }])(
    "does not infer an absent outer receipt: %j", value => {
      fails(() => parseNekoTaskReceipt(value), "missing-receipt");
    });
  it.each([
    ["version", 2], ["version", "1"], ["mode", "switchable"], ["id", ""], ["id", 7],
    ["id", "a".repeat(257)], ["label", "\t"], ["label", "界".repeat(86)],
    ["root", ""], ["root", "root\u0000"], ["root", "r".repeat(32769)],
    ["activationEpoch", 0], ["activationEpoch", -1], ["activationEpoch", 1.5],
    ["activationEpoch", "1"], ["activationEpoch", Number.MAX_SAFE_INTEGER + 1],
    ["activationEpoch", NaN], ["activationId", null], ["activationId", "a".repeat(257)],
  ])("rejects malformed receipt field %s", (field, value) => {
    fails(() => parseNekoTaskReceipt(envelope({ ...receipt, [field as string]: value })), "invalid-receipt");
  });
  it("requires every receipt field even for the current activation", () => {
    for (const field of Object.keys(receipt)) {
      const partial = { ...receipt } as Record<string, unknown>;
      delete partial[field];
      fails(() => parseNekoTaskReceipt(envelope(partial)), "invalid-receipt");
    }
  });
  it("does not execute accessors or accept inherited receipt fields", () => {
    const getter = vi.fn(() => receipt);
    const meta = Object.defineProperty({}, "neko.task", { get: getter });
    fails(() => parseNekoTaskReceipt({ _meta: meta }), "missing-receipt");
    expect(getter).not.toHaveBeenCalled();
    fails(() => parseNekoTaskReceipt(envelope(Object.create(receipt))), "invalid-receipt");
  });
  it("binds new admission to the exact authorized root, label and initial activation", () => {
    expect(validateNekoTaskNewReceipt(envelope(), { authorizedRoot: root, label: receipt.label })).toEqual({ sessionId, receipt });
    fails(() => validateNekoTaskNewReceipt(envelope(), { authorizedRoot: root + "-other", label: receipt.label }), "root-mismatch");
    fails(() => validateNekoTaskNewReceipt(envelope(), { authorizedRoot: root, label: "Different" }), "label-mismatch");
    fails(() => validateNekoTaskNewReceipt(loaded(), { authorizedRoot: root, label: receipt.label }), "activation-mismatch");
  });
  it("compares proven Windows roots by native identity without resolving parents or aliases", () => {
    for (const authorizedRoot of [root.toLowerCase(), root.replaceAll("\\", "/"), root + "\\", "\\\\?\\" + root]) {
      expect(validateNekoTaskNewReceipt(envelope(), { authorizedRoot, label: receipt.label }).receipt.root).toBe(root);
    }
    for (const authorizedRoot of [root + "\\..", root + "-sibling", "E:\\another-alias", "/posix/path"]) {
      fails(() => validateNekoTaskNewReceipt(envelope(), { authorizedRoot, label: receipt.label }), "root-mismatch");
    }
  });
  it("preserves POSIX case and does not turn relative drive paths into absolute roots", () => {
    expect(canonicalRootIdentity("/Home/User/Project")).toBe("/Home/User/Project");
    expect(canonicalRootsEqual("/Home/User/Project", "/home/user/project")).toBe(false);
    expect(canonicalRootsEqual("/Home/User/Project/", "/Home/User/Project")).toBe(false);
    expect(canonicalRootIdentity("E:\\")).toBe("e:\\");
    expect(canonicalRootsEqual("E:", "E:\\")).toBe(false);
    expect(canonicalRootsEqual("E:/", "E:\\")).toBe(true);
  });
  it("handles already-proven canonical Windows UNC roots and verbatim UNC aliases", () => {
    expect(canonicalRootIdentity("\\\\?\\UNC\\Server\\Share\\Project\\")).toBe("\\\\server\\share\\project");
    expect(canonicalRootsEqual("//server/share/project", "\\\\Server\\Share\\Project")).toBe(true);
    expect(canonicalRootsEqual("\\\\server\\other-share\\project", "\\\\Server\\Share\\Project")).toBe(false);
    // A forward-slash POSIX root is not itself proof that the host is Windows.
    expect(canonicalRootIdentity("//Server/Share/Project")).toBe("//Server/Share/Project");
  });
  it.each([undefined, null, "", " ", [], 1, "s".repeat(257), "id\nvalue"])(
    "rejects invalid returned sessionId: %j", id => {
      fails(() => validateNekoTaskNewReceipt(envelope(receipt, id), { authorizedRoot: root, label: receipt.label }), "invalid-session-id");
    });
  it("keeps task, activation and coordinator IDs distinct", () => {
    fails(() => parseNekoTaskReceipt(envelope({ ...receipt, activationId: receipt.id })), "identity-collision");
    for (const id of [receipt.id, receipt.activationId]) {
      fails(() => validateNekoTaskNewReceipt(envelope(receipt, id), { authorizedRoot: root, label: receipt.label }), "identity-collision");
    }
  });
});

describe("Neko load activation and full current receipt validation", () => {
  it("binds the requested coordinator for the actual ACP load/resume shape without result.sessionId", () => {
    const result = { _meta: loaded()._meta };
    expect(validateNekoTaskLoadReceipt(result, loadExpected)).toEqual({
      sessionId, receipt: { ...receipt, activationEpoch: 2, activationId: "activation-two" },
    });
    fails(() => validateNekoTaskNewReceipt({ _meta: envelope()._meta }, {
      authorizedRoot: root, label: receipt.label,
    }), "invalid-session-id");
  });
  it.each([undefined, null, "", 1, [], "id\nvalue"])(
    "rejects an explicitly malformed load response ID rather than treating it as omitted: %j", id => {
      fails(() => validateNekoTaskLoadReceipt({ ...loaded(), sessionId: id }, loadExpected), "invalid-session-id");
    });
  it("does not execute an accessor in a returned coordinator ID", () => {
    const getter = vi.fn(() => sessionId);
    const result = Object.defineProperty({ _meta: loaded()._meta }, "sessionId", { get: getter });
    fails(() => validateNekoTaskLoadReceipt(result, loadExpected), "invalid-session-id");
    expect(getter).not.toHaveBeenCalled();
  });
  it("accepts only a fresh next activation for the same coordinator/task/root/label", () => {
    expect(validateNekoTaskLoadReceipt(loaded(), loadExpected).receipt.activationEpoch).toBe(2);
    fails(() => validateNekoTaskLoadReceipt({ ...loaded(), sessionId: "other-session" }, loadExpected), "session-mismatch");
    fails(() => validateNekoTaskLoadReceipt(loaded({ id: "other-task" }), loadExpected), "task-mismatch");
    fails(() => validateNekoTaskLoadReceipt(loaded({ root: root + "-other" }), loadExpected), "root-mismatch");
    fails(() => validateNekoTaskLoadReceipt(loaded({ label: "Other" }), loadExpected), "label-mismatch");
    fails(() => validateNekoTaskLoadReceipt(loaded(), { ...loadExpected, authorizedRoot: root + "-other" }), "root-mismatch");
  });
  it.each([1, 3, 4, 99])("rejects stale or arbitrarily skipped load epoch %i", activationEpoch => {
    fails(() => validateNekoTaskLoadReceipt(loaded({ activationEpoch }), loadExpected), "activation-mismatch");
  });
  it("requires a changed activation ID and prevents epoch overflow", () => {
    fails(() => validateNekoTaskLoadReceipt(loaded({ activationId: receipt.activationId }), loadExpected), "activation-mismatch");
    const last = { ...receipt, activationEpoch: Number.MAX_SAFE_INTEGER };
    fails(() => validateNekoTaskLoadReceipt(envelope({ ...last, activationId: "new" }), { ...loadExpected, expected: last }), "activation-mismatch");
  });
  it("allows exactly one skipped activation only with explicit retry validation and the matching marker", () => {
    const retry = { ...loaded({ activationEpoch: 3 }), _meta: {
      "neko.task": { ...receipt, activationEpoch: 3, activationId: "activation-three" },
      "neko.taskRecovery": { version: 1, kind: "prior_receipt_retry" },
    } };
    fails(() => validateNekoTaskLoadReceipt(retry, loadExpected), "activation-mismatch");
    expect(validateNekoTaskLoadReceipt(retry, { ...loadExpected, allowPriorReceiptRetry: true }).receipt.activationEpoch).toBe(3);
    fails(() => validateNekoTaskLoadReceipt(loaded({ activationEpoch: 3 }), { ...loadExpected, allowPriorReceiptRetry: true }), "activation-mismatch");
    for (const marker of [{ version: 2, kind: "prior_receipt_retry" }, { version: 1, kind: "auto_recover" }, {}]) {
      fails(() => validateNekoTaskLoadReceipt({ ...retry, _meta: { ...retry._meta, "neko.taskRecovery": marker } },
        { ...loadExpected, allowPriorReceiptRetry: true }), "activation-mismatch");
    }
    fails(() => validateNekoTaskLoadReceipt({ ...retry, _meta: { ...retry._meta, "neko.task": {
      ...receipt, activationEpoch: 4, activationId: "activation-four",
    } } }, { ...loadExpected, allowPriorReceiptRetry: true }), "activation-mismatch");
  });
  it("validates successful prompt/close receipts without inventing a response sessionId", () => {
    expect(assertNekoTaskCurrentReceipt({ stopReason: "end_turn", _meta: { "neko.task": receipt } }, receipt)).toEqual(receipt);
    expect(assertNekoTaskCurrentReceipt({ _meta: { "neko.task": receipt } }, receipt)).toEqual(receipt);
    fails(() => assertNekoTaskCurrentReceipt({ stopReason: "end_turn" }, receipt), "missing-receipt");
  });
  it.each([
    ["root", root + "-other", "root-mismatch"], ["id", "foreign-task", "task-mismatch"],
    ["label", "Changed", "label-mismatch"], ["activationEpoch", 2, "activation-mismatch"],
    ["activationId", "stale-activation", "activation-mismatch"],
  ])("requires the exact full current %s", (field, value, reason) => {
    fails(() => assertNekoTaskCurrentReceipt(envelope({ ...receipt, [field]: value }), receipt), reason as NekoTaskProtocolFailure);
  });
  it("requires outer wire session identity as well as the receipt for updates and permissions", () => {
    expect(assertNekoTaskEventBinding(envelope(), sessionId, receipt)).toEqual(receipt);
    fails(() => assertNekoTaskEventBinding(envelope(receipt, "other-session"), sessionId, receipt), "session-mismatch");
    fails(() => assertNekoTaskEventBinding(envelope(receipt, undefined), sessionId, receipt), "invalid-session-id");
    fails(() => assertNekoTaskEventBinding(envelope({ ...receipt, activationId: "previous-process" }), sessionId, receipt), "activation-mismatch");
    fails(() => assertNekoTaskEventBinding({ sessionId, update: { _meta: { "neko.task": receipt } } }, sessionId, receipt), "missing-receipt");
  });
});

describe("Neko typed recovery and fixed task commands", () => {
  it.each(["writer_unavailable", "recovery_required"] as const)("retains only a supported %s recovery field", kind => {
    const value = parseNekoTaskRecoveryError(-32002, { "neko.taskError": {
      version: 1, kind, action: "retain_mapping_and_request_recovery", untrustedExtra: "never retained",
    }, body: "never retained" });
    expect(value).toEqual({ version: 1, kind, action: "retain_mapping_and_request_recovery" });
    expect(Object.isFrozen(value)).toBe(true);
  });
  it.each([
    [-32603, { version: 1, kind: "recovery_required", action: "retain_mapping_and_request_recovery" }],
    ["-32002", { version: 1, kind: "recovery_required", action: "retain_mapping_and_request_recovery" }],
    [-32002, { version: 2, kind: "recovery_required", action: "retain_mapping_and_request_recovery" }],
    [-32002, { version: 1, kind: "session_not_found", action: "retain_mapping_and_request_recovery" }],
    [-32002, { version: 1, kind: "recovery_required", action: "delete_lock_and_retry" }],
    [-32002, null], [-32002, {}],
  ])("keeps unknown/malformed errors on the regular fault path", (code, taskError) => {
    expect(parseNekoTaskRecoveryError(code, { "neko.taskError": taskError })).toBeUndefined();
  });
  it("does not infer recovery from -32002 alone or execute data getters", () => {
    expect(parseNekoTaskRecoveryError(-32002, undefined)).toBeUndefined();
    const getter = vi.fn();
    expect(parseNekoTaskRecoveryError(-32002, Object.defineProperty({}, "neko.taskError", { get: getter }))).toBeUndefined();
    expect(getter).not.toHaveBeenCalled();
  });
  it.each(["/task new", "/task new another item", " \n/task\tnew\tlabel ", "/task use id", "/task\nuse\nopaque"])(
    "classifies the fixed-lane switching command %j", text => {
      expect(classifyFixedTaskCommand(text, true)).toMatch(/^(new|use)$/);
      expect(classifyFixedTaskCommand(text, false)).toBeUndefined();
    });
  it.each(["/task", "/task status", "/task list", "/task newer", "/task useless", "/tasks new", "/TASK new", "Please /task new item", "`/task use id`"])(
    "preserves read-only commands, prose and other providers: %j", text => {
      expect(classifyFixedTaskCommand(text, true)).toBeUndefined();
    });
});
