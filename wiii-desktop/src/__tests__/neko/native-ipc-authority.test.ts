import { readFileSync } from "node:fs";
import { URL } from "node:url";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("native control IPC authority", () => {
  it("makes every invoked control command reachable through the declared local main-window boundary", () => {
    const client = source("../../neko/control-client.ts");
    const commands = [...client.matchAll(/"(neko_control_[a-z_]+)"/g)]
      .map(match => match[1]);
    expect(commands).toContain("neko_control_legacy_lease_recover");
    const build = source("../../../src-tauri/build.rs");
    const handler = source("../../../src-tauri/src/lib.rs");
    const capability = JSON.parse(source("../../../src-tauri/capabilities/workbench-agents.json"));
    expect(capability.windows).toEqual(["main"]);
    expect(capability.remote).toBeUndefined();
    for (const command of commands) {
      expect(build, `${command} must generate an app permission`).toContain(`"${command}"`);
      expect(handler, `${command} must be registered`).toContain(`commands::neko_agent::${command},`);
      expect(capability.permissions, `${command} must be allowed only by the local workbench capability`)
        .toContain(`allow-${command.replaceAll("_", "-")}`);
    }
  });
});
