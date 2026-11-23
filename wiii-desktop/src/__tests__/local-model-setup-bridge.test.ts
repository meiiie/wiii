import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { getLocalModelStatus, saveLocalModel } from "@/lib/local-model-setup";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
const original = Object.getOwnPropertyDescriptor(window, "__TAURI_INTERNALS__");
const draft = { presetId: "zai", model: "glm-5.3", apiKey: "unit-test-only-value" };

beforeEach(() => {
  vi.mocked(invoke).mockReset();
  Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
});
afterEach(() => {
  if (original) Object.defineProperty(window, "__TAURI_INTERNALS__", original);
  else Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
});

describe("local model credential boundary", () => {
  it("does not give a browser preview native configuration authority", async () => {
    await expect(getLocalModelStatus()).rejects.toThrow("chỉ có trong ứng dụng Wiii");
    await expect(saveLocalModel(draft)).rejects.toThrow("chỉ có trong ứng dụng Wiii");
    expect(invoke).not.toHaveBeenCalled();
  });

  it("uses the bounded native request and hides unexpected reflected IPC errors", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", { configurable: true, value: {} });
    vi.mocked(invoke).mockRejectedValueOnce(`unexpected parser detail ${draft.apiKey}`);
    let message = "";
    try { await saveLocalModel(draft); } catch (cause) { message = (cause as Error).message; }
    expect(invoke).toHaveBeenCalledWith("local_model_save", { request: draft });
    expect(message).toContain("cấu hình cũ vẫn được giữ");
    expect(message).not.toContain(draft.apiKey);
    expect(message).not.toContain("parser");
  });

  it("retains an actionable native validation error without adding credential content", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", { configurable: true, value: {} });
    const message = "Hãy nhập khóa API hợp lệ của nhà cung cấp.";
    vi.mocked(invoke).mockRejectedValueOnce(message);
    await expect(saveLocalModel(draft)).rejects.toThrow(message);
  });
});
