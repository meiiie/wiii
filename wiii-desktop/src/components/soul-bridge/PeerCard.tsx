/**
 * PeerCard — status card for a connected SubSoul peer.
 * Sprint 216: SoulBridgePanel sub-component.
 *
 * Displays connection state, agent card info, latest status summary,
 * capability badges, and event count. Click navigates to events tab.
 */
import { motion } from "motion/react";
import { Circle, Wifi, WifiOff, Activity } from "lucide-react";
import type { SoulBridgePeer, PeerDetail } from "@/api/soul-bridge";

// ── Helpers ──

interface ConnectionStyle {
  color: string;
  bg: string;
  label: string;
  icon: typeof Wifi;
}

function connectionStyle(
  state: SoulBridgePeer["state"],
): ConnectionStyle {
  switch (state) {
    case "CONNECTED":
      return {
        color: "#22c55e",
        bg: "rgba(34,197,94,0.1)",
        label: "Đã kết nối",
        icon: Wifi,
      };
    case "CONNECTING":
    case "RECONNECTING":
      return {
        color: "#f59e0b",
        bg: "rgba(245,158,11,0.1)",
        label: state === "CONNECTING" ? "Đang kết nối" : "Đang kết nối lại",
        icon: Wifi,
      };
    case "DISCONNECTED":
    default:
      return {
        color: "#ef4444",
        bg: "rgba(239,68,68,0.1)",
        label: "Mất kết nối",
        icon: WifiOff,
      };
  }
}

/** Extract human-readable status fields from latest_status (risk_score, mood, etc.) */
function statusSummary(
  latest: Record<string, unknown> | null,
): { label: string; value: string }[] {
  if (!latest) return [];
  const items: { label: string; value: string }[] = [];
  if (latest.risk_score !== undefined) {
    items.push({ label: "Risk", value: String(latest.risk_score) });
  }
  if (latest.mood !== undefined) {
    items.push({ label: "Mood", value: String(latest.mood) });
  }
  if (latest.status !== undefined) {
    items.push({ label: "Trạng thái", value: String(latest.status) });
  }
  if (latest.uptime !== undefined) {
    items.push({ label: "Uptime", value: String(latest.uptime) });
  }
  return items.slice(0, 4);
}

// ── Component ──

interface PeerCardProps {
  peerId: string;
  peer: SoulBridgePeer;
  detail: PeerDetail | null;
  onClick: () => void;
}

export function PeerCard({ peerId, peer, detail, onClick }: PeerCardProps) {
  const conn = connectionStyle(peer.state);
  const ConnIcon = conn.icon;
  const card = detail?.card ?? null;
  const name = card?.name ?? peerId;
  const description = card?.description ?? null;
  const capabilities = card?.capabilities ?? [];
  const status = statusSummary(detail?.latest_status ?? null);
  const eventCount = detail?.event_count ?? 0;

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className="w-full text-left p-4 rounded-xl bg-surface-secondary border border-border
        hover:border-[var(--accent)]/40 transition-colors cursor-pointer"
    >
      {/* Header: name + connection dot */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Connection status dot */}
          <div className="shrink-0 relative">
            <Circle
              size={10}
              fill={conn.color}
              color={conn.color}
            />
            {peer.state === "CONNECTED" && (
              <motion.div
                className="absolute inset-0 rounded-full"
                style={{ backgroundColor: conn.color }}
                animate={{ scale: [1, 1.8, 1], opacity: [0.5, 0, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            )}
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-text truncate">{name}</h3>
            {description && (
              <p className="text-xs text-text-tertiary truncate mt-0.5">
                {description}
              </p>
            )}
          </div>
        </div>

        {/* Connection badge */}
        <span
          className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1"
          style={{ backgroundColor: conn.bg, color: conn.color }}
        >
          <ConnIcon size={10} />
          {conn.label}
        </span>
      </div>

      {/* Latest status summary */}
      {status.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 mb-2.5">
          {status.map((s) => (
            <div key={s.label} className="flex items-center gap-1.5 text-xs">
              <span className="text-text-tertiary">{s.label}:</span>
              <span className="text-text font-medium">{s.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Capabilities */}
      {capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {capabilities.slice(0, 5).map((cap) => (
            <span
              key={cap}
              className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)]"
            >
              {cap}
            </span>
          ))}
          {capabilities.length > 5 && (
            <span className="text-[10px] text-text-tertiary">
              +{capabilities.length - 5}
            </span>
          )}
        </div>
      )}

      {/* Event count footer */}
      <div className="flex items-center gap-1.5 text-xs text-text-tertiary pt-1.5 border-t border-border">
        <Activity size={12} />
        <span>
          {eventCount} sự kiện
        </span>
      </div>
    </motion.button>
  );
}
