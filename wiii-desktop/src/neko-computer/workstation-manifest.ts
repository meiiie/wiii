import type {
  ComputerSemanticNode,
  ComputerWorkstationApp,
  ComputerWorkstationManifest,
} from "./contracts";

export const WIII_WORKSTATION_MANIFEST_SCHEMA = "wiii-workstation.manifest.v1" as const;

const CORE_APPS: readonly ComputerWorkstationApp[] = [
  {
    appId: "browser",
    displayName: "Trình duyệt",
    state: "available",
    actions: ["invoke"],
  },
  {
    appId: "terminal",
    displayName: "Terminal",
    state: "available",
    actions: ["invoke"],
  },
  {
    appId: "files",
    displayName: "Tệp dự án",
    state: "available",
    actions: ["invoke"],
  },
];

const APP_ID = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const MAX_MANIFEST_APPS = 16;

export function workstationAppsFromSnapshot(
  nodes: readonly ComputerSemanticNode[] = [],
): ComputerWorkstationApp[] {
  const apps = new Map(CORE_APPS.map((app) => [app.appId, {
    ...app,
    actions: [...app.actions],
  }]));
  for (const node of nodes) {
    if (
      node.parentRef !== "workstation:main"
      || !node.appId
      || !APP_ID.test(node.appId)
      || !["browser", "application_launcher"].includes(node.role)
      || !node.actions.includes("invoke")
    ) {
      continue;
    }
    apps.set(node.appId, {
      appId: node.appId,
      displayName: node.name.slice(0, 80),
      state: "available",
      actions: [...node.actions],
    });
    if (apps.size >= MAX_MANIFEST_APPS) break;
  }
  return [...apps.values()];
}

function contextVersion(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return `ctx-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

export function buildWorkstationManifest(input: {
  operatingSystem: string;
  projectName: string;
  launcherNodes?: readonly ComputerSemanticNode[];
}): ComputerWorkstationManifest {
  const activeProjectLabel = input.projectName.trim() || "Project hiện tại";
  const operatingSystem = input.operatingSystem.trim() || "Linux";
  const surfaces = ["computer", "browser", "terminal", "files"] as const;
  const apps = CORE_APPS.map((app) => ({ ...app, actions: [...app.actions] }));
  const installedApps = workstationAppsFromSnapshot(input.launcherNodes);

  return {
    schemaVersion: WIII_WORKSTATION_MANIFEST_SCHEMA,
    contextVersion: contextVersion(JSON.stringify({
      activeProjectLabel,
      operatingSystem,
      surfaces,
      installedApps,
    })),
    label: "Máy tính công việc của Neko",
    coworkerName: "Neko",
    persistence: "durable",
    operatingSystem,
    interactionMode: "semantic",
    activeProjectLabel,
    surfaces: [...surfaces],
    apps,
    installedApps,
  };
}
