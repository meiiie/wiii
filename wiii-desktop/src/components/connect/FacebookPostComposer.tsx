import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";
import type {
  WiiiConnectActivationReadinessResponse,
  WiiiConnectOperationApprovalLedger,
  WiiiConnectProviderConnectionRecord,
} from "@/api/types/wiii-connect";
import {
  applyWiiiConnectFacebookPost,
  fetchWiiiConnectFacebookPages,
  grantWiiiConnectProviderConnectionScopes,
  previewWiiiConnectFacebookPost,
} from "@/api/wiii-connect";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { compactText, scopeSummary } from "./connect-display";
import type {
  CatalogCard,
  FacebookPostComposerState,
  FacebookPostDraftImage,
} from "./connect-types";
import { StatusPill } from "./ConnectStatus";
import {
  providerConnectionRef,
  readinessBooleanLabel,
  readinessReadyForAction,
} from "./provider-readiness";

function operationApprovalLedgerTone(
  ledger: WiiiConnectOperationApprovalLedger | null | undefined,
): CapabilityStatusTone {
  if (!ledger) return "off";
  if (ledger.blocked || ledger.status === "blocked" || ledger.status === "expired") {
    return "warn";
  }
  if (ledger.persistent && (ledger.status === "pending" || ledger.status === "consumed")) {
    return "ok";
  }
  if (ledger.status === "unavailable") return "pending";
  return "off";
}

function operationApprovalLedgerLabel(
  ledger: WiiiConnectOperationApprovalLedger | null | undefined,
): string {
  if (!ledger) return "Chưa có";
  if (ledger.blocked || ledger.status === "blocked") return "Bị chặn";
  if (ledger.status === "consumed" || ledger.consumed) return "Đã consume";
  if (ledger.status === "pending" && ledger.persistent) return "Đã ghi ledger";
  if (ledger.status === "unavailable") return "Fallback HMAC";
  return compactText(ledger.status, "Chưa có");
}

function FacebookOperationApprovalLedgerStatus({
  ledger,
}: {
  ledger: WiiiConnectOperationApprovalLedger | null | undefined;
}) {
  if (!ledger) return null;
  const tone = operationApprovalLedgerTone(ledger);
  const detail = ledger.persistent
    ? compactText(ledger.reason, "ready")
    : "operation_approval_table_ready=false";
  return (
    <div
      data-testid="wiii-connect-facebook-approval-ledger"
      className="mt-3 rounded-md border border-[var(--border)] bg-surface px-3 py-2 text-xs"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-text">Approval ledger</span>
        <StatusPill tone={tone}>{operationApprovalLedgerLabel(ledger)}</StatusPill>
      </div>
      <div className="mt-1 grid gap-1 text-text-secondary sm:grid-cols-3">
        <span>Status: {compactText(ledger.status, "unknown")}</span>
        <span>Reason: {detail}</span>
        <span>Persistent: {readinessBooleanLabel(ledger.persistent)}</span>
      </div>
    </div>
  );
}

export function FacebookPostComposer({
  card,
  providerConnection,
  readiness,
  onRefreshConnections,
}: {
  card: CatalogCard;
  providerConnection: WiiiConnectProviderConnectionRecord | undefined;
  readiness: WiiiConnectActivationReadinessResponse | undefined;
  onRefreshConnections?: (card: CatalogCard) => Promise<unknown>;
}) {
  const [pageId, setPageId] = useState("");
  const [message, setMessage] = useState(
    "Wiii Connect test: bài đăng này đã đi qua preview và xác nhận trước khi đăng.",
  );
  const [image, setImage] = useState<FacebookPostDraftImage | null>(null);
  const [state, setState] = useState<FacebookPostComposerState>({
    pagesLoading: false,
    scopeGrantLoading: false,
    previewLoading: false,
    applyLoading: false,
  });

  useEffect(() => {
    return () => {
      if (image?.previewUrl) URL.revokeObjectURL(image.previewUrl);
    };
  }, [image?.previewUrl]);

  if (card.providerSlug !== "facebook" || card.registrySource !== "backend") {
    return null;
  }

  const connectionRef = providerConnectionRef(providerConnection);
  const connected = Boolean(
    connectionRef &&
      providerConnection &&
      (providerConnection.active || providerConnection.state === "connected") &&
      providerConnection.state !== "disabled",
  );
  const scopes: Record<string, boolean> = providerConnection?.scopes ?? {};
  const hasPostScopes = Boolean(scopes.read && scopes.preview && scopes.apply);
  const selectedPageId = pageId.trim();
  const canLoadPages = connected && Boolean(scopes.read);
  const canPreview = connected && hasPostScopes && Boolean(selectedPageId);
  const previewReady = Boolean(
    state.preview?.status === "ready" &&
      state.preview.approval_token &&
      state.preview.preview_evidence_id,
  );
  const canApply = canPreview && previewReady && !state.applyLoading;
  const imagePreviewUrl =
    image?.previewUrl && image.previewUrl.startsWith("blob:")
      ? image.previewUrl
      : "";
  const approvalLedger = state.apply?.approval_ledger ?? state.preview?.approval_ledger;

  const clearDecision = () => {
    setState((current) => ({
      ...current,
      preview: undefined,
      previewError: undefined,
      apply: undefined,
      applyError: undefined,
    }));
  };

  const grantScopes = async () => {
    if (!connectionRef || state.scopeGrantLoading) return;
    setState((current) => ({
      ...current,
      scopeGrantLoading: true,
      scopeGrantError: undefined,
    }));
    try {
      const response = await grantWiiiConnectProviderConnectionScopes(
        card.providerSlug,
        connectionRef,
        { read: true, preview: true, apply: true },
      );
      setState((current) => ({
        ...current,
        scopeGrantLoading: false,
        scopeGrantError: response.status === "ready" ? undefined : response.reason,
      }));
      await onRefreshConnections?.(card);
    } catch {
      setState((current) => ({
        ...current,
        scopeGrantLoading: false,
        scopeGrantError: "Không thể cấp scope qua backend.",
      }));
    }
  };

  const loadPages = async () => {
    if (!connectionRef || !canLoadPages || state.pagesLoading) return;
    setState((current) => ({
      ...current,
      pagesLoading: true,
      pagesError: undefined,
    }));
    try {
      const response = await fetchWiiiConnectFacebookPages(card.providerSlug, connectionRef);
      setState((current) => ({
        ...current,
        pages: response,
        pagesLoading: false,
        pagesError: response.status === "ready" ? undefined : response.reason,
      }));
      if (!pageId && response.pages?.[0]?.page_id) {
        setPageId(response.pages[0].page_id);
      }
    } catch {
      setState((current) => ({
        ...current,
        pagesLoading: false,
        pagesError: "Không thể đọc Page từ backend.",
      }));
    }
  };

  const chooseImage = async (file: File | undefined) => {
    if (!file) return;
    clearDecision();
    if (!["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type)) {
      setState((current) => ({
        ...current,
        previewError: "Ảnh phải là PNG, JPEG, WebP hoặc GIF.",
      }));
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setState((current) => ({
        ...current,
        previewError: "Ảnh tối đa 10MB.",
      }));
      return;
    }
    const base64 = await readFileAsDataUrl(file);
    setImage((current) => {
      if (current?.previewUrl) URL.revokeObjectURL(current.previewUrl);
      return {
        base64,
        mediaType: file.type,
        filename: file.name,
        previewUrl: URL.createObjectURL(file),
      };
    });
  };

  const previewPost = async () => {
    if (!canPreview || state.previewLoading) return;
    setState((current) => ({
      ...current,
      previewLoading: true,
      previewError: undefined,
      apply: undefined,
      applyError: undefined,
    }));
    try {
      const response = await previewWiiiConnectFacebookPost(card.providerSlug, {
        connection_ref: connectionRef,
        page_id: selectedPageId,
        message,
        image_base64: image?.base64 ?? null,
        image_media_type: image?.mediaType ?? null,
        image_filename: image?.filename ?? null,
      });
      setState((current) => ({
        ...current,
        preview: response,
        previewLoading: false,
        previewError: response.status === "ready" ? undefined : response.reason,
      }));
    } catch {
      setState((current) => ({
        ...current,
        previewLoading: false,
        previewError: "Không thể tạo preview qua backend.",
      }));
    }
  };

  const applyPost = async () => {
    if (!canApply || !state.preview?.approval_token || !state.preview.preview_evidence_id) {
      return;
    }
    setState((current) => ({
      ...current,
      applyLoading: true,
      applyError: undefined,
    }));
    try {
      const response = await applyWiiiConnectFacebookPost(card.providerSlug, {
        connection_ref: connectionRef,
        page_id: selectedPageId,
        message,
        image_base64: image?.base64 ?? null,
        image_media_type: image?.mediaType ?? null,
        image_filename: image?.filename ?? null,
        approval_token: state.preview.approval_token,
        preview_evidence_id: state.preview.preview_evidence_id,
      });
      setState((current) => ({
        ...current,
        apply: response,
        applyLoading: false,
        applyError: response.status === "succeeded" ? undefined : response.reason,
      }));
    } catch {
      setState((current) => ({
        ...current,
        applyLoading: false,
        applyError: "Không thể đăng qua backend.",
      }));
    }
  };

  return (
    <section className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase text-text-tertiary">
          Facebook post
        </div>
        <StatusPill tone={connected ? (hasPostScopes ? "ok" : "warn") : "off"}>
          {connected ? (hasPostScopes ? "Có quyền" : "Cần scope") : "Chưa nối"}
        </StatusPill>
      </div>

      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <div className="rounded-md bg-surface px-2 py-2">
          <dt className="text-text-tertiary">Preview/apply</dt>
          <dd className="mt-0.5 font-medium text-text">
            {readinessBooleanLabel(readinessReadyForAction(readiness))}
          </dd>
        </div>
        <div className="rounded-md bg-surface px-2 py-2">
          <dt className="text-text-tertiary">Scope</dt>
          <dd className="mt-0.5 font-medium text-text">{scopeSummary(scopes)}</dd>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!connected || hasPostScopes || state.scopeGrantLoading}
          onClick={() => void grantScopes()}
          className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 text-sm font-medium text-primary disabled:border-[var(--border)] disabled:bg-surface disabled:text-text-tertiary"
        >
          {state.scopeGrantLoading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <ShieldCheck size={14} aria-hidden="true" />
          )}
          Cho phép đăng
        </button>
        <button
          type="button"
          disabled={!canLoadPages || state.pagesLoading}
          onClick={() => void loadPages()}
          className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-surface px-3 text-sm font-medium text-text-secondary disabled:text-text-tertiary"
        >
          <RefreshCw
            size={14}
            className={state.pagesLoading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          Đọc Page
        </button>
      </div>

      <label className="mt-3 block text-xs font-medium text-text-tertiary">
        Page
        <select
          value={pageId}
          onChange={(event) => {
            setPageId(event.target.value);
            clearDecision();
          }}
          className="mt-1 h-10 w-full rounded-md border border-[var(--border)] bg-surface px-3 text-sm text-text outline-none focus:border-primary"
        >
          <option value="">Chọn Page</option>
          {state.pages?.pages?.map((page) => (
            <option key={page.page_id} value={page.page_id}>
              {page.name || page.page_id}
            </option>
          ))}
        </select>
      </label>

      <label className="mt-3 block text-xs font-medium text-text-tertiary">
        Nội dung
        <textarea
          value={message}
          onChange={(event) => {
            setMessage(event.target.value);
            clearDecision();
          }}
          rows={4}
          className="mt-1 w-full resize-none rounded-md border border-[var(--border)] bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
        />
      </label>

      <div className="mt-3 grid gap-3">
        <label className="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-surface px-3 text-sm font-medium text-text-secondary hover:text-text">
          <ImageIcon size={15} aria-hidden="true" />
          Chọn ảnh
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="sr-only"
            onChange={(event) => void chooseImage(event.target.files?.[0])}
          />
        </label>
        {image && imagePreviewUrl && (
          <div className="overflow-hidden rounded-md border border-[var(--border)] bg-surface">
            <img
              src={imagePreviewUrl}
              alt=""
              className="h-36 w-full object-cover"
            />
            <div className="px-3 py-2 text-xs text-text-secondary">
              {image.filename}
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canPreview || state.previewLoading}
          onClick={() => void previewPost()}
          className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-surface px-3 text-sm font-medium text-text-secondary disabled:text-text-tertiary"
        >
          {state.previewLoading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={14} aria-hidden="true" />
          )}
          Tạo preview
        </button>
        <button
          type="button"
          aria-label="Dang bai da duyet"
          disabled={!canApply}
          onClick={() => void applyPost()}
          className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 text-sm font-medium text-emerald-700 disabled:border-[var(--border)] disabled:bg-surface disabled:text-text-tertiary"
        >
          {state.applyLoading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <Send size={14} aria-hidden="true" />
          )}
          Đăng lên Facebook
        </button>
      </div>

      <FacebookOperationApprovalLedgerStatus ledger={approvalLedger} />

      {state.preview?.preview && (
        <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Preview sẵn sàng cho Page đã chọn.
        </div>
      )}
      {state.apply?.status === "succeeded" && (
        <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Đã gửi yêu cầu đăng qua gateway.
        </div>
      )}
      {[state.scopeGrantError, state.pagesError, state.previewError, state.applyError]
        .filter(Boolean)
        .map((error) => (
          <div
            key={String(error)}
            className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          >
            {error}
          </div>
        ))}
    </section>
  );
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error ?? new Error("file_read_failed"));
    reader.readAsDataURL(file);
  });
}
