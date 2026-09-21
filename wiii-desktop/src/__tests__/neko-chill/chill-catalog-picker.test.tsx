import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChillCatalogPicker } from "@/neko-chill/components/ChillCatalogPicker";
import { NekoComposer } from "@/neko-chill/components/NekoComposer";
import { clearNekoComposerDraft, readNekoComposerDraft } from "@/neko-chill/composer-drafts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

describe("ChillCatalogPicker", () => {
  const items = [
    { id: "neko", label: "Neko Core", group: "Harness trên máy" },
    { id: "gemini", label: "Gemini CLI", group: "Harness trên máy" },
    { id: "missing", label: "Missing", group: "Harness trên máy", disabled: true, title: "Chưa sẵn sàng" },
  ];

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
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "zzz-nope" } });
    expect(screen.getByText("Không tìm thấy harness phù hợp.")).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "" } });
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
