import { useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { completionPlayer } from "../completion-sound";
import { useCompletionNoticeStore } from "../stores/completion-notice-store";

export function CompletionPreferences() {
  const { enabled, sound, setEnabled, setSound } = useCompletionNoticeStore(useShallow((state) => ({
    enabled: state.enabled, sound: state.sound, setEnabled: state.setEnabled, setSound: state.setSound,
  })));
  const [message, setMessage] = useState("");
  return <div className="space-y-4 text-[13px] leading-5">
    <label className="flex items-center justify-between gap-4"><span>Báo khi trả lời xong</span>
      <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /></label>
    <p className="text-[var(--nk-text-2)]">Thông báo ở góc trái Wiii, tự ẩn sau 7 giây. Trỏ chuột hoặc chọn bằng bàn phím để giữ lại; bấm “Xem kết quả” để mở đúng phiên.</p>
    <label className="flex items-center justify-between gap-4"><span>Âm báo Neko Bubble</span>
      <input type="checkbox" checked={sound} disabled={!enabled} onChange={(event) => setSound(event.target.checked)} /></label>
    <button type="button" className="rounded-md border border-[var(--nk-border-strong)] px-3 py-1.5"
      onClick={async () => {
        const ready = await completionPlayer.prepare();
        setMessage(ready && await completionPlayer.play() ? "Đã phát thử âm Neko Bubble v6." : "Chưa phát được âm. Kiểm tra quyền âm thanh và thiết bị phát của Wiii.");
      }}>Nghe thử âm báo</button>
    {message && <p role="status" className="text-[var(--nk-text-2)]">{message}</p>}
    <p className="text-[var(--nk-text-3)]">Chỉ báo sau khi lượt trả lời kết thúc và được lưu. Không báo hoàn tất khi hủy, lỗi hoặc mới tải lịch sử. Đây là thông báo trong Wiii, không phải thông báo hệ điều hành.</p>
  </div>;
}
