import { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLocalModelStatus, saveLocalModel } from "@/lib/local-model-setup";
import { LocalModelSetupDialog } from "@/neko-chill/components/LocalModelSetupDialog";

vi.mock("@/lib/local-model-setup", () => ({ getLocalModelStatus: vi.fn(), saveLocalModel: vi.fn() }));
const presets = [
  { id: "zai", label: "GLM Coding Plan", provider: "anthropic", baseUrl: "https://api.z.ai/api/anthropic", model: "glm-5.3", requiresKey: true, customEndpoint: false },
  { id: "custom", label: "Máy chủ khác", provider: "openai_compat", baseUrl: "http://127.0.0.1:11434/v1", model: "", requiresKey: false, customEndpoint: true },
];
const saved = { profileId: "zai", model: "glm-5.3", provider: "anthropic" };
const onSaved = vi.fn();

function setup() {
  function Harness() {
    const [open, setOpen] = useState(false);
    return <><button onClick={() => setOpen(true)}>Mở thiết lập</button>{open ? <LocalModelSetupDialog onClose={() => setOpen(false)} onSaved={(value) => { onSaved(value); setOpen(false); }} /> : null}</>;
  }
  render(<Harness />);
  const opener = screen.getByRole("button", { name: "Mở thiết lập" });
  opener.focus();
  fireEvent.click(opener);
  return opener;
}

beforeEach(() => {
  vi.mocked(getLocalModelStatus).mockReset().mockResolvedValue({ configured: false, presets });
  vi.mocked(saveLocalModel).mockReset().mockResolvedValue(saved);
  onSaved.mockReset();
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(function () { this.setAttribute("open", ""); });
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function () { this.removeAttribute("open"); });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("first-use local model setup", () => {
  it("masks an ephemeral key and cancels back to the opener without saving", async () => {
    const persist = vi.spyOn(Storage.prototype, "setItem");
    const opener = setup();
    const key = await screen.findByLabelText(/^Khóa API/);
    expect(key.getAttribute("type")).toBe("password");
    fireEvent.change(key, { target: { value: "unit-test-only-value" } });
    expect(persist).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Hủy" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(saveLocalModel).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(opener);
    fireEvent.click(opener);
    expect((await screen.findByLabelText(/^Khóa API/) as HTMLInputElement).value).toBe("");
  });

  it("requires a key for the provider and clears it when changing endpoint ownership", async () => {
    setup();
    const provider = await screen.findByRole("combobox", { name: /^Nhà cung cấp/ });
    fireEvent.click(screen.getByRole("button", { name: "Lưu mô hình" }));
    expect(screen.getByRole("alert").textContent).toContain("Hãy nhập khóa API");
    expect(saveLocalModel).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/^Khóa API/), { target: { value: "unit-test-only-value" } });
    fireEvent.change(provider, { target: { value: "custom" } });
    expect((screen.getByLabelText(/^Khóa API/) as HTMLInputElement).value).toBe("");
    fireEvent.change(screen.getByLabelText(/^Khóa API/), { target: { value: "another-unit-value" } });
    fireEvent.change(screen.getByLabelText(/^Địa chỉ máy chủ/), { target: { value: "http://localhost:1234/v1" } });
    expect((screen.getByLabelText(/^Khóa API/) as HTMLInputElement).value).toBe("");
    fireEvent.change(screen.getByRole("textbox", { name: "Mã mô hình" }), { target: { value: "local-model" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Lưu mô hình" })); });
    expect(saveLocalModel).toHaveBeenCalledWith({ presetId: "custom", model: "local-model", baseUrl: "http://localhost:1234/v1", apiKey: "" });
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("retains correctable fields after save failure and retries without a model call", async () => {
    vi.mocked(saveLocalModel).mockRejectedValueOnce(new Error("Chưa lưu được mô hình. Hãy thử lại."));
    setup();
    const key = await screen.findByLabelText(/^Khóa API/) as HTMLInputElement;
    fireEvent.change(key, { target: { value: "unit-test-only-value" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Lưu mô hình" })); });
    expect(screen.getByRole("alert").textContent).toContain("Hãy thử lại");
    expect(key.value).toBe("unit-test-only-value");
    expect(onSaved).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Lưu mô hình" })); });
    expect(onSaved).toHaveBeenCalledWith(saved);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getLocalModelStatus).toHaveBeenCalledOnce();
    expect(saveLocalModel).toHaveBeenCalledTimes(2);
  });

  it("keeps pending writes single-flight and blocks cancellation only while saving", async () => {
    let finish!: (value: typeof saved) => void;
    vi.mocked(saveLocalModel).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    setup();
    fireEvent.change(await screen.findByLabelText(/^Khóa API/), { target: { value: "unit-test-only-value" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu mô hình" }));
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: false, cancelable: true }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(saveLocalModel).toHaveBeenCalledOnce();
    await act(async () => { finish(saved); });
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("retries an unavailable native status read without losing the setup route", async () => {
    vi.mocked(getLocalModelStatus).mockRejectedValueOnce(new Error("Chưa đọc được cấu hình mô hình."));
    setup();
    await screen.findByRole("button", { name: "Thử lại" });
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await screen.findByLabelText(/^Khóa API/);
    expect(getLocalModelStatus).toHaveBeenCalledTimes(2);
    expect(saveLocalModel).not.toHaveBeenCalled();
  });
});

describe("Linux native model setup keyboard boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("Linux x86_64");
    // jsdom has no layout or native Tab default; only model rendered visibility.
    vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(function () {
      return [new DOMRect(0, 0, 30, 20)] as unknown as DOMRectList;
    });
  });

  function tab(target: HTMLElement, init: KeyboardEventInit = {}) {
    const event = new KeyboardEvent("keydown", { key: "Tab", code: "Tab", bubbles: true, cancelable: true, ...init });
    fireEvent(target, event);
    return event;
  }

  it.each(["Tab", "Unidentified"])("keeps both edges inside the modal for %s, preserving fields and Escape return", async (key) => {
    const opener = setup();
    const provider = await screen.findByRole("combobox", { name: /^Nhà cung cấp/ });
    const model = screen.getByRole<HTMLInputElement>("textbox", { name: "Mã mô hình" });
    const apiKey = screen.getByLabelText<HTMLInputElement>(/^Khóa API/);
    fireEvent.change(apiKey, { target: { value: "unit-test-only-value" } });
    expect(document.activeElement).toBe(provider);
    const first = screen.getByRole("button", { name: "Đóng thiết lập mô hình" });
    const last = screen.getByRole("button", { name: "Lưu mô hình" });
    for (let cycle = 0; cycle < 2; cycle += 1) {
      last.focus();
      expect(tab(last, { key, keyCode: 9 }).defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(first);
      expect(tab(first, { key, keyCode: 9, shiftKey: true }).defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(last);
    }
    expect(model.value).toBe(presets[0].model);
    expect(apiKey.value).toBe("unit-test-only-value");
    expect(saveLocalModel).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("leaves inner ordering, modified shortcuts and child-prevented keys alone", async () => {
    setup();
    const provider = await screen.findByRole("combobox", { name: /^Nhà cung cấp/ });
    expect(tab(provider).defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(provider);
    const last = screen.getByRole("button", { name: "Lưu mô hình" });
    last.focus();
    expect(tab(last, { altKey: true }).defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(last);
    last.addEventListener("keydown", (event) => event.preventDefault(), { once: true });
    expect(tab(last).defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(last);
  });

  it("uses the current controls after a failed status read is retried", async () => {
    vi.mocked(getLocalModelStatus).mockRejectedValueOnce(new Error("Chưa đọc được cấu hình mô hình."));
    setup();
    const retry = await screen.findByRole("button", { name: "Thử lại" });
    const first = screen.getByRole("button", { name: "Đóng thiết lập mô hình" });
    retry.focus();
    tab(retry);
    expect(document.activeElement).toBe(first);
    tab(first, { key: "Unidentified", keyCode: 9, shiftKey: true });
    expect(document.activeElement).toBe(retry);
    fireEvent.click(retry);
    await screen.findByLabelText(/^Khóa API/);
    first.focus();
    tab(first, { key: "Unidentified", keyCode: 9, shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Lưu mô hình" }));
    expect(saveLocalModel).not.toHaveBeenCalled();
  });

  it.each(["MacIntel", "Win32", "Linux browser"])("keeps %s on its native keyboard policy", async (platform) => {
    if (platform === "Linux browser") vi.unstubAllGlobals();
    else vi.spyOn(window.navigator, "platform", "get").mockReturnValue(platform);
    setup();
    await screen.findByRole("combobox", { name: /^Nhà cung cấp/ });
    const first = screen.getByRole("button", { name: "Đóng thiết lập mô hình" });
    const last = screen.getByRole("button", { name: "Lưu mô hình" });
    last.focus();
    expect(tab(last).defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(last);
    first.focus();
    expect(tab(first, { key: "Unidentified", shiftKey: true }).defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(first);
  });
});
