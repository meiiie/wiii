import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChillCatalogPicker } from "@/neko-chill/components/ChillCatalogPicker";
import { NekoComposer } from "@/neko-chill/components/NekoComposer";
import { clearNekoComposerDraft, readNekoComposerDraft } from "@/neko-chill/composer-drafts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

describe("ChillCatalogPicker", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  const items = [
    { id: "neko", label: "Neko Core", group: "Harness trên máy" },
    { id: "gemini", label: "Gemini CLI", group: "Harness trên máy" },
    { id: "missing", label: "Missing", group: "Harness trên máy", disabled: true, title: "Chưa sẵn sàng" },
  ];

  function mountInPanel(bounds: () => DOMRect, anchor: DOMRect) {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute("data-panel") ? bounds() : anchor;
    });
    render(<div data-panel=""><ChillCatalogPicker items={items} value="neko" onChange={vi.fn()} ariaLabel="Catalog" testId="bounded-picker" /></div>);
    fireEvent.click(screen.getByRole("button", { name: "Catalog" }));
    return screen.getByTestId("bounded-picker-menu");
  }

  it.each([
    [new DOMRect(292, 90, 258, 410), new DOMRect(450, 460, 80, 20)],
    [new DOMRect(292, 300, 308, 350), new DOMRect(500, 330, 70, 20)],
  ])("keeps search/reset inside the containing panel, case %#", (bounds, anchor) => {
    const menu = mountInPanel(() => bounds, anchor);
    const left = anchor.left + parseFloat(menu.style.left);
    const width = parseFloat(menu.style.width);
    const height = parseFloat(menu.style.maxHeight);
    const top = menu.style.top ? anchor.bottom + 4 : anchor.top - 4 - height;
    expect(left).toBeGreaterThanOrEqual(bounds.left + 12);
    expect(left + width).toBeLessThanOrEqual(bounds.right - 12);
    expect(top).toBeGreaterThanOrEqual(bounds.top + 12);
    expect(top + height).toBeLessThanOrEqual(bounds.bottom - 12);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "gem" } });
    fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
    expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("");
  });

  it("refits an open catalog when only its split panel resizes", () => {
    let resize = () => {};
    vi.stubGlobal("ResizeObserver", class {
      constructor(callback: () => void) { resize = callback; }
      observe() {}
      disconnect() {}
    });
    let bounds = new DOMRect(292, 90, 600, 510);
    const anchor = new DOMRect(450, 460, 80, 20);
    const menu = mountInPanel(() => bounds, anchor);
    bounds = new DOMRect(292, 90, 258, 510);
    act(() => resize()); // No window resize: divider/sidebar changed only the panel.
    expect(anchor.left + parseFloat(menu.style.left) + parseFloat(menu.style.width)).toBeLessThanOrEqual(bounds.right - 12);
  });

  it("filters by search and selects with keyboard", () => {
    const onChange = vi.fn();
    render(
      <ChillCatalogPicker
        items={items}
        value="neko"
        onChange={onChange}
        ariaLabel="Chọn Harness"
        searchPlaceholder="Tìm harness…"
        testId="picker"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Chọn Harness" }));
    expect(screen.getByTestId("picker-menu")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Tìm harness…"), { target: { value: "gem" } });
    expect(screen.getByRole("option", { name: /Gemini CLI/i })).toBeTruthy();
    expect(screen.queryByRole("option", { name: /Neko Core/i })).toBeNull();
    fireEvent.keyDown(screen.getByTestId("picker-menu"), { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("gemini");
  });

  it("shows empty state and keeps disabled options titled", () => {
    render(
      <ChillCatalogPicker
        items={items}
        value="neko"
        onChange={vi.fn()}
        ariaLabel="Chọn Harness"
        emptyLabel="Không tìm thấy harness phù hợp."
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Chọn Harness" }));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "zzz-nope" } });
    expect(screen.getByText("Không tìm thấy harness phù hợp.")).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "" } });
    expect(screen.getByRole("option", { name: /Missing/i }).getAttribute("title")).toBe("Chưa sẵn sàng");
  });
});

describe("NekoComposer catalog + draft keep", () => {
  const workspace = { name: "workspace", path: "C:/ux-fixtures/project" };

  it("keeps the draft when switching model via the searchable picker", () => {
    clearNekoComposerDraft("session:picker-draft");
    const onSetConfigOption = vi.fn();
    const session = {
      id: "picker-draft",
      agentName: "Neko Core",
      status: "idle",
      commands: [],
      workspace,
      controls: [{
        id: "model",
        label: "Model",
        category: "model",
        kind: "select",
        currentValue: "a",
        choices: [
          { value: "a", label: "Model A" },
          { value: "b", label: "Model B" },
        ],
      }],
    } as unknown as NekoSession;

    render(
      <NekoComposer
        session={session}
        disabled={false}
        streaming={false}
        onSend={vi.fn()}
        onCancel={vi.fn()}
        onSetConfigOption={onSetConfigOption}
        onClientCommand={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Giữ bản nháp khi đổi model" } });
    fireEvent.click(screen.getByRole("button", { name: "Model" }));
    fireEvent.click(screen.getByRole("option", { name: /Model B/i }));
    expect(onSetConfigOption).toHaveBeenCalledWith("model", "b");
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Giữ bản nháp khi đổi model");
    expect(readNekoComposerDraft("session:picker-draft")).toBe("Giữ bản nháp khi đổi model");
  });

  it("surfaces a clear VI lock reason when launch profile model is immutable", () => {
    const session = {
      id: "picker-lock",
      agentName: "Neko Core",
      status: "idle",
      commands: [],
      controls: [],
      workspace,
      launchProfile: { id: "local", model: "glm-local", provider: "local" },
    } as unknown as NekoSession;
    render(
      <NekoComposer
        session={session}
        disabled={false}
        streaming={false}
        onSend={vi.fn()}
        onCancel={vi.fn()}
        onSetConfigOption={vi.fn()}
        onClientCommand={vi.fn()}
      />,
    );
    const lock = screen.getByTestId("neko-model-locked");
    expect(lock.getAttribute("title")).toMatch(/cố định cho phiên này/i);
    expect(lock.getAttribute("title")).toMatch(/Bản nháp vẫn giữ/i);
  });
});
