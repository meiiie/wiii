/**
 * Sprint 129: Avatar Preview Page — dev tool for inspecting all states & tiers.
 * Access via: http://localhost:1420?preview=avatar
 */
import { useState } from "react";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import type { AvatarState } from "@/lib/avatar/types";

const ALL_STATES: AvatarState[] = ["idle", "listening", "thinking", "speaking", "complete", "error"];

const STATE_DESCRIPTIONS: Record<AvatarState, string> = {
  idle: "Bình thường — mỉm cười nhẹ, mắt chớp tự nhiên",
  listening: "Lắng nghe — mắt mở to hơn, chân mày nhướn",
  thinking: "Suy nghĩ — mắt nhìn phải-trên, chân mày nhíu",
  speaking: "Trả lời — miệng mở/đóng liên tục (noise-driven)",
  complete: "Hoàn thành — cười rộng, blob xanh lá",
  error: "Lỗi — mắt to, cau mày, blob vàng amber",
};

const SIZES = [14, 20, 24, 32, 40, 48, 64, 80];

export function AvatarPreview() {
  const [activeState, setActiveState] = useState<AvatarState>("idle");

  return (
    <div
      style={{
        background: "#0f0f1a",
        color: "white",
        fontFamily: "system-ui, sans-serif",
        minHeight: "100vh",
        padding: 32,
        overflow: "auto",
      }}
    >
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>
        Wiii Avatar Preview — Sprint 129
      </h1>
      <p style={{ opacity: 0.6, marginBottom: 32, fontSize: 14 }}>
        Face renders on large tier (≥37px). Medium/tiny keep "W" text.
        Thêm <code>?preview=avatar</code> vào URL để xem trang này.
      </p>

      {/* ─── All 6 States at Large Size ─── */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 18, borderBottom: "1px solid #333", paddingBottom: 8, marginBottom: 20 }}>
          6 States @ 64px (Large Tier — Face)
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 24 }}>
          {ALL_STATES.map((state) => (
            <div key={state} style={{ textAlign: "center" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  height: 100,
                  background: "#1a1a2e",
                  borderRadius: 12,
                  border: "1px solid #2a2a3e",
                }}
              >
                <WiiiAvatar state={state} size={64} />
              </div>
              <div style={{ marginTop: 8, fontSize: 13, fontWeight: 600, color: "#f97316" }}>
                {state}
              </div>
              <div style={{ fontSize: 11, opacity: 0.5, marginTop: 2 }}>
                {STATE_DESCRIPTIONS[state]}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Size Comparison ─── */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 18, borderBottom: "1px solid #333", paddingBottom: 8, marginBottom: 20 }}>
          Size Comparison — {activeState}
        </h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
          {ALL_STATES.map((s) => (
            <button
              key={s}
              onClick={() => setActiveState(s)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "none",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
                background: activeState === s ? "#f97316" : "#2a2a3e",
                color: activeState === s ? "white" : "#aaa",
              }}
            >
              {s}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "end", gap: 24, flexWrap: "wrap" }}>
          {SIZES.map((size) => {
            const tier = size <= 20 ? "tiny" : size <= 36 ? "medium" : "large";
            return (
              <div key={size} style={{ textAlign: "center" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    width: Math.max(size + 24, 60),
                    height: Math.max(size + 24, 60),
                    background: "#1a1a2e",
                    borderRadius: 12,
                    border: "1px solid #2a2a3e",
                  }}
                >
                  <WiiiAvatar state={activeState} size={size} />
                </div>
                <div style={{ marginTop: 6, fontSize: 12, fontWeight: 600 }}>{size}px</div>
                <div
                  style={{
                    fontSize: 10,
                    opacity: 0.5,
                    color: tier === "large" ? "#22c55e" : tier === "medium" ? "#f59e0b" : "#888",
                  }}
                >
                  {tier}
                  {tier === "large" ? " (face)" : " (W)"}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ─── Extra Large for Detail Inspection ─── */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 18, borderBottom: "1px solid #333", paddingBottom: 8, marginBottom: 20 }}>
          Detail View — 80px
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 32 }}>
          {ALL_STATES.map((state) => (
            <div key={state} style={{ textAlign: "center" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  height: 140,
                  background: "#1a1a2e",
                  borderRadius: 16,
                  border: "1px solid #2a2a3e",
                }}
              >
                <WiiiAvatar state={state} size={80} />
              </div>
              <div style={{ marginTop: 10, fontSize: 15, fontWeight: 700, color: "#f97316" }}>
                {state}
              </div>
              <div style={{ fontSize: 12, opacity: 0.5, marginTop: 2, maxWidth: 220, margin: "4px auto 0" }}>
                {STATE_DESCRIPTIONS[state]}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
