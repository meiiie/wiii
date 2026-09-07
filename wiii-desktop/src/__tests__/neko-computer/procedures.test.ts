import { describe, expect, it } from "vitest";
import type { WorkPlaneDescriptor } from "@/neko-computer/contracts";
import { workPlaneProcedure } from "@/neko-computer/procedures";

function descriptor(maxInputBytes = 4_096): WorkPlaneDescriptor {
  return {
    protocolVersion: "wiii-work-plane.preview.v1",
    sourceAuthority: "source_application",
    resourceModel: "typed_revisioned_resources",
    transactionModel: "optimistic_idempotent",
    root: {
      ref: "work:project",
      resourceType: "project.root",
      name: "Project",
      parentRef: null,
      revision: `sha256:${"a".repeat(64)}`,
      mediaType: null,
      capabilities: ["project.file.create"],
      source: "project",
      metadata: {},
    },
    capabilities: [{
      id: "project.file.create",
      version: "1",
      resourceTypes: ["project.root"],
      inputSchema: {
        type: "object",
        required: ["content", "path"],
        properties: {
          content: { type: "string" },
          path: { type: "string" },
        },
      },
      mutating: true,
      risk: "reversible_local_edit",
      approval: "project_write_grant",
      retry: "idempotency_key_and_revision",
      reversible: true,
      maxInputBytes,
      evidence: ["file_hash_readback"],
    }],
  };
}

describe("Wiii Computer procedure fingerprints", () => {
  it("uses a bounded SHA-256 fingerprint", async () => {
    const procedure = await workPlaneProcedure(descriptor());
    expect(procedure?.compatibilityFingerprint).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it("invalidates a procedure when the capability contract drifts", async () => {
    const before = await workPlaneProcedure(descriptor(4_096));
    const after = await workPlaneProcedure(descriptor(8_192));
    expect(after?.compatibilityFingerprint).not.toBe(before?.compatibilityFingerprint);
  });

  it("is stable when JSON object key order changes", async () => {
    const left = descriptor();
    const right = descriptor();
    right.capabilities[0].inputSchema = {
      properties: {
        path: { type: "string" },
        content: { type: "string" },
      },
      required: ["content", "path"],
      type: "object",
    };
    expect((await workPlaneProcedure(right))?.compatibilityFingerprint)
      .toBe((await workPlaneProcedure(left))?.compatibilityFingerprint);
  });
});
