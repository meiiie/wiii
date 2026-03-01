/**
 * EventTimeline — chronological event list for a connected peer.
 * Sprint 216: SoulBridgePanel sub-component.
 *
 * Displays peer events as a vertical timeline with color-coded type badges,
 * relative Vietnamese timestamps, and compact payload summaries.
 */
import { motion } from "motion/react";
import { Clock } from "lucide-react";
import type { PeerEvent } from "@/api/soul-bridge";

// ── Helpers ──

function timeAgo(isoTimestamp: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(isoTimestamp).getTime()) / 1000,
  );
  if (seconds < 60) return "vừa xong";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút trước`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} giờ trước`;
  return `${Math.floor(seconds / 86400)} ngày trước`;
}

const EVENT_COLORS: Record<string, string> = {
  ESCALATION: "#ef4444", // red-500
  STATUS_UPDATE: "#3b82f6", // blue-500
  MOOD_CHANGE: "#f59e0b", // amber-500
  ACTION_TAKEN: "#22c55e", // green-500
  DISCOVERY: "#a855f7", // purple-500
  DAILY_REPORT: "#06b6d4", // cyan-500
};
const DEFAULT_COLOR = "#6b7280"; // gray-500

function badgeColor(eventType: string): string {
  return EVENT_COLORS[eventType] ?? DEFAULT_COLOR;
}

/** Render top-level string/number/boolean payload values in compact form */
function renderPayloadSummary(
  payload: Record<string, unknown>,
): React.ReactNode[] {
  return Object.entries(payload)
    .filter(([, v]) => typeof v !== "object" || v === null)
    .slice(0, 6)
    .map(([k, v]) => (
      <span key={k} className="inline-flex gap-1">
        <span className="text-text-tertiary">{k}:</span>
        <span className="text-text">{String(v ?? "—")}</span>
      </span>
    ));
}

// ── Component ──

interface EventTimelineProps {
  events: PeerEvent[];
}

export function EventTimeline({ events }: EventTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Clock className="w-10 h-10 text-text-tertiary mb-3" />
        <p className="text-sm text-text-secondary">Chưa có sự kiện nào</p>
        <p className="text-xs text-text-tertiary mt-1">
          Các sự kiện từ peer sẽ hiển thị tại đây
        </p>
      </div>
    );
  }

  return (
    <div className="relative pl-6">
      {/* Vertical connecting line */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-border" />

      <div className="space-y-4">
        {events.map((event, idx) => {
          const color = badgeColor(event.event_type);
          return (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.03, duration: 0.2 }}
              className="relative"
            >
              {/* Timeline dot */}
              <div
                className="absolute -left-6 top-1.5 w-[10px] h-[10px] rounded-full border-2 border-surface-secondary"
                style={{ backgroundColor: color }}
              />

              {/* Event card */}
              <div className="p-3 rounded-lg bg-surface-secondary border border-border">
                <div className="flex items-center justify-between mb-1.5">
                  {/* Type badge */}
                  <span
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      backgroundColor: `${color}18`,
                      color,
                    }}
                  >
                    {event.event_type}
                  </span>

                  {/* Timestamp */}
                  <span className="text-[10px] text-text-tertiary flex items-center gap-1">
                    <Clock size={10} />
                    {timeAgo(event.timestamp)}
                  </span>
                </div>

                {/* Priority + source */}
                <div className="flex items-center gap-2 text-[10px] text-text-tertiary mb-1.5">
                  {event.priority && (
                    <span>
                      Ưu tiên:{" "}
                      <span className="text-text-secondary">
                        {event.priority}
                      </span>
                    </span>
                  )}
                  {event.source_soul && (
                    <span>
                      Từ:{" "}
                      <span className="text-text-secondary">
                        {event.source_soul}
                      </span>
                    </span>
                  )}
                </div>

                {/* Payload summary */}
                {Object.keys(event.payload).length > 0 && (
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
                    {renderPayloadSummary(event.payload)}
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
