/** Derive provider lifecycle and next steps from backend-owned decisions. */
import type {
  WiiiConnectActivationReadinessResponse,
  WiiiConnectAuthorizationUrlDecision,
  WiiiConnectConnectionLifecycleDecision,
  WiiiConnectProviderConnectionRecord,
} from "@/api/types";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { compactText, statusLabel } from "./connect-display";
import type {
  CatalogCard,
  ProviderConnectionFlowStatus,
  ProviderConnectionFlowView,
  ProviderConnectionListState,
  ProviderDisconnectState,
  ProviderLifecycleStage,
  ProviderNextAction,
} from "./connect-types";
import {
  gatewayLifecycleTone,
  providerConnectionSummary,
  providerConnectionTone,
  providerHasUsableConnection,
  readableRequiredNext,
  readinessGatewayStatus,
  readinessReadyForAction,
  readinessReadyForReadonly,
  requirementDisplayLabel,
} from "./provider-readiness";

export function providerLifecycleStages({
  card,
  readiness,
  providerConnection,
  connectionList,
}: {
  card: CatalogCard;
  readiness: WiiiConnectActivationReadinessResponse | undefined;
  providerConnection: WiiiConnectProviderConnectionRecord | undefined;
  connectionList?: ProviderConnectionListState;
}): ProviderLifecycleStage[] {
  const accountPresent = providerHasUsableConnection(providerConnection, readiness);
  const accountState =
    providerConnection?.state ??
    readiness?.connection?.state ??
    (connectionList?.loading ? "waiting" : undefined);
  const registryFromBackend = card.registrySource === "backend";
  const registryTone: CapabilityStatusTone =
    card.provider === "wiii_native" ? card.tone : registryFromBackend ? "ok" : "off";
  const accountTone: CapabilityStatusTone = providerConnection
    ? providerConnectionTone(providerConnection, connectionList?.response)
    : accountPresent
      ? "ok"
      : connectionList?.loading || readinessStateIsConnectable(readiness)
        ? "pending"
        : "off";
  const agentTone: CapabilityStatusTone = readiness
    ? readinessReadyForAction(readiness)
      ? "ok"
      : accountPresent
        ? "warn"
        : readiness.ready_to_connect
          ? "pending"
          : "off"
    : card.agentReady
      ? "ok"
      : "off";

  return [
    {
      id: "registry",
      label: "Registry",
      value:
        card.provider === "wiii_native"
          ? "Runtime native"
          : registryFromBackend
            ? "Đã đăng ký"
            : "Local fallback",
      detail:
        card.provider === "wiii_native"
          ? "Đọc từ snapshot runtime hoặc fallback client."
          : registryFromBackend
            ? "Provider do backend khai báo; UI không tự giữ secret."
            : "Chỉ là catalog tham khảo, chưa được phép kết nối.",
      tone: registryTone,
    },
    {
      id: "account",
      label: "Account",
      value: accountPresent
        ? statusLabel(accountState)
        : connectionList?.loading
          ? "Đang đọc"
          : "Chưa có account",
      detail: accountPresent
        ? providerConnection
          ? providerConnectionSummary(providerConnection)
          : compactText(readiness?.connection?.reason, "Provider account đã được backend ghi nhận.")
        : "Cần OAuth/Connect Link trước khi agent nhìn thấy account này.",
      tone: accountTone,
    },
    {
      id: "agent-policy",
      label: "Agent policy",
      value: readinessReadyForAction(readiness)
        ? "Đã cho phép action"
        : card.agentReady
          ? "Agent-ready"
          : accountPresent
            ? "Chờ policy"
            : "Chưa agent-ready",
      detail: readinessReadyForAction(readiness)
        ? "Action đã qua scope policy và catalog đã kiểm duyệt."
        : accountPresent
          ? "Account đã kết nối nhưng policy/gateway vẫn đang chặn agent."
          : "Agent chưa được phép dùng provider này.",
      tone: agentTone,
    },
    {
      id: "gateway",
      label: "Gateway",
      value: readinessGatewayStatus(readiness),
      detail: compactText(
        readiness?.execution_gateway?.reason,
        "Chưa có quyết định execution gateway.",
      ),
      tone: gatewayLifecycleTone(readiness),
    },
  ];
}

function backendConnectionLifecycle(
  lifecycle: WiiiConnectConnectionLifecycleDecision | null | undefined,
): ProviderConnectionFlowView | null {
  const status = String(lifecycle?.status ?? "").toLowerCase();
  if (
    ![
      "disconnected",
      "authorizing",
      "waiting",
      "connected",
      "expired",
      "error",
      "disconnecting",
    ].includes(status)
  ) {
    return null;
  }
  const flowStatus = status as ProviderConnectionFlowStatus;
  const reason = compactText(lifecycle?.reason, "backend_lifecycle");
  const detail = `Backend lifecycle: ${reason}.`;
  if (flowStatus === "connected") {
    return {
      status: "connected",
      label: "Đã kết nối",
      detail,
      tone: "ok",
    };
  }
  if (flowStatus === "authorizing") {
    return {
      status: "authorizing",
      label: "Đang xác thực OAuth",
      detail,
      tone: "pending",
    };
  }
  if (flowStatus === "waiting") {
    return {
      status: "waiting",
      label: "Đang chờ OAuth hoàn tất",
      detail,
      tone: "pending",
    };
  }
  if (flowStatus === "expired") {
    return {
      status: "expired",
      label: "Kết nối hết hạn",
      detail,
      tone: "warn",
    };
  }
  if (flowStatus === "error") {
    return {
      status: "error",
      label: "Connection lỗi",
      detail,
      tone: "warn",
    };
  }
  if (flowStatus === "disconnecting") {
    return {
      status: "disconnecting",
      label: "Đang ngắt kết nối",
      detail,
      tone: "pending",
    };
  }
  return {
    status: "disconnected",
    label: lifecycle?.ready_to_connect ? "Sẵn sàng kết nối" : "Chưa kết nối",
    detail,
    tone: lifecycle?.ready_to_connect ? "pending" : "off",
  };
}

export function providerConnectionFlow({
  card,
  readiness,
  providerConnection,
  connectionList,
  authorizationDecision,
  authorizationLoading,
  authorizationError,
  disconnectState,
}: {
  card: CatalogCard;
  readiness: WiiiConnectActivationReadinessResponse | undefined;
  providerConnection: WiiiConnectProviderConnectionRecord | undefined;
  connectionList?: ProviderConnectionListState;
  authorizationDecision?: WiiiConnectAuthorizationUrlDecision;
  authorizationLoading?: boolean;
  authorizationError?: string;
  disconnectState?: ProviderDisconnectState;
}): ProviderConnectionFlowView {
  if (card.provider === "wiii_native") {
    return {
      status: card.agentReady ? "connected" : "waiting",
      label: card.agentReady ? "Runtime ready" : "Chờ runtime",
      detail: card.agentReady
        ? "Connection native đã được backend runtime xác nhận."
        : "Chờ snapshot runtime từ host hoặc lượt chat phù hợp.",
      tone: card.agentReady ? "ok" : "pending",
    };
  }

  if (disconnectState?.loading) {
    return {
      status: "disconnecting",
      label: "Đang ngắt kết nối",
      detail: "Backend đang khóa local connection trước khi dọn provider.",
      tone: "pending",
    };
  }

  if (disconnectState?.error || authorizationError || (!readiness && connectionList?.error)) {
    return {
      status: "error",
      label: "Lỗi connection flow",
      detail:
        disconnectState?.error ||
        authorizationError ||
        connectionList?.error ||
        "Backend chưa trả được trạng thái connection.",
      tone: "warn",
    };
  }

  if (authorizationLoading) {
    return {
      status: "authorizing",
      label: "Đang xin Connect Link",
      detail: "Wiii đang yêu cầu backend cấp authorization URL.",
      tone: "pending",
    };
  }

  const canonicalFlow = backendConnectionLifecycle(
    providerConnection?.connection_lifecycle ??
      readiness?.connection_lifecycle ??
      connectionList?.response?.connection_lifecycle,
  );
  if (canonicalFlow && canonicalFlow.status !== "disconnected") {
    return canonicalFlow;
  }

  const connectionState = String(
    providerConnection?.state ?? readiness?.connection?.state ?? "",
  ).toLowerCase();
  const active = Boolean(providerConnection?.active || readiness?.connection?.active);

  if (active || connectionState === "connected") {
    return {
      status: "connected",
      label: "Đã kết nối",
      detail: "Backend đã thấy account active. Agent policy vẫn do readiness/gateway quyết định.",
      tone: "ok",
    };
  }

  if (connectionState === "expired") {
    return {
      status: "expired",
      label: "Kết nối hết hạn",
      detail: "OAuth/account đã hết hạn; cần reconnect trước khi agent thấy action.",
      tone: "warn",
    };
  }

  if (connectionState === "error") {
    return {
      status: "error",
      label: "Connection lỗi",
      detail: compactText(
        providerConnection?.reason ?? readiness?.connection?.reason,
        "Backend báo connection không dùng được.",
      ),
      tone: "warn",
    };
  }

  if (connectionState === "authorizing") {
    return {
      status: "authorizing",
      label: "Đang xác thực OAuth",
      detail: "OAuth flow đã bắt đầu nhưng backend chưa xác nhận account active.",
      tone: "pending",
    };
  }

  if (
    connectionState === "waiting" ||
    connectionState === "pending" ||
    (authorizationDecision?.status === "ready" && authorizationDecision.authorization_url)
  ) {
    return {
      status: "waiting",
      label: "Đang chờ OAuth hoàn tất",
      detail: "Hoàn tất cửa sổ Connect Link; Wiii sẽ poll lại connection thật.",
      tone: "pending",
    };
  }

  if (authorizationDecision?.status === "blocked") {
    return {
      status: "error",
      label: "Connect Link bị chặn",
      detail: compactText(authorizationDecision.reason, "Backend chưa thể phát hành link."),
      tone: "warn",
    };
  }

  if (connectionList?.loading) {
    return {
      status: "waiting",
      label: "Đang đọc connection backend",
      detail: "Wiii đang đồng bộ danh sách account thật từ backend.",
      tone: "pending",
    };
  }

  if (canonicalFlow) {
    return canonicalFlow;
  }

  return {
    status: "disconnected",
    label: readiness?.ready_to_connect ? "Sẵn sàng kết nối" : "Chưa kết nối",
    detail: readiness?.ready_to_connect
      ? "Backend đã sẵn sàng phát hành Connect Link khi người dùng bấm kết nối."
      : "Chưa có account provider hợp lệ trong Wiii Connect.",
    tone: readiness?.ready_to_connect ? "pending" : "off",
  };
}

function readinessStateIsConnectable(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): boolean {
  return Boolean(readiness?.ready_to_connect);
}

export function providerNextAction({
  card,
  readiness,
  providerConnection,
  connectionList,
  authorizationDecision,
  authorizationLoading,
  authorizationError,
  disconnectState,
}: {
  card: CatalogCard;
  readiness: WiiiConnectActivationReadinessResponse | undefined;
  providerConnection: WiiiConnectProviderConnectionRecord | undefined;
  connectionList?: ProviderConnectionListState;
  authorizationDecision?: WiiiConnectAuthorizationUrlDecision;
  authorizationLoading?: boolean;
  authorizationError?: string;
  disconnectState?: ProviderDisconnectState;
}): ProviderNextAction {
  if (card.provider === "wiii_native") {
    return {
      title: card.agentReady ? "Đang dùng được trong runtime" : "Chờ runtime snapshot",
      detail: card.agentReady
        ? "Kết nối native này đã có trong path/capability hiện tại."
        : "Mở một lượt chat hoặc host tương ứng để backend phát snapshot mới.",
      tone: card.agentReady ? "ok" : "pending",
      items: card.requirements?.map(requirementDisplayLabel).slice(0, 3) ?? [],
    };
  }

  if (card.registrySource !== "backend") {
    return {
      title: "Chưa thể kết nối an toàn",
      detail:
        "Provider này mới là catalog cục bộ. Cần backend adapter, vault, policy và audit trước khi mở OAuth thật.",
      tone: "warn",
      items: [],
    };
  }

  const flow = providerConnectionFlow({
    card,
    readiness,
    providerConnection,
    connectionList,
    authorizationDecision,
    authorizationLoading,
    authorizationError,
    disconnectState,
  });

  if (flow.status === "disconnecting") {
    return {
      title: "Đang ngắt kết nối",
      detail: "Wiii đang khóa local connection và chờ backend phản hồi.",
      tone: "pending",
      items: ["Không mở schema mới trong lúc disconnect"],
    };
  }

  if (flow.status === "authorizing" || flow.status === "waiting") {
    return {
      title: flow.label,
      detail: flow.detail,
      tone: "pending",
      items: ["Không hiển thị raw connection id", "Không tự coi là agent-ready"],
    };
  }

  if (flow.status === "expired") {
    return {
      title: "Kết nối hết hạn, cần reconnect",
      detail:
        "Account đã từng tồn tại nhưng không còn dùng được. Bấm Kết nối qua Wiii để phát hành link reconnect.",
      tone: "warn",
      items: ["Reconnect provider", "Giữ agent tools đóng cho tới khi active"],
    };
  }

  if (flow.status === "error") {
    return {
      title: "Sửa lỗi connection flow",
      detail: flow.detail,
      tone: "warn",
      items: ["Đọc lại doctor/readiness", "Không retry action khi chưa ready"],
    };
  }

  if (!readiness && !connectionList?.response) {
    return {
      title: "Đọc trạng thái backend trước",
      detail:
        "Bấm kiểm tra readiness hoặc làm mới trạng thái để Wiii đọc account, policy và gateway thật.",
      tone: "pending",
      items: ["Không dùng dữ liệu đoán từ UI", "Không hiển thị token/provider payload"],
    };
  }

  if (readinessReadyForReadonly(readiness)) {
    return {
      title: "Sẵn sàng cho agent read-only",
      detail:
        "Agent có thể dùng action đọc đã kiểm duyệt; mutation/write vẫn bị chặn ngoài allowlist.",
      tone: "ok",
      items: ["Không tự mở write/admin scope", "Theo dõi audit khi agent gọi tool"],
    };
  }

  if (readinessReadyForAction(readiness)) {
    return {
      title: "Sẵn sàng cho agent action",
      detail:
        "Agent có thể dùng action đã kiểm duyệt. Mutation vẫn phải qua allowlist và approval riêng.",
      tone: "ok",
      items: ["Không tự mở write/admin scope", "Theo dõi audit khi agent gọi tool"],
    };
  }

  const hasAccount = providerHasUsableConnection(providerConnection, readiness);
  if (!hasAccount && readiness?.ready_to_connect) {
    return {
      title: "Mở OAuth/Connect Link với provider",
      detail:
        "Bấm Kết nối qua Wiii để backend cấp link. Sau khi OAuth xong, Wiii sẽ poll lại connection thật.",
      tone: "pending",
      items: readableRequiredNext(readiness),
    };
  }

  if (!hasAccount) {
    return {
      title: "Chưa có account provider",
      detail:
        "Backend chưa thấy account dùng được. Cần hoàn tất connect policy/vault trước khi mở cho agent.",
      tone: "warn",
      items: readableRequiredNext(readiness),
    };
  }

  const nextItems = readableRequiredNext(readiness);
  return {
    title: "Hoàn tất policy/gateway trước khi agent dùng",
    detail:
      "Account đã kết nối, nhưng agent chưa được phép chạy action. Đây là fail-closed đúng: UI không tự cấp quyền thay backend.",
    tone: "warn",
    items: nextItems.length > 0 ? nextItems : ["Kiểm tra scope policy", "Kiểm tra execution gateway"],
  };
}
