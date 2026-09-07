import { describe, expect, it } from "vitest";
import type {
  ComputerDisplaySeat,
  ComputerEnvironment,
  CoworkerComputerStatus,
} from "@/neko-computer/contracts";
import {
  computerProjectKey,
  projectStatesWithComputerSeat,
  projectStatesForCoworkerStatus,
  type ProjectComputerState,
} from "@/neko-computer/store";

function projectState(): ProjectComputerState {
  return {
    environment: null,
    semanticSnapshot: null,
    semanticError: null,
    loading: true,
    mutating: false,
    error: null,
  };
}

function environment(projectId: string, path: string): ComputerEnvironment {
  return {
    environmentId: "computer-neko",
    projectId,
    projectName: "Wiii",
    projectPath: path,
    providerKind: "local_docker",
    isolationClass: "shared_container",
    computerKind: "web_computer",
    operatingSystem: "Linux · Debian 12",
    semanticProtocol: "neko-computer.semantic.v1",
    state: "ready",
    projectMount: "/workspace/project",
    attachUrl: "http://127.0.0.1:4317",
    resources: {
      cpus: "2",
      memoryBytes: 4_294_967_296,
      pidsLimit: 320,
      sharedMemoryBytes: 536_870_912,
      temporaryStorageBytes: 4_294_967_296,
    },
    seat: {
      seatId: "seat-computer-neko",
      state: "available",
      leaseId: null,
      ownerId: null,
      updatedAt: "2026-08-27T00:00:00.000Z",
    },
    createdAt: "2026-08-27T00:00:00.000Z",
    updatedAt: "2026-08-27T00:00:00.000Z",
  };
}

function status(projectId: string | null, path: string | null): CoworkerComputerStatus {
  return {
    coworkerId: "wiii-coworker-neko",
    environmentId: "computer-neko",
    activeProjectId: projectId,
    activeProjectPath: path,
    environment: projectId && path ? environment(projectId, path) : null,
    grants: [],
  };
}

describe("coworker Computer Project projection", () => {
  it("uses ProjectId, not a Windows drive or namespace path, as identity", () => {
    const projectId = "project-wiii";
    const projected = projectStatesForCoworkerStatus(
      { [computerProjectKey(projectId)]: projectState() },
      status(projectId, "\\\\?\\D:\\Moved\\Wiii"),
      projectId,
    );

    expect(projected[projectId].environment?.projectPath).toBe(
      "\\\\?\\D:\\Moved\\Wiii",
    );
  });

  it("projects one durable workstation into only its active Project", () => {
    const projected = projectStatesForCoworkerStatus({
      "project-wiii": projectState(),
      "project-other": projectState(),
    }, status("project-wiii", "E:\\Projects\\Wiii"));

    expect(projected["project-wiii"].environment?.environmentId).toBe("computer-neko");
    expect(projected["project-other"].environment).toBeNull();
    expect(projected["project-wiii"].loading).toBe(false);
    expect(projected["project-other"].loading).toBe(false);
  });

  it("clears every Project surface when the active grant is revoked", () => {
    const previous = projectState();
    previous.environment = environment("project-wiii", "E:\\Projects\\Wiii");
    const projected = projectStatesForCoworkerStatus(
      { "project-wiii": previous },
      status(null, null),
    );

    expect(projected["project-wiii"].environment).toBeNull();
  });

  it("projects an agent lease into the active viewer without a status refresh", () => {
    const previous = projectState();
    previous.environment = environment("project-wiii", "E:\\Projects\\Wiii");
    const seat: ComputerDisplaySeat = {
      seatId: "seat-computer-neko",
      state: "agent_controlled",
      leaseId: "lease-agent",
      ownerId: "agent-session:session-1",
      updatedAt: "2026-08-28T06:00:00.000Z",
    };

    const projected = projectStatesWithComputerSeat(
      { "project-wiii": previous },
      "computer-neko",
      seat,
    );

    expect(projected["project-wiii"].environment?.seat).toEqual(seat);
  });
});
