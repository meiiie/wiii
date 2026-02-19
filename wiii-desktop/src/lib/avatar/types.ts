/**
 * Avatar system types — Sprint 115: Living Avatar Foundation.
 */

/** 6 avatar emotional states */
export type AvatarState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "complete"
  | "error";

/** 3-tier size-adaptive rendering */
export type SizeTier = "tiny" | "medium" | "large";

/** Visual parameters for each avatar state */
export interface StateVisuals {
  /** Simplex noise amplitude (0-1) — blob deformation intensity */
  noiseAmplitude: number;
  /** Simplex noise frequency — spatial detail level */
  noiseFrequency: number;
  /** Animation time speed multiplier */
  timeSpeed: number;
  /** Glow opacity (0-1) */
  glowIntensity: number;
  /** Glow hex color */
  glowColor: string;
  /** Blob fill CSS color (for tiny tier / fallback) */
  blobColor: string;
  /** Sprint 134: Blob fill hex color (interpolatable for smooth transitions) */
  blobColorHex: string;
  /** Scale multiplier (1.0 = base size) */
  scale: number;
  /** Indicator dot color */
  indicatorColor: string;
  /** Indicator dot visible */
  indicatorVisible: boolean;
  /** Particle count (large tier only) */
  particleCount: number;
  /** Particle base hex color */
  particleColor: string;
  /** Particle orbit speed (0 = static) */
  particleOrbitSpeed: number;
  /** Particle outward drift speed */
  particleDriftSpeed: number;
  /** CSS border-radius for tiny tier */
  tinyBorderRadius: string;
}

/** A single ambient particle */
export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** 0-1, decreases over time */
  life: number;
  /** Initial life value (seconds) */
  maxLife: number;
  /** Radius in px */
  size: number;
  /** Orbital angle (radians) */
  angle: number;
  /** Distance from center */
  orbitRadius: number;
}

/** Re-export FaceExpression from face-config for convenience */
export type { FaceExpression } from "./face-config";

/**
 * Sprint 142: Reactive micro-expression — brief transient flash on state entry.
 * Decays exponentially and overlays on top of the normal state transition.
 */
export interface MicroReaction {
  type: "surprise" | "nod" | "flinch" | "perk"          // existing (state-triggered)
     | "sparkle_eyes" | "shy" | "panic" | "dreamy"       // Sprint 143 (mood-triggered)
     | "doki" | "hmph"                                    // Sprint 143 (mood-triggered)
     | "blush_deep" | "eye_twitch" | "smirk"             // Sprint 143b (soul-triggered)
     | "tear_up" | "startle" | "giggle" | "sigh";        // Sprint 143b (soul-triggered)
  /** Seconds elapsed since reaction started */
  elapsed: number;
  /** Total duration in seconds */
  duration: number;
}

/** Sprint 143b: Expression echo — aftershock that replays reduced reaction */
export interface ExpressionEcho {
  parentType: string;
  delay: number;      // seconds until echo fires
  duration: number;   // echo duration
  scale: number;      // intensity multiplier (0-1)
  countdown: number;  // decrements, fires at 0
}

/** Re-export MoodType from mood-theme for convenience */
export type { MoodType } from "./mood-theme";

/** Sprint 135: Soul emotion data for avatar expression override */
export interface SoulEmotionData {
  mood: import("./mood-theme").MoodType;
  face: Partial<Record<string, number>>;
  intensity: number;
}

/** Props for the WiiiAvatar React component */
export interface WiiiAvatarProps {
  state?: AvatarState;
  /** Size in px — default 24 */
  size?: number;
  /** Extra CSS class */
  className?: string;
  /** Sprint 132: Emotional mood — affects visual tone (particles, expression, energy) */
  mood?: import("./mood-theme").MoodType;
  /** Sprint 135: Soul emotion — LLM-driven facial expression override */
  soulEmotion?: SoulEmotionData | null;
}
