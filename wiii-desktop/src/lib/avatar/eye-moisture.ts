/**
 * Sprint 144: Tear Shimmer & Eye Moisture System.
 * Gradual moisture buildup → glassy eyes → visible tears → tear drop release.
 * Triggered by sadness-related reactions, concerned mood, and soul emotions.
 */

export interface EyeMoistureState {
  moisture: number;  // 0 (dry) → 1 (tears)
  tearDrop: { progress: number; side: "left" | "right" } | null;
}

export interface MoistureTriggers {
  tearUpActive: boolean;     // tear_up reaction is playing
  sighActive: boolean;       // sigh reaction is playing
  isConcerned: boolean;      // concerned mood
  soulSadness: boolean;      // soul emotion indicates sadness (browRaise > 0.2, mouthCurve < -0.1)
}

/** Natural decay rate (moisture per second) */
const DECAY_RATE = 0.1;

/** Moisture accumulation rates per trigger (per second) */
const RATES = {
  tearUp: 0.3,
  sigh: 0.15,
  concerned: 0.05,
  soulSadness: 0.2,
};

/**
 * Update moisture level based on triggers.
 * Mutates state in place.
 */
export function updateMoisture(
  state: EyeMoistureState,
  triggers: MoistureTriggers,
  dt: number,
): void {
  // Accumulation
  let gain = 0;
  if (triggers.tearUpActive) gain += RATES.tearUp;
  if (triggers.sighActive) gain += RATES.sigh;
  if (triggers.isConcerned) gain += RATES.concerned;
  if (triggers.soulSadness) gain += RATES.soulSadness;

  // Decay when no triggers
  const decay = gain > 0 ? 0 : DECAY_RATE;

  state.moisture = Math.max(0, Math.min(1, state.moisture + (gain - decay) * dt));

  // Tear drop lifecycle
  if (state.tearDrop) {
    state.tearDrop.progress += dt / 1.5; // 1.5s slide duration
    if (state.tearDrop.progress >= 1) {
      // Tear finished — reset moisture partially
      state.tearDrop = null;
      state.moisture = Math.min(state.moisture, 0.5);
    }
  } else if (state.moisture >= 1.0) {
    // Spawn tear drop
    state.tearDrop = {
      progress: 0,
      side: Math.random() > 0.5 ? "right" : "left",
    };
  }
}

/**
 * Get visual effects based on moisture level.
 */
export function getMoistureEffects(moisture: number): {
  shineBoost: number;      // extra eye shine opacity (0-0.15)
  scleraBlue: number;      // blue-white tint intensity (0-1)
  lowerShine: number;      // lower-eye moisture shine (0-1)
  tearOpacity: number;     // tear forming at eye corner (0-1)
} {
  if (moisture < 0.3) {
    return { shineBoost: 0, scleraBlue: 0, lowerShine: 0, tearOpacity: 0 };
  }
  if (moisture < 0.5) {
    const t = (moisture - 0.3) / 0.2;
    return { shineBoost: t * 0.15, scleraBlue: t * 0.3, lowerShine: 0, tearOpacity: 0 };
  }
  if (moisture < 0.7) {
    const t = (moisture - 0.5) / 0.2;
    return { shineBoost: 0.15, scleraBlue: 0.3 + t * 0.2, lowerShine: t, tearOpacity: 0 };
  }
  // 0.7 - 1.0: Tear forming
  const t = (moisture - 0.7) / 0.3;
  return { shineBoost: 0.15, scleraBlue: 0.5, lowerShine: 1, tearOpacity: t };
}

/**
 * Generate SVG path for a sliding tear drop.
 * @param startX - X position at outer eye corner
 * @param startY - Y position at outer eye corner
 * @param progress - 0 (at eye) → 1 (at chin level)
 * @param blobRadius - For scaling
 */
export function generateTearDropPath(
  startX: number,
  startY: number,
  progress: number,
  blobRadius: number,
): string {
  const slideDistance = blobRadius * 0.6;
  const tearY = startY + progress * slideDistance;
  const tearSize = blobRadius * 0.04 * (1 - progress * 0.3); // shrinks slightly
  // Teardrop: pointed top, round bottom
  return [
    `M ${startX.toFixed(2)} ${(tearY - tearSize * 1.5).toFixed(2)}`,
    `Q ${(startX + tearSize).toFixed(2)} ${tearY.toFixed(2)}, ${startX.toFixed(2)} ${(tearY + tearSize).toFixed(2)}`,
    `Q ${(startX - tearSize).toFixed(2)} ${tearY.toFixed(2)}, ${startX.toFixed(2)} ${(tearY - tearSize * 1.5).toFixed(2)}`,
    "Z",
  ].join(" ");
}

export function createMoistureState(): EyeMoistureState {
  return { moisture: 0, tearDrop: null };
}
