import { useState, type MouseEvent } from "react";
import { isTauri } from "@tauri-apps/api/core";
import type { DetectedAgent } from "../stores/neko-agent-store";

const NEKO_DOWNLOAD_URL = "https://neko.holilihu.online/";

export function HarnessSetupNotice({ agents, loading, error, selectedAgent, onRetry }: {
  agents: DetectedAgent[];
  loading: boolean;
  error: string | null;
  selectedAgent: DetectedAgent | null;
  onRetry: () => void;
}) {
  const [linkError, setLinkError] = useState(false);
  const neko = agents.find((agent) => agent.id === "neko");
  const missing = neko?.availability === "not_installed";
  const failed = neko?.availability === "probe_failed";
  const unsupported = neko?.availability === "host_unsupported";
  if (!loading && !error && selectedAgent && !missing && !failed) return null;

  const title = loading ? "Đang kiểm tra agent…"
    : error ? "Chưa kiểm tra được agent"
      : missing ? "Chưa cài Neko Core"
        : failed ? "Chưa kiểm tra được Neko Core"
          : unsupported ? "Hệ điều hành chưa được hỗ trợ"
            : "Chưa có kết quả kiểm tra agent";
  const description = loading || error || failed ? null
    : selectedAgent ? `Đang dùng ${selectedAgent.name}`
      : unsupported ? "Bạn vẫn có thể xem các phiên đã lưu."
        : missing ? "Cài Neko Core để bắt đầu."
          : "Kiểm tra lại để tìm agent trên máy.";

  const openDownload = async (event: MouseEvent<HTMLAnchorElement>) => {
    if (!isTauri()) return;
    event.preventDefault();
    setLinkError(false);
    try {
      const { open } = await import("@tauri-apps/plugin-shell");
      await open(NEKO_DOWNLOAD_URL);
    } catch {
      setLinkError(true);
    }
  };

  return (
    <section aria-label="Trạng thái agent" className="mb-3 border-t border-[var(--nk-border)] pt-3 text-[12px] leading-5 text-[var(--nk-text-2)]">
      <div role={error || failed ? "alert" : "status"}>
        <p className="font-medium text-[var(--nk-text)]">{title}</p>
        {description ? <p>{description}</p> : null}
      </div>
      {!loading && (error || failed) && <details className="mt-1">
        <summary className="cursor-pointer">Chi tiết kiểm tra</summary>
        <p className="mt-1 wrap-break-word text-[var(--nk-text-3)]">{error ?? neko?.detail ?? "Không có thông tin lỗi bổ sung."}</p>
      </details>}
      {!loading && !error && missing && <details className="mt-2">
        <summary className="cursor-pointer font-medium text-[var(--nk-text)]">Cách cài Neko Core</summary>
        <ol className="my-2 list-decimal v3-space-y-1 pl-5">
          <li>Tải và cài Neko Core từ trang chính thức.</li>
          <li>Mở Neko Core để chọn tài khoản hoặc model.</li>
          <li>Quay lại Wiii và nhấn “Kiểm tra lại”.</li>
        </ol>
        <a href={NEKO_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer"
          onClick={(event) => { void openDownload(event); }}
          className="font-medium underline underline-offset-4">Mở trang tải Neko Core ↗</a>
        <p className="mt-2 text-[var(--nk-text-3)]">Đã cài nhưng chưa tìm thấy? Khởi động lại Wiii.</p>
      </details>}
      {linkError && <p role="alert" className="mt-2">Chưa mở được trình duyệt. Bạn có thể mở địa chỉ {NEKO_DOWNLOAD_URL} rồi quay lại đây.</p>}
      {!loading && (error || !unsupported) && <button type="button" onClick={onRetry}
        className="mt-2 rounded-md border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] px-3 py-1 font-medium text-[var(--nk-text)] hover:bg-[var(--nk-overlay)]">
        {error ? "Thử lại" : "Kiểm tra lại"}
      </button>}
    </section>
  );
}
