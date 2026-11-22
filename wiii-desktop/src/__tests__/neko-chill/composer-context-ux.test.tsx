import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NekoComposer } from "@/neko-chill/components/NekoComposer";
import { clearNekoComposerDraft } from "@/neko-chill/composer-drafts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

const session = {
  id: "composer-context-ux", agentName: "Neko Core", status: "idle",
  workspace: { name: "Wiii", path: "E:/MeiiieGroup/wiii/long-project-path" },
  controls: [{ id: "mode", category: "mode", kind: "select", label: "Chế độ", currentValue: "default", choices: [
    { value: "default", label: "Mặc định" }, { value: "plan", label: "Lập kế hoạch" },
  ] }], commands: [],
} as unknown as NekoSession;

function mount(overrides: Partial<NekoSession> = {}) {
  const props = { session: { ...session, ...overrides }, disabled: false, streaming: false,
    onSend: vi.fn(), onCancel: vi.fn(), onSetConfigOption: vi.fn(), onClientCommand: vi.fn() };
  return { ...render(<NekoComposer {...props} />), props };
}

describe("composer context and keyboard UX", () => {
  beforeEach(() => clearNekoComposerDraft("session:composer-context-ux"));

  it("lets the user inspect the project path without changing the workspace or draft", () => {
    const { props } = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Giữ bản nháp" } });
    const project = screen.getByRole("button", { name: "Dự án Wiii. Xem đường dẫn" });
    expect(project.getAttribute("aria-expanded")).toBe("false");
    project.focus();
    fireEvent.click(project);
    expect(project.getAttribute("aria-expanded")).toBe("true");
    const details = document.getElementById(project.getAttribute("aria-controls")!)!;
    expect(details.hidden).toBe(false);
    expect(details.textContent).toContain(session.workspace!.path);
    fireEvent.keyDown(project, { key: "Escape" });
    expect(details.hidden).toBe(true);
    expect(document.activeElement).toBe(project);
    expect(input.value).toBe("Giữ bản nháp");
    expect(props.onClientCommand).not.toHaveBeenCalled();
    expect(props.onSend).not.toHaveBeenCalled();
  });

  it("returns to the composer after a keyboard configuration selection and retains the draft", async () => {
    const { props } = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Nội dung chưa gửi" } });
    fireEvent.keyDown(screen.getByRole("button", { name: "Chế độ" }), { key: "Enter" });
    const search = screen.getByRole("combobox", { name: "Tìm chế độ…" });
    fireEvent.keyDown(search, { key: "ArrowDown" });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(props.onSetConfigOption).toHaveBeenCalledExactlyOnceWith("mode", "plan");
    await vi.waitFor(() => expect(document.activeElement).toBe(input));
    expect(input.value).toBe("Nội dung chưa gửi");
    expect(props.onSend).not.toHaveBeenCalled();
  });

  it("restores the picker trigger on Escape without changing configuration", async () => {
    const { props } = mount();
    const trigger = screen.getByRole("button", { name: "Chế độ" });
    fireEvent.keyDown(trigger, { key: "Enter" });
    const search = screen.getByRole("combobox", { name: "Tìm chế độ…" });
    await vi.waitFor(() => expect(document.activeElement).toBe(search));
    fireEvent.keyDown(search, { key: "Escape" });
    expect(screen.queryByRole("listbox", { name: "Chế độ" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(props.onSetConfigOption).not.toHaveBeenCalled();
  });

  it.each([{ isComposing: true }, { keyCode: 229 }])("keeps IME Enter from inserting a slash command or choosing configuration (%j)", key => {
    const { props } = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "/" } });
    fireEvent.keyDown(input, { key: "Enter", ...key });
    expect(input.value).toBe("/");
    expect(props.onSend).not.toHaveBeenCalled();
    expect(props.onClientCommand).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Chế độ" }));
    fireEvent.keyDown(screen.getByRole("combobox", { name: "Tìm chế độ…" }), { key: "Enter", ...key });
    expect(screen.getByRole("listbox", { name: "Chế độ" })).toBeTruthy();
    expect(props.onSetConfigOption).not.toHaveBeenCalled();
  });

  it("explains a pending configuration next to the retained, read-only draft", () => {
    mount({ pendingControlId: "mode" });
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    expect(input.readOnly).toBe(true);
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Đang đổi cấu hình. Bản nháp được giữ lại.");
    expect(input.getAttribute("aria-describedby")).toBe(status.id);
    expect((screen.getByRole("button", { name: "Chế độ" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("points to the error notice without dropping the draft or allowing another send", () => {
    const view = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Bản nháp chưa gửi" } });
    view.rerender(<NekoComposer {...view.props} session={{ ...session, status: "error" }} />);
    const notice = screen.getByRole("status");
    expect(notice.textContent).toBe("Chưa thể gửi. Xem thông báo phía trên.");
    expect(input.getAttribute("aria-describedby")).toBe(notice.id);
    expect(input.value).toBe("Bản nháp chưa gửi");
    expect(input.readOnly).toBe(true);
    const send = screen.getByTestId("neko-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.click(send);
    expect(view.props.onSend).not.toHaveBeenCalled();
    expect(view.props.onCancel).not.toHaveBeenCalled();
  });

  it("labels keyboard Send, keeps it on hover, and dismisses without sending or losing the draft", () => {
    const { props } = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Chưa gửi" } });
    const send = screen.getByRole("button", { name: "Gửi tin nhắn" });
    act(() => send.focus());
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toBe("Gửi");
    expect(document.getElementById(send.getAttribute("aria-describedby")!)?.textContent).toBe("Gửi");
    expect(send.hasAttribute("title")).toBe(false);
    fireEvent.mouseLeave(send.parentElement!);
    expect(screen.getByRole("tooltip")).toBe(tooltip);
    fireEvent.keyDown(send, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(document.activeElement).toBe(send);
    expect(input.value).toBe("Chưa gửi");
    expect(props.onSend).not.toHaveBeenCalled();
    act(() => input.focus());
    fireEvent.mouseEnter(send.parentElement!);
    expect(screen.getByRole("tooltip").textContent).toBe("Gửi");
    fireEvent.mouseLeave(send.parentElement!);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("clears the Send popup on explicit send and retains the disabled explanation", async () => {
    const view = mount();
    view.props.onSend.mockImplementation((_text, accepted) => accepted());
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Gửi một lần" } });
    const send = screen.getByTestId("neko-send") as HTMLButtonElement;
    fireEvent.mouseEnter(send.parentElement!);
    await act(async () => fireEvent.click(send));
    expect(view.props.onSend).toHaveBeenCalledOnce();
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(send.disabled).toBe(true);
    fireEvent.mouseLeave(send.parentElement!);
    fireEvent.mouseEnter(send.parentElement!);
    expect(screen.getByRole("tooltip").textContent).toBe("Nhập nội dung trước khi gửi.");
    fireEvent.click(send);
    expect(view.props.onSend).toHaveBeenCalledOnce();
  });

  it("dismisses hovered Send help with Escape while focus stays in the draft", () => {
    const { props } = mount();
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    act(() => input.focus());
    const send = screen.getByTestId("neko-send");
    fireEvent.mouseEnter(send.parentElement!);
    expect(screen.getByRole("tooltip")).toBeTruthy();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(document.activeElement).toBe(input);
    expect(props.onSend).not.toHaveBeenCalled();
  });

  it("always describes why Send is disabled to assistive technology without needing pointer hover", () => {
    const { props } = mount();
    const send = screen.getByTestId("neko-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(document.getElementById(send.getAttribute("aria-describedby")!)?.textContent)
      .toBe("Nhập nội dung trước khi gửi.");
    fireEvent.click(send);
    expect(props.onSend).not.toHaveBeenCalled();
  });
  it.each(["streaming", "dispatching"] as const)("allows drafting during %s without submitting or cancelling", status => {
    const props = { session: { ...session, status }, disabled: true, streaming: true,
      onSend: vi.fn(), onCancel: vi.fn(), onSetConfigOption: vi.fn(), onClientCommand: vi.fn() };
    const view = render(<NekoComposer {...props} />);
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    expect(input.readOnly).toBe(false);
    expect(screen.queryByText("Enter", { selector: "kbd" })).toBeNull();
    expect(input.disabled).toBe(false);
    fireEvent.change(input, { target: { value: "Bản nháp cho lượt tiếp theo" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onSend).not.toHaveBeenCalled();
    expect(props.onCancel).not.toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toContain("chưa được gửi");
    view.rerender(<NekoComposer {...props} session={{ ...session, status: "idle" }} disabled={false} streaming={false} />);
    expect(input.value).toBe("Bản nháp cho lượt tiếp theo");
    expect(props.onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onSend).toHaveBeenCalledOnce();
  });

});
