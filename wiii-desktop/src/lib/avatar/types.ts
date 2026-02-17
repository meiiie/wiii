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
  /** Blob fill CSS color */
  blobColor: string;
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

/** Props for the WiiiAvatar React component */
export interface WiiiAvatarProps {
  state?: AvatarState;
  /** Size in px — default 24 */
  size?: number;
  /** Extra CSS class */
  className?: string;
}
