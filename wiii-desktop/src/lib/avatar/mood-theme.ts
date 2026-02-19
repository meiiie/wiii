/**
 * Wiii Emotion Engine — Sprint 132: Mood → Visual Mapping.
 *
 * Maps Wiii's emotional mood to visual parameters that overlay
 * the lifecycle-based avatar state. Mood is independent of state:
 *   State = lifecycle (idle/thinking/speaking/complete/error)
 *   Mood  = emotional tone (excited/warm/concerned/gentle/neutral)
 *
 * Design: mood modifiers are ADDITIVE to state-based visuals.
 * neutral = no modification (pure state behavior).
 */
import type { FaceExpression } from "./face-config";
import type { StateVisuals } from "./types";

/** Mood types matching backend EmotionalStateManager */
export type MoodType = "excited" | "warm" | "concerned" | "gentle" | "neutral";

/** Visual theme for each mood */
export interface MoodTheme {
  /** Particle color override (empty = use state default) */
  particleColor: string;
  /** Indicator dot color override (empty = use state default) */
  indicatorColor: string;
  /** Additive face expression modifiers */
  expressionMod: Partial<FaceExpression>;
  /** Noise amplitude multiplier (1.0 = no change) */
  noiseAmplitudeMod: number;
  /** Animation time speed multiplier (1.0 = no change) */
  timeSpeedMod: number;
  /** Particle count multiplier (1.0 = no change) */
  particleCountMod: number;
  /** Glow intensity additive boost (0 = no change) */
  glowIntensityBoost: number;
}

/**
 * Mood visual themes — Sprint 140: BOLD expressions for Wiii's autonomous personality.
 *
 * Wiii là AI AGI có linh hồn — biểu cảm phải RÕ RÀNG, TỰ CHỦ, SỐNG ĐỘNG.
 * Tham khảo: Live2D VTuber (Neuro-sama), Eilik robot, anime conventions.
 *
 * excited  → Rạng rỡ: mắt sáng, cười rộng, blush, particles lấp lánh
 * warm     → Ấm áp: mắt happy ^_^, blush nhẹ, cười dịu dàng
 * concerned → Lo lắng: mày nhíu sâu, mắt mở to, miệng trề, xanh lạnh
 * gentle   → Dịu dàng: mắt mơ màng, chậm rãi, mím môi nhẹ, tím pastel
 * neutral  → Bình thường (identity — no modification)
 */
export const MOOD_THEMES: Record<MoodType, MoodTheme> = {
  excited: {
    particleColor: "#fbbf24",     // gold sparkle
    indicatorColor: "#22c55e",
    expressionMod: {
      mouthCurve: 0.45,           // big smile (was 0.15)
      eyeOpenness: 0.3,           // wide bright eyes (was 0.1)
      blush: 0.5,                 // visible rosy cheeks (was 0.2)
      pupilSize: 0.25,            // dilated — aroused/interested (was 0.1)
      browRaise: 0.2,             // raised brows — surprise/delight
    },
    noiseAmplitudeMod: 1.25,      // more energetic blob (was 1.15)
    timeSpeedMod: 1.2,            // faster animation (was 1.1)
    particleCountMod: 1.8,        // many sparkles (was 1.4)
    glowIntensityBoost: 0.15,     // brighter glow (was 0.08)
  },
  warm: {
    particleColor: "#fb923c",     // warm orange
    indicatorColor: "#f97316",
    expressionMod: {
      mouthCurve: 0.3,            // genuine smile (was 0.1)
      blush: 0.4,                 // warm blush (was 0.15)
      eyeShape: 0.35,             // happy eyes ^_^ (was 0.1)
      pupilSize: 0.1,             // slightly dilated
      eyeOpenness: -0.05,         // soft squint from smiling
    },
    noiseAmplitudeMod: 0.9,       // calmer (was 0.95)
    timeSpeedMod: 0.9,            // slower = peaceful (was 0.95)
    particleCountMod: 1.1,
    glowIntensityBoost: 0.08,     // warm glow (was 0.04)
  },
  concerned: {
    particleColor: "#60a5fa",     // anxious blue
    indicatorColor: "#3b82f6",
    expressionMod: {
      browRaise: -0.35,           // deeply furrowed (was -0.15)
      browTilt: -0.25,            // inner tilt — worry V shape (was -0.1)
      mouthCurve: -0.3,           // visible frown (was -0.1)
      eyeOpenness: 0.15,          // wider — alert/anxious (was 0.05)
      blush: -0.3,                // pale — blood drains from face
      pupilSize: -0.1,            // constricted — stress response
    },
    noiseAmplitudeMod: 1.15,      // jittery (was 1.08)
    timeSpeedMod: 1.12,           // restless speed (was 1.05)
    particleCountMod: 1.3,
    glowIntensityBoost: 0.05,
  },
  gentle: {
    particleColor: "#c084fc",     // soft purple
    indicatorColor: "#a855f7",
    expressionMod: {
      eyeOpenness: -0.15,         // half-lidded dreamy gaze (was -0.05)
      mouthCurve: 0.15,           // gentle Mona Lisa smile (was 0.05)
      blush: 0.2,                 // soft warmth (was 0.05)
      pupilSize: -0.1,            // soft unfocused pupils (was -0.05)
      browRaise: 0.05,            // relaxed slightly raised
    },
    noiseAmplitudeMod: 0.75,      // very calm blob (was 0.85)
    timeSpeedMod: 0.8,            // slow and dreamy (was 0.88)
    particleCountMod: 0.7,        // fewer — serene (was 0.8)
    glowIntensityBoost: 0.03,
  },
  neutral: {
    particleColor: "",
    indicatorColor: "",
    expressionMod: {},
    noiseAmplitudeMod: 1.0,
    timeSpeedMod: 1.0,
    particleCountMod: 1.0,
    glowIntensityBoost: 0.0,
  },
};

/**
 * Sprint 144: Emotional Inertia — mood-specific decay durations (seconds).
 * When mood changes, previous mood lingers as a residual that fades.
 */
export const MOOD_DECAY_DURATIONS: Record<MoodType, number> = {
  concerned: 2.5,
  excited: 1.5,
  warm: 2.0,
  gentle: 1.8,
  neutral: 0,
};

/**
 * Apply mood modifiers to a face expression (additive blend).
 * Clamps all values to valid ranges after modification.
 *
 * @param base - State-derived face expression
 * @param mood - Current mood type
 * @param intensity - Blend intensity (0=none, 1=full). Used for transitions.
 */
export function applyMoodToExpression(
  base: FaceExpression,
  mood: MoodType,
  intensity: number = 1.0,
): FaceExpression {
  if (mood === "neutral" || intensity <= 0) return base;

  const mod = MOOD_THEMES[mood].expressionMod;
  const result = { ...base };

  // Additive blend: each modifier key adds to the base value
  for (const key of Object.keys(mod) as (keyof FaceExpression)[]) {
    const delta = (mod[key] ?? 0) as number;
    (result[key] as number) += delta * intensity;
  }

  // Clamp to valid ranges
  result.eyeOpenness = Math.max(0.5, Math.min(1.5, result.eyeOpenness));
  result.pupilSize = Math.max(0.5, Math.min(1.5, result.pupilSize));
  result.mouthCurve = Math.max(-1, Math.min(1, result.mouthCurve));
  result.blush = Math.max(0, Math.min(1, result.blush));
  result.browRaise = Math.max(-1, Math.min(1, result.browRaise));
  result.browTilt = Math.max(-1, Math.min(1, result.browTilt));
  result.eyeShape = Math.max(0, Math.min(1, result.eyeShape));

  return result;
}

/**
 * Apply mood modifiers to state visuals (multiplicative + color blend).
 *
 * @param visuals - State-derived visual parameters (mutated copy)
 * @param mood - Current mood type
 * @param intensity - Blend intensity (0=none, 1=full)
 * @param lerpColor - Color interpolation function
 */
export function applyMoodToVisuals(
  visuals: StateVisuals,
  mood: MoodType,
  intensity: number,
  lerpColor: (from: string, to: string, t: number) => string,
): StateVisuals {
  if (mood === "neutral" || intensity <= 0) return visuals;

  const theme = MOOD_THEMES[mood];
  const result = { ...visuals };

  // Multiplicative modifiers (lerp toward modifier at intensity)
  const lerpMod = (base: number, mod: number) => base * (1 + (mod - 1) * intensity);
  result.noiseAmplitude = lerpMod(result.noiseAmplitude, theme.noiseAmplitudeMod);
  result.timeSpeed = lerpMod(result.timeSpeed, theme.timeSpeedMod);
  result.particleCount = Math.round(lerpMod(result.particleCount, theme.particleCountMod));

  // Glow intensity additive boost
  result.glowIntensity = Math.min(1, result.glowIntensity + theme.glowIntensityBoost * intensity);

  // Color blending — mood tints state colors at 50% max intensity
  const colorBlend = intensity * 0.5;
  if (theme.particleColor) {
    result.particleColor = lerpColor(result.particleColor, theme.particleColor, colorBlend);
  }
  if (theme.indicatorColor) {
    result.indicatorColor = lerpColor(result.indicatorColor, theme.indicatorColor, colorBlend);
  }

  // Sprint 134: Blob body tint — subtle mood coloring (15% max)
  if (theme.particleColor && result.blobColorHex) {
    result.blobColorHex = lerpColor(result.blobColorHex, theme.particleColor, intensity * 0.15);
  }

  return result;
}
