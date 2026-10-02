import type { NekoSession } from "../stores/neko-session-store";
import { isNekoTaskScopeMapping } from "../task-scope-mapping";

const APPROVAL = {
  default: "Default — hỏi theo policy",
  "accept-edits": "Accept edits — tự duyệt chỉnh sửa",
  plan: "Plan — chế độ lập kế hoạch",
  auto: "Auto — tự động theo policy",
} as const;

/** These are live agent reports, never permission or OS authority controls. */
export function ExecutionReceiptCard({ session }: { session: NekoSession }) {
  if (session.agentId !== "neko") return null;
  const scoped = session.taskScope && isNekoTaskScopeMapping(session.taskScope);
  const live = session.runtime && !session.closePending && !session.deletePending
    && scoped && session.taskScope?.state === "bound"
    && session.executionProjection?.providerInstanceId === session.runtime.instanceId
    ? session.executionProjection.value : undefined;
  const reported = live?.status === "reported" ? live : undefined;
  const displayRoot = reported?.root.replace(/[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g,
    (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
  const unknownLabel = live?.status === "unsupported" ? "Chưa hỗ trợ receipt này"
    : live?.status === "unverified" ? "Chưa xác minh được receipt" : "Chưa có dữ liệu";
  return (
    <section aria-label="Thực thi Neko" data-testid="execution-receipt-card"
      className="mt-3 rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] p-3">
      <h2 className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--nk-text-3)]">Thực thi Neko</h2>
      <p className="mb-2 mt-1 text-[10px] leading-4 text-[var(--nk-ghost)]">
        {!scoped ? "Phiên thủ công/cũ — chưa có receipt tác vụ."
          : reported ? "Thông tin agent báo cáo cho phiên đang chạy."
            : "Chưa có thông tin thực thi đã đối chiếu cho phiên này."}
      </p>
      <dl className="space-y-2 text-[11px] leading-4">
        <div><dt className="text-[var(--nk-ghost)]">Vị trí Bash</dt>
          <dd className="text-[var(--nk-text-2)]">{reported
            ? `${reported.bashTarget === "host" ? "Host" : "Sandbox được yêu cầu"} · ${reported.bashExecutor === "local-process" ? "tiến trình cục bộ" : "backend native"}`
            : unknownLabel}</dd>
          {reported?.bashExecutor === "native-backend" && reported.nativeBackendSandbox === "unsupported"
            ? <dd className="text-[10px] text-[var(--nk-text-3)]">Backend báo chưa hỗ trợ sandbox cho Bash.</dd> : null}
        </div>
        <div><dt className="text-[var(--nk-ghost)]">Chính sách duyệt</dt>
          <dd className="text-[var(--nk-text-2)]">{reported ? APPROVAL[reported.approvalMode] : unknownLabel}</dd>
          {reported ? <dd className="text-[10px] text-[var(--nk-text-3)]">YOLO {reported.yolo ? "bật" : "tắt"}</dd> : null}
        </div>
        <div><dt className="text-[var(--nk-ghost)]">Thư mục tác vụ (logic)</dt>
          <dd className="truncate font-mono text-[10px] text-[var(--nk-text-2)]" title={displayRoot}>
            {reported ? <bdi dir="ltr">{displayRoot}</bdi> : unknownLabel}
          </dd>
        </div>
      </dl>
      <p className="mt-2 text-[10px] leading-4 text-[var(--nk-ghost)]">
        Thư mục liên kết tác vụ; quyền truy cập do host/runtime kiểm soát. Receipt không xác nhận cô lập OS hay hoạt động không chiếm focus.
      </p>
    </section>
  );
}
