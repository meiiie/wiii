/**
 * Sprint 143b: Data-driven micro-reaction registry.
 * Replaces switch-statement based reaction application with a composable table.
 * Each reaction type defines face deltas, easing, and optional echo (aftershock).
 */
import type { FaceExpression } from "./face-config";

/** A single frame modifier applied additively to face during a micro-reaction */
export interface ReactionModifier {
  /** FaceExpression delta values (additive) */
  face: Partial<FaceExpression>;
  /** Optional custom easing: "linear" | "pulse" | "bounce" */
  easing?: "linear" | "pulse" | "bounce";
  /** For pulse easing: frequency in Hz (e.g. 5 for doki heartbeat) */
  pulseHz?: number;
  /** Sprint 144: Disney Principle #1 — face group squash-stretch (1.0 = no change) */
  squash?: { scaleX: number; scaleY: number };
}

/** Registry entry for a micro-reaction type */
export interface ReactionDef {
  duration: number;     // seconds
  modifier: ReactionModifier;
  /** Optional "echo" — reduced repeat that fires after primary (e.g. aftershock) */
  echo?: { delay: number; duration: number; scale: number };
}

export const REACTION_REGISTRY: Record<string, ReactionDef> = {
  // === State-triggered (Sprint 142, squash Sprint 144) ===
  surprise:     { duration: 0.18, modifier: { face: { eyeOpenness: 0.15, pupilSize: 0.1, browRaise: 0.25 }, squash: { scaleX: 0.92, scaleY: 1.10 } } },
  nod:          { duration: 0.3,  modifier: { face: { eyeShape: 0.5, mouthCurve: 0.15 }, squash: { scaleX: 1.02, scaleY: 0.98 } } },
  flinch:       { duration: 0.2,  modifier: { face: { eyeOpenness: -0.15, browTilt: -0.2 }, squash: { scaleX: 1.08, scaleY: 0.93 } } },
  perk:         { duration: 0.15, modifier: { face: { browRaise: 0.1, pupilSize: 0.08 }, squash: { scaleX: 0.97, scaleY: 1.04 } } },

  // === Mood-triggered (Sprint 143) ===
  sparkle_eyes: { duration: 0.35, modifier: { face: { pupilSize: 0.25, eyeOpenness: 0.2, blush: 0.3, eyeShape: 0.3, browRaise: 0.15 } } },
  shy:          { duration: 0.4,  modifier: { face: { blush: 0.5, eyeOpenness: -0.1, mouthCurve: 0.1, browRaise: -0.05 } } },
  panic:        { duration: 0.25, modifier: { face: { eyeOpenness: 0.25, pupilSize: -0.15, browTilt: -0.3, browRaise: -0.2, mouthOpenness: 0.15 } } },
  dreamy:       { duration: 0.5,  modifier: { face: { eyeOpenness: -0.15, pupilSize: -0.1, mouthCurve: 0.15, blush: 0.15 } } },
  doki:         { duration: 0.4,  modifier: { face: { blush: 0.4, pupilSize: 0.2, eyeOpenness: 0.1 }, easing: "pulse", pulseHz: 5 } },
  hmph:         { duration: 0.3,  modifier: { face: { eyeOpenness: -0.2, mouthCurve: -0.15, browRaise: 0.15, browTilt: 0.1 } } },

  // === Sprint 143b: New mood + soul triggered ===
  blush_deep:   { duration: 0.45, modifier: { face: { blush: 0.7, eyeOpenness: -0.12, mouthCurve: 0.08, browRaise: -0.1 } },
                  echo: { delay: 0.5, duration: 0.3, scale: 0.4 } },
  eye_twitch:   { duration: 0.30, modifier: { face: { eyeOpenness: -0.25, browTilt: 0.15 }, easing: "bounce" } },
  smirk:        { duration: 0.35, modifier: { face: { mouthCurve: 0.25, browRaise: 0.2, browTilt: 0.15, eyeOpenness: -0.05 } } },
  tear_up:      { duration: 0.6,  modifier: { face: { eyeOpenness: 0.1, blush: 0.2, mouthCurve: -0.1, browRaise: 0.3, browTilt: -0.2 } } },
  startle:      { duration: 0.12, modifier: { face: { eyeOpenness: 0.3, pupilSize: -0.2, browRaise: 0.4, mouthOpenness: 0.2 }, easing: "bounce", squash: { scaleX: 0.90, scaleY: 1.12 } },
                  echo: { delay: 0.15, duration: 0.2, scale: 0.3 } },
  giggle:       { duration: 0.5,  modifier: { face: { eyeShape: 0.4, mouthCurve: 0.3, mouthOpenness: 0.12, blush: 0.2 }, easing: "pulse", pulseHz: 8, squash: { scaleX: 1.04, scaleY: 0.97 } } },
  sigh:         { duration: 0.7,  modifier: { face: { eyeOpenness: -0.1, mouthOpenness: 0.08, browRaise: -0.15, mouthCurve: -0.05 } } },
};

/**
 * Compute intensity for a given reaction at elapsed time, respecting easing.
 * @returns Intensity value (typically 0-1, can overshoot with bounce)
 */
export function computeReactionIntensity(
  elapsed: number,
  duration: number,
  easing?: "linear" | "pulse" | "bounce",
  pulseHz?: number,
): number {
  const t = elapsed / duration;
  let intensity = Math.max(0, 1 - t); // linear decay baseline

  if (easing === "pulse" && pulseHz) {
    const pulse = Math.sin(elapsed * pulseHz * Math.PI * 2);
    const pulseBoost = Math.max(0, pulse);
    intensity = intensity * (0.7 + 0.3 * pulseBoost);
  } else if (easing === "bounce") {
    if (t < 0.3) {
      intensity = 1.2 * (1 - t / 0.3);
    } else {
      intensity = Math.max(0, 1 - t) * 0.8;
    }
  }

  return intensity;
}
