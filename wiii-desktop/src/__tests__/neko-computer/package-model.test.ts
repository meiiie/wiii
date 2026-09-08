import { describe, expect, it } from "vitest";
import type { ComputerDoctor, ComputerEnvironment } from "@/neko-computer/contracts";
import {
  computerPackUpdateSummary,
  coreComputerPackage,
  formatComputerBytes,
} from "@/neko-computer/package-model";

function doctor(): ComputerDoctor {
  return {
    supported: true,
    runtimeReady: true,
    packageReady: true,
    dockerCli: true,
    daemonReady: true,
    imageReady: true,
    providerKind: "local_docker",
    isolationClass: "shared_container",
    availableCpus: 8,
    availableMemoryBytes: 16 * 1024 ** 3,
    recommendedPreset: "balanced",
    packages: [{
      packageId: "web-computer-core",
      displayName: "Web Computer Core",
      description: "Desktop Linux cho Wiii",
      state: "installed",
      manifest: {
        schemaVersion: "wiii-computer-pack.v2",
        version: "semantic-v11",
        channel: "preview",
        aiFrameVersion: "wiii-ai-frame.v1",
        profileSchemaVersion: 1,
        upgradePolicy: "replace_shell_preserve_profile",
        rollbackPolicy: "automatic_shell_restore",
      },
      installedBytes: 1536 * 1024 ** 2,
      sharedAcrossProjects: true,
      preservesProfileOnRemove: true,
      capabilities: ["computer", "browser", "terminal", "files"],
    }],
    storage: {
      packageStoreKind: "runtime_managed_local",
      profileStoreKind: "durable_local",
      projectStoreKind: "host_source",
      locationSelectable: false,
    },
    detail: "ready",
  };
}

function environment(overrides: Partial<ComputerEnvironment> = {}): ComputerEnvironment {
  return {
    environmentId: "computer-neko",
    projectId: "project-1",
    projectName: "Project",
    projectPath: "C:\\Project",
    providerKind: "local_docker",
    isolationClass: "shared_container",
    computerKind: "web_computer",
    operatingSystem: "Linux · Debian 12",
    semanticProtocol: "neko-computer.semantic.v1",
    state: "ready",
    projectMount: "/workspace/project",
    attachUrl: "http://127.0.0.1/display",
    resources: {
      cpus: "2",
      memoryBytes: 4 * 1024 ** 3,
      pidsLimit: 320,
      sharedMemoryBytes: 1024 ** 3,
      temporaryStorageBytes: 4 * 1024 ** 3,
    },
    seat: {
      seatId: "display-0",
      state: "available",
      leaseId: null,
      ownerId: null,
      updatedAt: "2026-09-02T00:00:00Z",
    },
    createdAt: "2026-09-02T00:00:00Z",
    updatedAt: "2026-09-02T00:00:00Z",
    ...overrides,
  };
}

describe("Computer package presentation", () => {
  it("selects the provider-authoritative core package", () => {
    const core = coreComputerPackage(doctor());

    expect(core?.state).toBe("installed");
    expect(core?.sharedAcrossProjects).toBe(true);
    expect(core?.preservesProfileOnRemove).toBe(true);
    expect(core?.manifest).toMatchObject({
      version: "semantic-v11",
      channel: "preview",
      profileSchemaVersion: 1,
      rollbackPolicy: "automatic_shell_restore",
    });
  });

  it("formats exact provider bytes without claiming a size before installation", () => {
    expect(formatComputerBytes(1536 * 1024 ** 2)).toBe("1,5 GB");
    expect(formatComputerBytes(null)).toBe("Đang tính dung lượng");
  });

  it("distinguishes a pack upgrade from a paused computer", () => {
    const core = coreComputerPackage(doctor());

    expect(computerPackUpdateSummary(environment(), core)).toBeNull();
    expect(computerPackUpdateSummary(environment({
      state: "suspended",
      activePackVersion: "semantic-v10",
      packUpdateAvailable: true,
    }), core)).toEqual({
      activeVersion: "semantic-v10",
      targetVersion: "semantic-v11",
    });
  });

  it("uses honest fallback labels when an old provider cannot report its version", () => {
    expect(computerPackUpdateSummary(environment({
      state: "suspended",
      packUpdateAvailable: true,
    }), null)).toEqual({
      activeVersion: "gói cũ",
      targetVersion: "bản mới",
    });
  });
});
