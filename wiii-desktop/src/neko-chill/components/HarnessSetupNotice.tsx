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

  const title = loading ? "Đang kiểm tra agent trên máy…"
    : error ? "Chưa kiểm tra được agent trên máy"
      : missing ? "Chưa cài Neko Core"
        : failed ? "Chưa kiểm tra được Neko Core"
          : unsupported ? "Bản Wiii này chưa hỗ trợ chạy agent trên hệ điều hành này"
            : "Chưa có kết quả kiểm tra agent";
  const description = loading ? "Bạn có thể soạn yêu cầu trong lúc chờ. Wiii chưa gửi bản nháp."
    : error ? "Chưa xác nhận được trạng thái chạy an toàn. Hãy kiểm tra lại trước khi gửi yêu cầu."
      : selectedAgent ? `Bạn đã chọn ${selectedAgent.name}. Phiên này dùng lựa chọn của bạn; các Project mới mặc định dùng Neko Core.`
        : unsupported ? "Cài thêm Neko Core không khắc phục giới hạn này của Wiii. Bạn vẫn có thể xem các phiên đã lưu."
          : failed ? "Kiểm tra bị lỗi không có nghĩa là chưa cài. Hãy thử lại trước khi cài mới."
            : missing ? "Neko Core thực hiện yêu cầu của bạn trong Wiii. Cài Neko Core, rồi quay lại kiểm tra. Bạn vẫn có thể soạn và giữ bản nháp."
              : "Wiii chưa xác nhận agent nào dùng được. Bản xem trước trong trình duyệt không kiểm tra được phần mềm trên máy.";

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
        <p>{description}</p>
      </div>
      {!loading && (error || failed) && <details className="mt-1">
        <summary className="cursor-pointer">Chi tiết kiểm tra</summary>
        <p className="mt-1 break-words text-[var(--nk-text-3)]">{error ?? neko?.detail ?? "Không có thông tin lỗi bổ sung."}</p>
      </details>}
      {!loading && !error && missing && <details className="mt-2">
        <summary className="cursor-pointer font-medium text-[var(--nk-text)]">Cách cài Neko Core</summary>
        <ol className="my-2 list-decimal space-y-1 pl-5">
          <li>Tải và cài Neko Core từ trang chính thức.</li>
          <li>Mở Neko Core để chọn tài khoản hoặc model. Không cần tài khoản Wiii Service.</li>
          <li>Quay lại Wiii và nhấn “Kiểm tra lại”. Bản nháp không tự gửi.</li>
        </ol>
        <a href={NEKO_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer"
          onClick={(event) => { void openDownload(event); }}
          className="font-medium underline underline-offset-4">Mở trang tải Neko Core ↗</a>
        <p className="mt-2 text-[var(--nk-text-3)]">Wiii chỉ mở trang hướng dẫn, không tự tải hoặc chạy bộ cài. Nếu đã cài mà vẫn chưa tìm thấy, hãy khởi động lại Wiii để nhận đường dẫn chương trình mới.</p>
      </details>}
      {linkError && <p role="alert" className="mt-2">Chưa mở được trình duyệt. Bạn có thể mở địa chỉ {NEKO_DOWNLOAD_URL} rồi quay lại đây.</p>}
      {!loading && (error || !unsupported) && <button type="button" onClick={onRetry}
        className="mt-2 rounded-md border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] px-3 py-1 font-medium text-[var(--nk-text)] hover:bg-[var(--nk-overlay)]">
        {error ? "Thử lại" : "Kiểm tra lại"}
      </button>}
    </section>
  );
}
