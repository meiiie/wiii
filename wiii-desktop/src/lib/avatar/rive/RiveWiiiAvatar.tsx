/**
 * RiveWiiiAvatar — Sprint 141: Rive-powered Wiii avatar component.
 *
 * Supports two modes:
 * 1. Full Wiii mode: .riv with state machine "main" + emotion engine inputs
 * 2. Demo mode: Any .riv file with its own state machine (just renders + pointer tracking)
 *
 * The component auto-detects whether the .riv has Wiii-compatible inputs
 * and gracefully degrades to simple rendering if not.
 */
import { memo, useState, useCallback } from "react";
import { useRive } from "@rive-app/react-webgl2";
import type { AvatarState, SoulEmotionData } from "../types";
import type { MoodType } from "../mood-theme";
import { useRiveEmotions } from "./useRiveEmotions";
import { RIVE_FILE_PATH, MAIN_STATE_MACHINE } from "./rive-config";

export interface RiveWiiiAvatarProps {
  state?: AvatarState;
  size?: number;
  className?: string;
  mood?: MoodType;
  soulEmotion?: SoulEmotionData | null;
  /** Override .riv file path */
  riveSrc?: string;
  /** Override state machine name (default: "main") */
  stateMachine?: string;
}

/** Placeholder shown while Rive loads or if .riv file is missing */
function RivePlaceholder({ size, state }: { size: number; state: AvatarState }) {
  const colors: Record<string, string> = {
    idle: "#f97316",
    listening: "#f97316",
    thinking: "#f97316",
    speaking: "#f97316",
    complete: "#22c55e",
    error: "#f59e0b",
  };
  const bg = colors[state] || colors.idle;

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "38%",
        background: bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "white",
        fontWeight: 700,
        fontSize: Math.round(size * 0.35),
        opacity: 0.9,
        animation: state === "thinking" ? "pulse 1.2s ease-in-out infinite" : undefined,
      }}
    >
      W
    </div>
  );
}

function RiveWiiiAvatarInner({
  state = "idle",
  size = 120,
  className = "",
  mood = "neutral",
  soulEmotion = null,
  riveSrc,
  stateMachine,
}: RiveWiiiAvatarProps) {
  const [loadError, setLoadError] = useState(false);
  const smName = stateMachine || MAIN_STATE_MACHINE;
  const isWiiiMode = smName === MAIN_STATE_MACHINE;

  const onLoadError = useCallback((e: Event) => {
    console.error("[RiveWiiiAvatar] .riv load error:", e);
    setLoadError(true);
  }, []);

  const { rive, RiveComponent } = useRive({
    src: riveSrc || RIVE_FILE_PATH,
    stateMachines: smName,
    autoplay: true,
    onLoadError,
  });

  // Only connect emotion engine in Wiii mode (matching inputs)
  useRiveEmotions({
    state,
    mood,
    soulEmotion,
    rive: isWiiiMode ? rive : null,
  });

  // If .riv failed to load, show placeholder
  if (loadError || !RiveComponent) {
    return (
      <div className={`wiii-rive-avatar ${className}`}>
        <RivePlaceholder size={size} state={state} />
      </div>
    );
  }

  return (
    <div
      className={`wiii-rive-avatar ${className}`}
      style={{
        width: size,
        height: size,
        position: "relative",
        overflow: "hidden",
        borderRadius: isWiiiMode ? undefined : "20%",
      }}
    >
      <RiveComponent
        style={{
          width: size,
          height: size,
        }}
      />
    </div>
  );
}

export const RiveWiiiAvatar = memo(RiveWiiiAvatarInner);
