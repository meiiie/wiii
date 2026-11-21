import { StatusPill } from "./ConnectStatus";
import type { ProviderConnectionFlowStatus } from "./connect-types";
import { providerConnectionFlow } from "./provider-lifecycle";

const labels: Record<ProviderConnectionFlowStatus, string> = {
  disconnected: "Chưa kết nối",
  authorizing: "Đang xác thực",
  waiting: "Đang chờ xác nhận",
  connected: "Đã kết nối",
  expired: "Kết nối hết hạn",
  error: "Không thể kết nối",
  disconnecting: "Đang ngắt kết nối",
};

/** The card and detail show the same account lifecycle, not agent readiness. */
export function ProviderConnectionStatus(props: Parameters<typeof providerConnectionFlow>[0]) {
  if (props.card.provider === "wiii_native") {
    return <StatusPill tone={props.card.tone}>{props.card.status}</StatusPill>;
  }
  const flow = providerConnectionFlow(props);
  return <StatusPill tone={flow.tone}>{labels[flow.status]}</StatusPill>;
}
