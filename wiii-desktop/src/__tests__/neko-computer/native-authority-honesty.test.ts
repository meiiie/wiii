import { afterEach, describe, expect, it, vi } from "vitest";

const tauri = vi.hoisted(() => ({ invoke: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke: tauri.invoke }));

import {
  assertNativeComputerAuthority,
  doctorComputer,
  installComputerPackage,
  NATIVE_COMPUTER_UNAVAILABLE_VI,
} from "@/neko-computer/client";

describe("native computer authority honesty", () => {
  afterEach(() => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    tauri.invoke.mockReset();
  });

  it("throws VI honesty instead of a raw invoke TypeError", async () => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    expect(() => assertNativeComputerAuthority()).toThrow(NATIVE_COMPUTER_UNAVAILABLE_VI);
    await expect(doctorComputer()).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    await expect(installComputerPackage()).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    expect(tauri.invoke).not.toHaveBeenCalled();
  });

  it("invokes when Tauri internals are present", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: {},
    });
    tauri.invoke.mockResolvedValue({ supported: true });
    await expect(doctorComputer()).resolves.toEqual({ supported: true });
    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_doctor");
  });
});
