/**
 * HeartbeatStatus — displays heartbeat scheduler status with manual trigger.
 * Sprint 170: "Linh Hồn Sống"
 */
import { useState } from "react";
import { motion } from "motion/react";
import { Heart, Play } from "lucide-react";
import type { LivingAgentHeartbeat } from "@/api/types";
import { useLivingAgentStore } from "@/stores/living-agent-store";

interface HeartbeatStatusProps {
  heartbeat: LivingAgentHeartbeat;
}

export function HeartbeatStatus({ heartbeat }: HeartbeatStatusProps) {
  const [triggering, setTriggering] = useState(false);
  const triggerHeartbeat = useLivingAgentStore((s) => s.triggerHeartbeat);

  const handleTrigger = async () => {
    setTriggering(true);
    await triggerHeartbeat();
    setTriggering(false);
  };

  return (
    <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <motion.div
            animate={
              heartbeat.is_running
                ? { scale: [1, 1.2, 1] }
                : { scale: 1 }
            }
            transition={
              heartbeat.is_running
                ? { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
                : {}
            }
          >
            <Heart
              className="w-4 h-4"
              style={{
                color: heartbeat.is_running
                  ? "var(--accent)"
                  : "var(--text-tertiary)",
                fill: heartbeat.is_running ? "var(--accent)" : "none",
              }}
            />
          </motion.div>
          <span className="text-sm font-medium text-[var(--text-primary)]">
            Nhịp tim
          </span>
        </div>
        <span
          className="text-[10px] px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: heartbeat.is_running
              ? "rgba(16, 185, 129, 0.1)"
              : "rgba(156, 163, 175, 0.1)",
            color: heartbeat.is_running ? "#10b981" : "#9ca3af",
          }}
        >
          {heartbeat.is_running ? "Đang chạy" : "Dừng"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div>
          <div className="text-[var(--text-tertiary)]">Chu kỳ</div>
          <div className="text-[var(--text-primary)] font-medium">
            {heartbeat.heartbeat_count}
          </div>
        </div>
        <div>
          <div className="text-[var(--text-tertiary)]">Khoảng cách</div>
          <div className="text-[var(--text-primary)] font-medium">
            {Math.round(heartbeat.interval_seconds / 60)}min
          </div>
        </div>
        <div className="col-span-2">
          <div className="text-[var(--text-tertiary)]">Giờ hoạt động</div>
          <div className="text-[var(--text-primary)] font-medium">
            {heartbeat.active_hours}
          </div>
        </div>
      </div>

      <button
        onClick={handleTrigger}
        disabled={triggering}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
          bg-[var(--accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {triggering ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            className="w-3 h-3 border-2 border-white border-t-transparent rounded-full"
          />
        ) : (
          <Play className="w-3 h-3" />
        )}
        {triggering ? "Đang chạy..." : "Kích hoạt nhịp tim"}
      </button>
    </div>
  );
}
