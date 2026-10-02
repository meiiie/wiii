/** Durable user-intent outbox. It never implements agent orchestration or retries. */
export interface OutboxBinding { sessionId: string; workspace: string; task: string; model: string }
export interface OutboxItem {
  id: string; text: string; binding: OutboxBinding;
  state: "queued" | "delivering" | "uncertain";
}
export interface OutboxQueue { sessionId: string; paused: boolean; reason: string | null; items: OutboxItem[] }
export interface OutboxSnapshot { version: 1; queues: OutboxQueue[] }
export const emptyOutbox = (): OutboxSnapshot => ({ version: 1, queues: [] });
export function sameOutboxBinding(a: OutboxBinding, b: OutboxBinding): boolean {
  return a.sessionId === b.sessionId && a.workspace === b.workspace && a.task === b.task && a.model === b.model;
}
export function parseOutbox(value: unknown): OutboxSnapshot {
  const x = value as OutboxSnapshot;
  if (!x || x.version !== 1 || !Array.isArray(x.queues)) throw new Error("Dữ liệu hàng đợi không hợp lệ; bản lưu được giữ nguyên.");
  const ids = new Set<string>();
  for (const q of x.queues) {
    if (!q || typeof q.sessionId !== "string" || ids.has(q.sessionId) || typeof q.paused !== "boolean"
      || !(q.reason === null || typeof q.reason === "string") || !Array.isArray(q.items) || q.items.length > 100) throw new Error("Hàng đợi không hợp lệ.");
    ids.add(q.sessionId);
    const itemIds = new Set<string>();
    for (const i of q.items) {
      if (!i || typeof i.id !== "string" || itemIds.has(i.id) || typeof i.text !== "string" || !i.text.trim() || i.text.length > 64000
        || !["queued", "delivering", "uncertain"].includes(i.state) || !i.binding || i.binding.sessionId !== q.sessionId
        || ![i.binding.workspace, i.binding.task, i.binding.model].every(v => typeof v === "string")) throw new Error("Tin nhắn chờ không hợp lệ.");
      itemIds.add(i.id);
    }
  }
  return structuredClone(x);
}

export class DurableOutbox {
  snapshot = emptyOutbox();
  ready = false;
  error: string | null = null;
  private tail: Promise<unknown> = Promise.resolve();
  private inFlight = new Set<string>();
  private blocked = new Set<string>();
  constructor(private storage: { read(): Promise<unknown>; write(value: OutboxSnapshot): Promise<void> }, private changed: () => void) {}
  private transact(change: (value: OutboxSnapshot) => void): Promise<void> {
    const work = this.tail.then(async () => {
      if (!this.ready) throw new Error("Chưa đọc được hàng đợi.");
      const next = structuredClone(this.snapshot);
      change(next);
      await this.storage.write(next);
      this.snapshot = next;
      this.error = null;
      this.changed();
    });
    this.tail = work.catch(error => { this.error = String(error); this.changed(); });
    return work;
  }
  async hydrate(): Promise<void> {
    if (this.ready) return;
    try {
      const next = parseOutbox(await this.storage.read());
      for (const q of next.queues) {
        q.paused = true;
        q.reason = "Wiii đã mở lại. Kiểm tra tin nhắn trước khi tiếp tục.";
        for (const item of q.items) if (item.state === "delivering") item.state = "uncertain";
      }
      await this.storage.write(next);
      this.snapshot = next;
      this.ready = true;
      this.error = null;
      this.changed();
    } catch (error) { this.error = String(error); this.changed(); throw error; }
  }
  enqueue(binding: OutboxBinding, text: string, id: string): Promise<void> {
    return this.transact(state => {
      if (!text.trim() || text.length > 64000) throw new Error("Tin nhắn cần từ 1 đến 64.000 ký tự.");
      let q = state.queues.find(q => q.sessionId === binding.sessionId);
      if (!q) { q = { sessionId: binding.sessionId, paused: false, reason: null, items: [] }; state.queues.push(q); }
      if (q.items.length >= 100) throw new Error("Hàng đợi đã đủ 100 tin. Hãy xử lý hoặc bỏ bớt tin chờ.");
      if (q.items.some(i => i.id === id)) return;
      q.items.push({ id, text, binding: { ...binding }, state: "queued" });
    });
  }
  pause(sessionId: string, reason: string): Promise<void> {
    this.blocked.add(sessionId); // synchronous gate precedes the durability write
    return this.transact(state => {
      const q = state.queues.find(q => q.sessionId === sessionId);
      if (q) { q.paused = true; q.reason = reason; }
    });
  }
  async resume(sessionId: string): Promise<void> {
    await this.transact(state => {
      const q = state.queues.find(q => q.sessionId === sessionId);
      if (!q) return;
      if (q.items.some(i => i.state !== "queued")) throw new Error("Có tin chưa rõ kết quả gửi. Đối chiếu lịch sử và bỏ tin đó khỏi hàng đợi trước.");
      q.paused = false; q.reason = null;
    });
    this.blocked.delete(sessionId);
    this.changed();
  }
  edit(sessionId: string, id: string, text: string): Promise<void> {
    return this.transact(state => {
      const item = state.queues.find(q => q.sessionId === sessionId)?.items.find(i => i.id === id);
      if (!item || item.state !== "queued") throw new Error("Tin này không còn ở trạng thái chờ sửa.");
      if (!text.trim() || text.length > 64000) throw new Error("Nội dung không hợp lệ.");
      item.text = text;
    });
  }
  remove(sessionId: string, id: string): Promise<void> {
    return this.transact(state => {
      const q = state.queues.find(q => q.sessionId === sessionId);
      if (!q) return;
      if (q.items.find(i => i.id === id)?.state === "delivering") throw new Error("Đang chuyển tin; chưa thể bỏ.");
      q.items = q.items.filter(i => i.id !== id);
    });
  }
  async dispatch(sessionId: string, current: () => OutboxBinding | null, canSend: () => boolean,
    send: (text: string, accepted: () => void, binding: OutboxBinding) => Promise<boolean>): Promise<void> {
    const q = this.snapshot.queues.find(q => q.sessionId === sessionId);
    if (!this.ready || this.error || !q || q.paused || this.blocked.has(sessionId) || this.inFlight.has(sessionId) || !canSend()) return;
    const item = q.items[0];
    if (!item || item.state !== "queued") return;
    const binding = current();
    if (!binding || !sameOutboxBinding(binding, item.binding)) {
      await this.pause(sessionId, "Dự án, tác vụ hoặc model đã đổi. Kiểm tra lại tin chờ; không tự gửi sang ngữ cảnh mới."); return;
    }
    this.inFlight.add(sessionId);
    let invoked = false;
    try {
      await this.transact(s => { s.queues.find(q => q.sessionId === sessionId)!.items.find(i => i.id === item.id)!.state = "delivering"; });
      const latest = current();
      if (this.blocked.has(sessionId) || !canSend() || !latest || !sameOutboxBinding(latest, item.binding)) {
        await this.transact(s => { const queue = s.queues.find(q => q.sessionId === sessionId)!; queue.items.find(i => i.id === item.id)!.state = "queued"; queue.paused = true; queue.reason = "Phiên đã thay đổi. Tin chưa được gửi."; });
        return;
      }
      const durableItem = this.snapshot.queues.find(q => q.sessionId === sessionId)!.items.find(i => i.id === item.id)!;
      const completed = await send(durableItem.text, () => { invoked = true; }, durableItem.binding);
      await this.transact(s => {
        const queue = s.queues.find(q => q.sessionId === sessionId)!;
        if (invoked && completed) queue.items = queue.items.filter(i => i.id !== item.id);
        else {
          queue.items.find(i => i.id === item.id)!.state = invoked ? "uncertain" : "queued";
          queue.paused = true; queue.reason = invoked ? "Chưa xác nhận kết quả gửi. Đối chiếu lịch sử; không gửi lại tự động." : "Phiên chưa nhận tin. Tin chờ được giữ lại.";
        }
      });
    } catch (error) {
      this.blocked.add(sessionId);
      this.error = `Không hoàn tất chuyển tin; hàng đợi đã dừng. ${String(error)}`;
      const held = structuredClone(this.snapshot);
      const queue = held.queues.find(q => q.sessionId === sessionId);
      if (queue) {
        queue.paused = true; queue.reason = this.error;
        const current = queue.items.find(i => i.id === item.id);
        if (current?.state === "delivering") current.state = "uncertain";
      }
      this.snapshot = held; // memory-only safety hold; failed disk bytes remain intact
    } finally { this.inFlight.delete(sessionId); this.changed(); }
  }
}
