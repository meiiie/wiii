/**
 * Connection status badge — shows health status with reconnect action.
 * Sprint 106: Clickable reconnect when disconnected.
 */
import { useConnectionStore } from "@/stores/connection-store";
import { Wifi, WifiOff, Loader2, RefreshCw } from "lucide-react";

interface ConnectionBadgeProps {
  /** Icon-only mode for collapsed sidebar */
  compact?: boolean;
}

export function ConnectionBadge({ compact }: ConnectionBadgeProps) {
  const { status, serverVersion, errorMessage, checkHealth } = useConnectionStore();

  const config = {
    connected: {
      color: "text-green-500",
      bg: "bg-green-500/10",
      icon: Wifi,
      label: "Wiii sẵn sàng",
    },
    degraded: {
      color: "text-yellow-500",
      bg: "bg-yellow-500/10",
      icon: Wifi,
      label: "Mình hơi chập chờn",
    },
    disconnected: {
      color: "text-red-500",
      bg: "bg-red-500/10",
      icon: WifiOff,
      label: "Mình mất tín hiệu",
    },
    checking: {
      color: "text-text-secondary",
      bg: "bg-surface-tertiary",
      icon: Loader2,
      label: "Mình đang lắng nghe...",
    },
  }[status];

  const Icon = config.icon;
  const canReconnect = status === "disconnected" || status === "degraded";

  if (compact) {
    return (
      <button
        onClick={canReconnect ? checkHealth : undefined}
        className={`flex items-center justify-center w-9 h-9 rounded-lg ${config.color} ${canReconnect ? "cursor-pointer hover:bg-surface-tertiary" : "cursor-default"}`}
        title={canReconnect ? "Nhấn để kết nối lại" : errorMessage || `${config.label}${serverVersion ? ` (v${serverVersion})` : ""}`}
        aria-label={canReconnect ? "Kết nối lại" : config.label}
      >
        <Icon
          size={16}
          className={status === "checking" ? "animate-spin" : ""}
        />
      </button>
    );
  }

  return (
    <button
      onClick={canReconnect ? checkHealth : undefined}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${config.bg} ${config.color} ${canReconnect ? "cursor-pointer hover:opacity-80" : "cursor-default"}`}
      title={canReconnect ? "Nhấn để kết nối lại" : errorMessage || `${config.label}${serverVersion ? ` (v${serverVersion})` : ""}`}
      aria-label={canReconnect ? "Kết nối lại" : config.label}
    >
      <Icon
        size={12}
        className={status === "checking" ? "animate-spin" : ""}
      />
      <span>{config.label}</span>
      {canReconnect && (
        <RefreshCw size={10} className="ml-0.5" />
      )}
    </button>
  );
}
