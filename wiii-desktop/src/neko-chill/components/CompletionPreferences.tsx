import { useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { completionPlayer } from "../completion-sound";
import { useCompletionNoticeStore } from "../stores/completion-notice-store";
import { NekoButton } from "./ui";

export function CompletionPreferences() {
  const { enabled, sound, setEnabled, setSound } = useCompletionNoticeStore(useShallow((state) => ({
    enabled: state.enabled, sound: state.sound, setEnabled: state.setEnabled, setSound: state.setSound,
  })));
  const [message, setMessage] = useState("");
  return <div className="v3-space-y-4 text-[13px] leading-5">
    <label className="flex items-center justify-between gap-4"><span>Báo khi trả lời xong</span>
      <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /></label>
    <p className="text-[var(--nk-text-2)]">Thông báo trong Wiii. Chọn “Xem kết quả” để mở phiên.</p>
    <label className="flex items-center justify-between gap-4"><span>Âm báo Neko Bubble</span>
      <input type="checkbox" checked={sound} disabled={!enabled} onChange={(event) => setSound(event.target.checked)} /></label>
    <NekoButton
      onClick={async () => {
        const ready = await completionPlayer.prepare();
        setMessage(ready && await completionPlayer.play() ? "Đã phát thử âm Neko Bubble v6." : "Chưa phát được âm. Kiểm tra quyền âm thanh và thiết bị phát của Wiii.");
      }}>Nghe thử âm báo</NekoButton>
    {message && <p role="status" className="text-[var(--nk-text-2)]">{message}</p>}
    <p className="text-[var(--nk-text-3)]">Không báo khi hủy hoặc có lỗi.</p>
  </div>;
}
