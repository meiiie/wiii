import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NekoOutbox } from "@/neko-chill/components/NekoOutbox";
import type { OutboxItem, OutboxQueue } from "@/neko-chill/durable-outbox";
const fake = vi.hoisted(() => ({ state: {} as any, pause: vi.fn(), resume: vi.fn(), edit: vi.fn(), remove: vi.fn(), hydrate: vi.fn() }));
vi.mock("@/neko-chill/stores/neko-outbox-store", () => ({
  useNekoOutboxStore: (selector: (s: any) => unknown) => selector(fake.state),
  outbox: { pause: fake.pause, resume: fake.resume, edit: fake.edit, remove: fake.remove }, hydrateOutbox: fake.hydrate,
}));
const item = (id: string, state: OutboxItem["state"] = "queued"): OutboxItem => ({ id, text: `Tin ${id} cần xem`, state, binding: { sessionId: "s", workspace: "/qa", task: "legacy", model: "qa" } });
function setup(items = [item("one")], paused = false) {
  const queue: OutboxQueue = { sessionId: "s", items, paused, reason: paused ? "Đã tạm dừng để kiểm tra." : null };
  fake.state = { snapshot: { version: 1, queues: [queue] }, error: null, ready: true };
  return render(<NekoOutbox sessionId="s" />);
}
beforeEach(() => { vi.resetAllMocks(); fake.pause.mockResolvedValue(undefined); fake.edit.mockResolvedValue(undefined); fake.remove.mockResolvedValue(undefined); });
describe("compact outbox panel", () => {
  it("keeps ordered rows compact with named keyboard actions", () => {
    setup([item("one"), item("two")]);
    expect(screen.getAllByTestId("neko-outbox-row")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Sửa tin 2" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Bỏ tin 2 khỏi hàng đợi" })).toBeTruthy();
    expect(screen.queryByText("Chưa gửi")).toBeNull();
    expect(screen.getByRole("list").className).toContain("max-h-");
  });
  it("collapses rows without hiding pause or the paused reason", () => {
    setup([item("one")], true);
    fireEvent.click(screen.getByRole("button", { name: /Thu gọn hàng đợi/ }));
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.getByText("Đã tạm dừng để kiểm tra.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tiếp tục hàng đợi" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Mở hàng đợi/ }));
    expect(screen.getByRole("list")).toBeTruthy();
  });
  it("opens full text without mutating or pausing the queue", () => {
    setup(); fireEvent.click(screen.getByRole("button", { name: /^Xem tin 1/ }));
    expect(screen.getByRole("button", { name: /^Xem tin 1/ }).getAttribute("aria-expanded")).toBe("true");
    expect(fake.pause).not.toHaveBeenCalled();
  });
  it("waits for durable pause before showing edit and prevents duplicate clicks", async () => {
    let finish!: () => void;
    fake.pause.mockImplementation(() => new Promise<void>(resolve => { finish = resolve; }));
    setup(); const edit = screen.getByRole("button", { name: "Sửa tin 1" });
    fireEvent.click(edit); fireEvent.click(edit);
    expect(fake.pause).toHaveBeenCalledOnce(); expect(screen.queryByRole("textbox")).toBeNull();
    await act(async () => finish());
    expect(screen.getByRole("textbox", { name: "Sửa tin chờ" })).toBe(document.activeElement);
    expect((screen.getByRole("button", { name: /Thu gọn hàng đợi/ }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("retains edited text on storage failure and never resumes automatically", async () => {
    setup(); await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sửa tin 1" })));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "new text" } });
    fake.edit.mockRejectedValue(new Error("disk full"));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Lưu sửa đổi" })));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("new text");
    expect(screen.getByRole("alert").textContent).toContain("disk full"); expect(fake.resume).not.toHaveBeenCalled();
  });
  it("saves only the selected item; Escape cancels edit without saving", async () => {
    setup(); await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sửa tin 1" })));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "changed" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Lưu sửa đổi" })));
    expect(fake.edit).toHaveBeenCalledExactlyOnceWith("s", "one", "changed");
    expect(screen.queryByRole("textbox")).toBeNull();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sửa tin 1" })));
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
    expect(fake.edit).toHaveBeenCalledOnce(); expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("blocks resume for uncertain items and exposes reconciliation guidance", () => {
    setup([item("one", "uncertain")], true);
    expect((screen.getByRole("button", { name: "Tiếp tục hàng đợi" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Đối chiếu lịch sử trước/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sửa tin 1" })).toBeNull();
    expect((screen.getByRole("button", { name: "Bỏ tin 1 khỏi hàng đợi" }) as HTMLButtonElement).disabled).toBe(false);
  });
  it("cannot edit or remove a delivering item", () => {
    setup([item("one", "delivering")]);
    expect(screen.queryByRole("button", { name: "Sửa tin 1" })).toBeNull();
    expect((screen.getByRole("button", { name: "Bỏ tin 1 khỏi hàng đợi" }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("shows failed pause instead of opening an unsafe editor", async () => {
    fake.pause.mockRejectedValue(new Error("write failed")); setup();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sửa tin 1" })));
    expect(screen.queryByRole("textbox")).toBeNull(); expect(screen.getByRole("alert").textContent).toContain("write failed");
  });
  it("isolates session content and renders nothing for an empty queue", () => {
    const view = setup([]); expect(screen.queryByRole("region")).toBeNull();
    fake.state.snapshot.queues[0].items = [item("one")]; view.rerender(<NekoOutbox sessionId="another" />);
    expect(screen.queryByTestId("neko-outbox")).toBeNull();
  });
});
