import { describe, expect, it } from "vitest";
import type { ComputerSemanticNode } from "@/neko-computer/contracts";
import {
  buildWorkstationManifest,
  workstationAppsFromSnapshot,
} from "@/neko-computer/workstation-manifest";

function launcher(
  appId: string,
  name: string,
  actions: ComputerSemanticNode["actions"] = ["invoke"],
): ComputerSemanticNode {
  return {
    ref: `app:${appId}`,
    parentRef: "workstation:main",
    appId,
    role: appId === "browser" ? "browser" : "application_launcher",
    name,
    description: null,
    value: null,
    states: ["enabled"],
    actions,
    bounds: null,
    sources: ["workstation"],
    version: `sha256:${appId}`,
  };
}

describe("Wiii workstation manifest", () => {
  it("projects the current allowlisted launcher catalog without provider details", () => {
    const apps = workstationAppsFromSnapshot([
      launcher("browser", "Trình duyệt", ["invoke", "set_text"]),
      launcher("wechat", "WeChat"),
      launcher("office", "Office"),
      { ...launcher("invalid app", "Ignored"), appId: "invalid app" },
      { ...launcher("window", "Ignored window"), role: "window" },
    ]);

    expect(apps.map((app) => app.appId)).toEqual([
      "browser",
      "terminal",
      "files",
      "wechat",
      "office",
    ]);
    expect(apps.find((app) => app.appId === "browser")?.actions).toEqual([
      "invoke",
      "set_text",
    ]);
    expect(JSON.stringify(apps)).not.toMatch(/container|docker|executable|path/i);
  });

  it("changes context identity when the installed app catalog changes", () => {
    const base = {
      operatingSystem: "Linux · Debian 12",
      projectName: "Wiii",
    };
    const core = buildWorkstationManifest(base);
    const withWeChat = buildWorkstationManifest({
      ...base,
      launcherNodes: [launcher("wechat", "WeChat")],
    });

    expect(core.contextVersion).not.toBe(withWeChat.contextVersion);
    expect(withWeChat.apps).toEqual([
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
    ]);
    expect(withWeChat.installedApps).toContainEqual({
      appId: "wechat",
      displayName: "WeChat",
      state: "available",
      actions: ["invoke"],
    });
  });

  it("keeps the v1 core projection compatible while extending the live catalog", () => {
    const manifest = buildWorkstationManifest({
      operatingSystem: "Linux · Debian 12",
      projectName: "Wiii",
      launcherNodes: [
        launcher("browser", "Trình duyệt", [
          "invoke",
          "set_text",
          "press_key",
          "input_sequence",
        ]),
        launcher("office", "Office"),
      ],
    });

    expect(manifest.apps).toHaveLength(3);
    expect(manifest.apps.every((app) =>
      ["browser", "terminal", "files"].includes(app.appId)
      && app.actions.every((action) => ["invoke", "focus"].includes(action))
    )).toBe(true);
    expect(manifest.installedApps).toEqual(expect.arrayContaining([
      expect.objectContaining({
        appId: "browser",
        actions: ["invoke", "set_text", "press_key", "input_sequence"],
      }),
      expect.objectContaining({ appId: "office" }),
    ]));
  });
});
