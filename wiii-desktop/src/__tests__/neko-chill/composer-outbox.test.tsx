import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";
import { NekoComposer } from "@/neko-chill/components/NekoComposer";
import { clearNekoComposerDraft, readNekoComposerDraft } from "@/neko-chill/composer-drafts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
const session = { id: "queue-ui", agentName: "Neko", status: "streaming", workspace: { name: "qa", path: "/qa" }, controls: [], commands: [] } as unknown as NekoSession;
function mount(queue: (text: string) => Promise<void>, idle = false) {
  const props = { session: { ...session, status: idle ? "idle" as const : "streaming" as const }, streaming: !idle, disabled: false,
    queuedCount: idle ? 1 : 0, onQueue: queue, onSend: vi.fn(), onCancel: vi.fn(), onSetConfigOption: vi.fn(), onClientCommand: vi.fn() };
  render(<NekoComposer {...props} />); return props;
}
beforeEach(() => clearNekoComposerDraft("session:queue-ui"));
describe("queue composer contract", () => {
  it("retains a newer draft while durable enqueue completes and prevents duplicate Enter", async () => {
    let finish!: () => void; const queue = vi.fn(() => new Promise<void>(r => { finish = r; }));
    const props = mount(queue); const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "first" } }); fireEvent.keyDown(input, { key: "Enter" }); fireEvent.keyDown(input, { key: "Enter" });
    expect(queue).toHaveBeenCalledExactlyOnceWith("first"); expect(input.value).toBe("first");
    fireEvent.change(input, { target: { value: "new draft" } }); await act(async () => finish());
    expect(input.value).toBe("new draft"); expect(readNekoComposerDraft("session:queue-ui")).toBe("new draft"); expect(props.onSend).not.toHaveBeenCalled();
  });
  it("keeps the draft when enqueue fails", async () => {
    const queue = vi.fn(async () => { throw new Error("disk full"); }); mount(queue);
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "keep" } }); await act(async () => fireEvent.keyDown(input, { key: "Enter" }));
    expect(input.value).toBe("keep"); expect(screen.getByRole("alert").textContent).toContain("disk full");
  });
  it("never sends past an existing queue when the session becomes idle", async () => {
    const queue = vi.fn(async () => {}); const props = mount(queue, true);
    fireEvent.change(screen.getByTestId("neko-composer-input"), { target: { value: "next" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Xếp hàng tin nhắn" })));
    expect(queue).toHaveBeenCalledExactlyOnceWith("next"); expect(props.onSend).not.toHaveBeenCalled();
  });
  it("releases send admission at acceptance so the same composer can queue during its own running turn", async () => {
    let accept!: () => void; let finishTurn!: () => void; let finishQueue!: () => void;
    const onSend = vi.fn((_text: string, accepted: () => void) => { accept = accepted; return new Promise<void>(resolve => { finishTurn = resolve; }); });
    const onQueue = vi.fn(() => new Promise<void>(resolve => { finishQueue = resolve; }));
    const props = { session: { ...session, status: "idle" as const }, streaming: false, disabled: false, onSend, onQueue,
      onCancel: vi.fn(), onSetConfigOption: vi.fn(), onClientCommand: vi.fn() };
    const view = render(<NekoComposer {...props} />);
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "first turn" } }); fireEvent.keyDown(input, { key: "Enter" });
    act(() => accept());
    view.rerender(<NekoComposer {...props} session={session} streaming />);
    fireEvent.change(input, { target: { value: "next turn" } }); fireEvent.keyDown(input, { key: "Enter" });
    expect(onQueue).toHaveBeenCalledExactlyOnceWith("next turn");
    await act(async () => finishTurn());
    fireEvent.keyDown(input, { key: "Enter" }); expect(onQueue).toHaveBeenCalledOnce();
    await act(async () => finishQueue()); expect(input.value).toBe("");
  });
  it("keeps Stop independent from queue submission", () => {
    const queue = vi.fn(async () => {}); const props = mount(queue);
    fireEvent.click(screen.getByRole("button", { name: "Dừng lượt đang chạy" }));
    expect(props.onCancel).toHaveBeenCalledOnce(); expect(queue).not.toHaveBeenCalled();
  });
});
