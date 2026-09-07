import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NekoMenuBar } from "@/neko-chill/components/NekoMenuBar";
import { captureTextEditTarget, runTextEdit } from "@/neko-chill/text-edit-target";

const readText = vi.fn<() => Promise<string>>();
const writeText = vi.fn<(text: string) => Promise<void>>();
const execute = vi.fn();
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");

function setup(ready = true) {
  const actions = { onNewSession: vi.fn(), onCreateProject: vi.fn(), onSearch: vi.fn(),
    onToggleSidebar: vi.fn(), onToggleWorkspace: vi.fn(), onConnections: vi.fn() };
  const view = render(<div className="nk-root">
    <NekoMenuBar ready={ready} sidebarOpen workspaceOpen={false} workspaceAvailable={ready} {...actions} />
    <textarea aria-label="Bản nháp" defaultValue="Nội dung Wiii" /><textarea aria-label="Ô khác" />
    <iframe title="Computer cách ly" />
  </div>);
  const input = screen.getByRole("textbox", { name: "Bản nháp" }) as HTMLTextAreaElement;
  input.focus();
  input.setSelectionRange(0, 8);
  return { ...view, actions, input, root: view.container.firstElementChild! };
}

function openEdit() {
  const trigger = within(screen.getByRole("menubar")).getByRole("menuitem", { name: "Sửa" });
  fireEvent.pointerDown(trigger);
  fireEvent.click(trigger);
  return screen.getByRole("menu", { name: "Sửa" });
}

describe("application menu and local editing", () => {
  beforeEach(() => {
    readText.mockReset().mockResolvedValue("Văn bản mới");
    writeText.mockReset().mockResolvedValue(undefined);
    execute.mockReset().mockReturnValue(true);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { readText, writeText } });
    Object.defineProperty(document, "queryCommandSupported", { configurable: true, value: vi.fn(() => true) });
    Object.defineProperty(document, "queryCommandEnabled", { configurable: true, value: vi.fn(() => true) });
    Object.defineProperty(document, "execCommand", { configurable: true, value: execute });
  });
  afterEach(() => {
    if (originalClipboard) Object.defineProperty(navigator, "clipboard", originalClipboard);
    else Reflect.deleteProperty(navigator, "clipboard");
    Reflect.deleteProperty(document, "queryCommandSupported");
    Reflect.deleteProperty(document, "queryCommandEnabled");
    Reflect.deleteProperty(document, "execCommand");
  });

  it("routes real project/search/view actions without starting a task implicitly", () => {
    const { actions } = setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Tệp", exact: true }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Tạo Project…" }));
    expect(actions.onCreateProject).toHaveBeenCalledOnce();
    expect(actions.onNewSession).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("menuitem", { name: "Xem", exact: true }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: /Thanh bên/ }));
    expect(actions.onToggleSidebar).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("menuitem", { name: "Tệp", exact: true }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Tìm Project/ }));
    expect(actions.onSearch).toHaveBeenCalledOnce();
  });

  it("does not bypass hydration or workspace availability through a menu", () => {
    const { actions } = setup(false);
    fireEvent.click(screen.getByRole("menuitem", { name: "Tệp", exact: true }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Phiên mới" }));
    expect(actions.onNewSession).not.toHaveBeenCalled();
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: /Công cụ dự án/ }));
    expect(actions.onToggleWorkspace).not.toHaveBeenCalled();
  });

  it("supports F10, roving menus and two-step Escape back to the draft", () => {
    const { input } = setup();
    fireEvent.keyDown(window, { key: "F10" });
    expect(document.activeElement?.textContent).toBe("Tệp");
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    expect(document.activeElement?.textContent).toBe("Sửa");
    fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
    const menu = screen.getByRole("menu", { name: "Sửa" });
    expect(document.activeElement).toBe(within(menu).getAllByRole("menuitem")[0]);
    fireEvent.keyDown(document.activeElement!, { key: "End" });
    expect(document.activeElement).toBe(within(menu).getAllByRole("menuitem").at(-1));
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement?.textContent).toBe("Sửa");
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(document.activeElement).toBe(input);
    expect(input.value).toBe("Nội dung Wiii");
  });

  it("ignores IME and does not read the clipboard merely by opening Edit", () => {
    const { input } = setup();
    fireEvent.keyDown(window, { key: "F10", isComposing: true });
    expect(document.activeElement).toBe(input);
    openEdit();
    expect(readText).not.toHaveBeenCalled();
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("menuitem", { name: /Chọn tất cả/ }));
    expect(input.selectionEnd).toBe(input.value.length);
    expect(input.selectionStart).toBe(0);
  });

  it("opens the last menu item with ArrowUp after entering by Tab", () => {
    const { input } = setup();
    fireEvent.keyDown(input, { key: "Tab" });
    const trigger = screen.getByRole("menuitem", { name: "Sửa", exact: true });
    act(() => trigger.focus());
    fireEvent.keyDown(trigger, { key: "ArrowUp" });
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: /Chọn tất cả/ }));
    fireEvent.click(document.activeElement!);
    expect(document.activeElement).toBe(input);
    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe(input.value.length);
  });

  it("disables unsupported editing without reading the clipboard", () => {
    const { root } = setup();
    Reflect.deleteProperty(document, "execCommand");
    Reflect.deleteProperty(document, "queryCommandEnabled");
    const target = captureTextEditTarget(root)!;
    expect(target.enabled).toEqual({ undo: false, redo: false, cut: false,
      copy: true, paste: false, selectAll: true });
    expect(readText).not.toHaveBeenCalled();
  });

  it("copies only the selected text and preserves the field", async () => {
    const { input } = setup();
    openEdit();
    fireEvent.click(screen.getByRole("menuitem", { name: /Sao chép/ }));
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith("Nội dung"));
    expect(input.value).toBe("Nội dung Wiii");
    expect(execute).not.toHaveBeenCalled();
  });

  it("does not delete text when clipboard permission fails", async () => {
    setup();
    writeText.mockRejectedValueOnce(new Error("Clipboard bị từ chối"));
    openEdit();
    fireEvent.click(screen.getByRole("menuitem", { name: /Cắt/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("Clipboard bị từ chối");
    expect(execute).not.toHaveBeenCalled();
  });

  it.each(["value", "focus", "selection", "removed"])("rejects a pending paste after %s changes", async (change) => {
    const { input, root } = setup();
    let resolve!: (value: string) => void;
    readText.mockReturnValueOnce(new Promise<string>((done) => { resolve = done; }));
    const target = captureTextEditTarget(root)!;
    const pending = runTextEdit("paste", target);
    if (change === "value") input.value = "Bản nháp mới";
    if (change === "focus") screen.getByRole("textbox", { name: "Ô khác" }).focus();
    if (change === "selection") input.setSelectionRange(3, 3);
    if (change === "removed") input.remove();
    resolve("Không được chèn nhầm");
    await expect(pending).rejects.toThrow(/đã đổi/);
    expect(execute).not.toHaveBeenCalled();
  });

  it("never targets the Computer iframe or editor-owned history", () => {
    const { root, input } = setup();
    screen.getByTitle("Computer cách ly").focus();
    expect(captureTextEditTarget(root)).toBeNull();
    input.parentElement!.classList.add("monaco-editor");
    input.focus();
    expect(captureTextEditTarget(root)).toBeNull();
  });

  it("pastes through the undo-preserving adapter and reports unsupported operations", async () => {
    setup();
    openEdit();
    await act(async () => { fireEvent.click(screen.getByRole("menuitem", { name: /Dán/ })); });
    expect(execute).toHaveBeenCalledWith("insertText", false, "Văn bản mới");
    execute.mockReturnValueOnce(false);
    openEdit();
    fireEvent.click(screen.getByRole("menuitem", { name: /Hoàn tác/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("chưa hỗ trợ");
  });
});
