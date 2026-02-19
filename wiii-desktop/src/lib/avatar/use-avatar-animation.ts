/**
 * Avatar animation hook — Sprint 115: Living Avatar Foundation.
 * Sprint 119: Reduced motion support (WCAG 2.2), smooth color transitions.
 * Sprint 129: SVG Face animation (eyes, mouth, eyebrows, blink).
 * Sprint 130: Breathing, blush, happy eyes, squash-stretch, mouse tracking.
 *
 * Sprint 132: Mood crossfade (emotion engine integration).
 * Sprint 133: Idle personality system, iris mood tinting, speaking face tune.
 * Sprint 142: "Có Hồn" — staggered transitions, asymmetry, momentum,
 *   micro-reactions, richer idle, speaking rhythm.
 *
 * Manages: rAF loop, state interpolation, IntersectionObserver visibility,
 * direct DOM updates for SVG path (bypasses React at 60fps), canvas DPI,
 * face expression interpolation, blink controller, speaking mouth oscillation,
 * breathing sway, blush opacity, happy-eye crossfade, spring transitions,
 * mouse pupil tracking, idle personality poses, iris mood coloring.
 */
import { useRef, useEffect, useCallback, useState } from "react";
import type { AvatarState, Particle, SoulEmotionData, MicroReaction, ExpressionEcho } from "./types";
import type { StateVisuals } from "./types";
import { STATE_CONFIG, getSizeTier, getBlobResolution } from "./state-config";
import { generateBlobPath } from "./blob-geometry";
import { spawnParticle, updateParticles, renderParticles, spawnBurst, spawnFallingBurst, updateBurstParticles, renderBurstParticles } from "./particle-system";
import type { BurstParticle } from "./particle-system";
import { FACE_EXPRESSIONS, lerpFaceExpression, staggeredLerpFace } from "./face-config";
import type { FaceExpression } from "./face-config";
import { getFaceDimensions, generateMouthPath, generateCatMouthPath, generateDotMouthPath, generateWavyMouthPath, generatePoutMouthPath, generateKnockedOutEyePath } from "./face-geometry";
import { BlinkController } from "./blink-controller";
import { getNoiseGenerator } from "./noise-engine";
import { getIndicatorForState } from "./manga-indicators";
import type { MangaIndicatorType } from "./manga-indicators";
import { applyMoodToExpression, applyMoodToVisuals, MOOD_DECAY_DURATIONS } from "./mood-theme";
import type { MoodType } from "./mood-theme";
import { REACTION_REGISTRY, computeReactionIntensity } from "./micro-reaction-registry";
import { GazeController } from "./gaze-controller";
import { REACTION_CHAINS, advanceChain, createChainPlayback } from "./reaction-chains";
import type { ChainPlayback } from "./reaction-chains";
import { createMoistureState, updateMoisture, getMoistureEffects, generateTearDropPath } from "./eye-moisture";
import type { EyeMoistureState } from "./eye-moisture";
import { generateTeethPath, generateTonguePath } from "./face-geometry";

/** Global per-instance seed counter */
let _seedCounter = 0;

/** Cubic ease-in-out for smooth state transitions */
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** Linearly interpolate between two values */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Interpolate between two hex color strings (e.g. "#f97316" → "#22c55e") */
export function lerpHexColor(from: string, to: string, t: number): string {
  if (from === to || t >= 1) return to;
  if (t <= 0) return from;
  const f = parseInt(from.slice(1), 16);
  const t2 = parseInt(to.slice(1), 16);
  if (isNaN(f) || isNaN(t2)) return to;
  const r = Math.round(lerp((f >> 16) & 0xff, (t2 >> 16) & 0xff, t));
  const g = Math.round(lerp((f >> 8) & 0xff, (t2 >> 8) & 0xff, t));
  const b = Math.round(lerp(f & 0xff, t2 & 0xff, t));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

/**
 * Sprint 130: Damped spring ease for squash-and-stretch transitions.
 * Overshoots then settles — feels organic.
 *
 * @param t - Progress 0→1
 * @param stiffness - Spring stiffness (higher = faster settle)
 * @param damping - Oscillation frequency
 * @returns Value that overshoots then converges to 1.0
 */
export function springEase(t: number, stiffness: number = 6, damping: number = 0.8): number {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  return 1 - Math.exp(-stiffness * t) * Math.cos(damping * 2 * Math.PI * t);
}

/** Interpolate all visual parameters between two states */
function lerpVisuals(from: StateVisuals, to: StateVisuals, t: number): StateVisuals {
  const e = easeInOutCubic(t);
  return {
    noiseAmplitude: lerp(from.noiseAmplitude, to.noiseAmplitude, e),
    noiseFrequency: lerp(from.noiseFrequency, to.noiseFrequency, e),
    timeSpeed: lerp(from.timeSpeed, to.timeSpeed, e),
    glowIntensity: lerp(from.glowIntensity, to.glowIntensity, e),
    glowColor: lerpHexColor(from.glowColor, to.glowColor, e),
    blobColor: to.blobColor,  // CSS variable — kept for tiny tier
    blobColorHex: lerpHexColor(from.blobColorHex, to.blobColorHex, e), // Sprint 134: smooth transition
    scale: lerp(from.scale, to.scale, e),
    indicatorColor: lerpHexColor(from.indicatorColor, to.indicatorColor, e),
    indicatorVisible: to.indicatorVisible,
    particleCount: Math.round(lerp(from.particleCount, to.particleCount, e)),
    particleColor: lerpHexColor(from.particleColor, to.particleColor, e),
    particleOrbitSpeed: lerp(from.particleOrbitSpeed, to.particleOrbitSpeed, e),
    particleDriftSpeed: lerp(from.particleDriftSpeed, to.particleDriftSpeed, e),
    tinyBorderRadius: to.tinyBorderRadius,
  };
}

/** Sprint 130: ViewBox padding ratio (must match WiiiAvatar.tsx) */
const VIEWBOX_PAD_RATIO = 0.15;

/** Sprint 130: Mouse disinterest distance — beyond this, mouse tracking fades */
const MOUSE_DISINTEREST_DISTANCE = 400;

/** Sprint 130: Mouse influence blend ratio (vs state-based pupil offset) */
const MOUSE_BLEND_RATIO = 0.6;

// ─── Sprint 133: Idle Personality System ───────────────────────────
// Spontaneous micro-expressions when idle, making Wiii feel inhabited.

/** Possible idle personality poses — Sprint 143b: added daydream, fidget, stretch, pout, nuzzle */
type IdlePose = "none" | "curious_right" | "curious_left" | "widen" | "squint" | "glance_up" | "head_tilt" | "hum" | "yawn"
  | "daydream" | "fidget" | "stretch" | "pout" | "nuzzle";

interface IdlePoseState {
  pose: IdlePose;
  /** 0→blendIn→hold→blendOut→done */
  elapsed: number;
  blendIn: number;   // duration of blend-in
  hold: number;      // duration of hold at full
  blendOut: number;  // duration of blend-out
}

/** Calculate idle pose intensity (0→1→1→0 envelope) */
function idlePoseIntensity(s: IdlePoseState): number {
  if (s.pose === "none") return 0;
  const { elapsed, blendIn, hold, blendOut } = s;
  if (elapsed < blendIn) return elapsed / blendIn;
  if (elapsed < blendIn + hold) return 1;
  const fadeElapsed = elapsed - blendIn - hold;
  if (fadeElapsed < blendOut) return 1 - fadeElapsed / blendOut;
  return 0;
}

/** Total duration of an idle pose */
function idlePoseDuration(s: IdlePoseState): number {
  return s.blendIn + s.hold + s.blendOut;
}

/** Random interval between idle poses (8-18 seconds) */
function randomIdleInterval(): number {
  return 8 + Math.random() * 10;
}

/** Sprint 143b: Weighted idle pose selection — common vs rare poses */
const IDLE_WEIGHTS: Record<Exclude<IdlePose, "none">, number> = {
  curious_right: 15,
  curious_left: 15,
  widen: 12,
  squint: 12,
  glance_up: 12,
  head_tilt: 15,
  hum: 14,
  yawn: 5,
  // Sprint 143b: New poses
  daydream: 8,
  fidget: 10,
  stretch: 4,
  pout: 7,
  nuzzle: 5,
};

/** Sprint 143: Pick a weighted random idle pose — mood biases the weights */
function pickIdlePose(mood: MoodType = "neutral"): IdlePoseState {
  const weights = { ...IDLE_WEIGHTS };
  // Sprint 143/143b: Mood biases — adjust weights per mood
  switch (mood) {
    case "excited":
      weights.widen *= 2;
      weights.squint *= 0.3;
      weights.fidget *= 2;
      weights.stretch *= 0;
      break;
    case "warm":
      weights.hum *= 2;
      weights.head_tilt *= 1.5;
      weights.nuzzle *= 3;
      weights.daydream *= 1.5;
      break;
    case "concerned":
      weights.squint *= 2;
      weights.hum *= 0.3;
      weights.fidget *= 3;
      weights.pout *= 2;
      weights.nuzzle *= 0;
      break;
    case "gentle":
      weights.head_tilt *= 2;
      weights.yawn *= 2;
      weights.daydream *= 3;
      weights.nuzzle *= 2;
      weights.fidget *= 0.2;
      break;
  }
  const entries = Object.entries(weights) as [Exclude<IdlePose, "none">, number][];
  const totalWeight = entries.reduce((sum, [, w]) => sum + w, 0);
  let roll = Math.random() * totalWeight;
  let pose: Exclude<IdlePose, "none"> = entries[0][0];
  for (const [p, w] of entries) {
    roll -= w;
    if (roll <= 0) { pose = p; break; }
  }
  switch (pose) {
    case "curious_right":
    case "curious_left":
      return { pose, elapsed: 0, blendIn: 0.3, hold: 1.2, blendOut: 0.5 };
    case "widen":
      return { pose, elapsed: 0, blendIn: 0.2, hold: 0.6, blendOut: 0.4 };
    case "squint":
      return { pose, elapsed: 0, blendIn: 0.3, hold: 0.8, blendOut: 0.5 };
    case "glance_up":
      return { pose, elapsed: 0, blendIn: 0.25, hold: 1.0, blendOut: 0.4 };
    case "head_tilt":
      return { pose, elapsed: 0, blendIn: 0.3, hold: 1.2, blendOut: 0.5 };
    case "hum":
      return { pose, elapsed: 0, blendIn: 0.25, hold: 1.0, blendOut: 0.55 };
    case "yawn":
      return { pose, elapsed: 0, blendIn: 0.4, hold: 1.5, blendOut: 0.6 };
    // Sprint 143b: New poses
    case "daydream":
      return { pose, elapsed: 0, blendIn: 0.5, hold: 2.0, blendOut: 0.6 };
    case "fidget":
      return { pose, elapsed: 0, blendIn: 0.1, hold: 0.3, blendOut: 0.15 };
    case "stretch":
      return { pose, elapsed: 0, blendIn: 0.4, hold: 1.8, blendOut: 0.7 };
    case "pout":
      return { pose, elapsed: 0, blendIn: 0.2, hold: 1.0, blendOut: 0.4 };
    case "nuzzle":
      return { pose, elapsed: 0, blendIn: 0.35, hold: 1.5, blendOut: 0.5 };
    default:
      return { pose: "none", elapsed: 0, blendIn: 0, hold: 0, blendOut: 0 };
  }
}

/** Idle pose facial modifiers — Sprint 143b: added daydream, fidget, stretch, pout, nuzzle */
const IDLE_POSE_MODS: Record<Exclude<IdlePose, "none">, Partial<FaceExpression> & { _pupilX?: number; _pupilY?: number }> = {
  curious_right: { browRaise: 0.25, eyeOpenness: 0.08, _pupilX: 0.5, _pupilY: -0.15 },
  curious_left:  { browRaise: 0.25, eyeOpenness: 0.08, _pupilX: -0.5, _pupilY: -0.15 },
  widen:         { eyeOpenness: 0.15, pupilSize: 0.1 },
  squint:        { eyeOpenness: -0.12, mouthCurve: 0.12 },
  glance_up:     { browRaise: 0.15, _pupilX: 0, _pupilY: -0.45 },
  head_tilt:     { browRaise: 0.1, mouthCurve: 0.15, _pupilX: 0.25, _pupilY: -0.1 },
  hum:           { eyeOpenness: -0.08, mouthWidth: 0.15 },
  yawn:          { mouthOpenness: 0.55, eyeOpenness: -0.2, browRaise: 0.3 },
  // Sprint 143b: New poses
  daydream:      { eyeOpenness: -0.1, pupilSize: -0.08, mouthCurve: 0.1, blush: 0.1, _pupilX: 0.3, _pupilY: -0.3 },
  fidget:        { browRaise: 0.08, _pupilX: -0.4, _pupilY: 0 },
  stretch:       { mouthOpenness: 0.4, eyeOpenness: -0.25, browRaise: 0.35, mouthWidth: 1.3 },
  pout:          { mouthCurve: -0.2, mouthWidth: 0.7, browRaise: -0.1 },
  nuzzle:        { eyeOpenness: -0.3, mouthCurve: 0.2, browRaise: -0.05, _pupilX: 0.15 },
};

/** Sprint 133: Iris CSS filter per mood for emotional eye coloring */
const MOOD_IRIS_FILTER: Record<MoodType, string> = {
  neutral: "",
  excited: "saturate(1.3) brightness(1.1)",
  warm: "saturate(1.15)",
  concerned: "hue-rotate(200deg) saturate(0.8)",
  gentle: "hue-rotate(280deg) saturate(0.7) brightness(1.05)",
};

export interface AnimationResult {
  svgRef: React.RefObject<SVGSVGElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  pathRef: React.RefObject<SVGPathElement | null>;
  /** Sprint 129: Face element refs for direct DOM manipulation */
  faceGroupRef: React.RefObject<SVGGElement | null>;
  leftEyeRef: React.RefObject<SVGGElement | null>;
  rightEyeRef: React.RefObject<SVGGElement | null>;
  /** Sprint 131: Iris group refs (gaze tracking, clipped to sclera) */
  leftIrisRef: React.RefObject<SVGGElement | null>;
  rightIrisRef: React.RefObject<SVGGElement | null>;
  leftBrowRef: React.RefObject<SVGLineElement | null>;
  rightBrowRef: React.RefObject<SVGLineElement | null>;
  mouthRef: React.RefObject<SVGPathElement | null>;
  /** Sprint 130: Blush ellipse refs */
  leftBlushRef: React.RefObject<SVGEllipseElement | null>;
  rightBlushRef: React.RefObject<SVGEllipseElement | null>;
  /** Sprint 130: Happy eye arc refs */
  leftHappyRef: React.RefObject<SVGPathElement | null>;
  rightHappyRef: React.RefObject<SVGPathElement | null>;
  /** Sprint 131 Phase 4: Manga indicator group refs */
  sparkleRef: React.RefObject<SVGGElement | null>;
  thoughtRef: React.RefObject<SVGGElement | null>;
  sweatRef: React.RefObject<SVGGElement | null>;
  musicRef: React.RefObject<SVGGElement | null>;
  /** Sprint 143: New manga indicator refs */
  heartRef: React.RefObject<SVGGElement | null>;
  exclaimRef: React.RefObject<SVGGElement | null>;
  questionRef: React.RefObject<SVGGElement | null>;
  /** Sprint 143b: New manga indicator refs */
  angerVeinRef: React.RefObject<SVGGElement | null>;
  gloomRef: React.RefObject<SVGGElement | null>;
  spiralRef: React.RefObject<SVGGElement | null>;
  flowerRef: React.RefObject<SVGGElement | null>;
  zzzRef: React.RefObject<SVGGElement | null>;
  fireRef: React.RefObject<SVGGElement | null>;
  /** Sprint 143: Star/heart pupil overlay refs */
  leftStarRef: React.RefObject<SVGPathElement | null>;
  rightStarRef: React.RefObject<SVGPathElement | null>;
  leftHeartRef: React.RefObject<SVGPathElement | null>;
  rightHeartRef: React.RefObject<SVGPathElement | null>;
  /** Sprint 144: Knocked-out eye (×) overlay refs */
  leftKORef: React.RefObject<SVGPathElement | null>;
  rightKORef: React.RefObject<SVGPathElement | null>;
  /** Sprint 144: Mouth interior refs */
  teethRef: React.RefObject<SVGPathElement | null>;
  tongueRef: React.RefObject<SVGPathElement | null>;
  mouthGlintRef: React.RefObject<SVGCircleElement | null>;
  /** Sprint 144: Tear + moisture refs */
  leftTearRef: React.RefObject<SVGPathElement | null>;
  rightTearRef: React.RefObject<SVGPathElement | null>;
  leftMoistureRef: React.RefObject<SVGCircleElement | null>;
  rightMoistureRef: React.RefObject<SVGCircleElement | null>;
  glowOpacity: number;
  glowColor: string;
  blobColor: string;
  scale: number;
  indicatorColor: string;
  indicatorVisible: boolean;
}

// ─── Sprint 135/140: Soul Emotion Constants ─────────────────────
/** Duration (seconds) for soul emotion to blend in */
const SOUL_BLEND_DURATION = 0.35;  // Sprint 140: snappier (was 0.5)
/** Seconds after last emotion before decay starts */
const SOUL_DECAY_START = 12.0;     // Sprint 140: hold longer — Wiii savors emotions (was 5.0)
/** Duration (seconds) of the decay-to-zero phase */
const SOUL_DECAY_DURATION = 4.0;   // Sprint 140: gentle fade (was 2.0)

export function useAvatarAnimation(
  state: AvatarState,
  size: number,
  mood: MoodType = "neutral",
  soulEmotion: SoulEmotionData | null = null,
): AnimationResult {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pathRef = useRef<SVGPathElement | null>(null);

  // Sprint 129: Face element refs
  const faceGroupRef = useRef<SVGGElement | null>(null);
  const leftEyeRef = useRef<SVGGElement | null>(null);
  const rightEyeRef = useRef<SVGGElement | null>(null);
  // Sprint 131: Iris group refs (gaze tracking inside clipped sclera)
  const leftIrisRef = useRef<SVGGElement | null>(null);
  const rightIrisRef = useRef<SVGGElement | null>(null);
  const leftBrowRef = useRef<SVGLineElement | null>(null);
  const rightBrowRef = useRef<SVGLineElement | null>(null);
  const mouthRef = useRef<SVGPathElement | null>(null);

  // Sprint 130: Blush + happy eye refs
  const leftBlushRef = useRef<SVGEllipseElement | null>(null);
  const rightBlushRef = useRef<SVGEllipseElement | null>(null);
  const leftHappyRef = useRef<SVGPathElement | null>(null);
  const rightHappyRef = useRef<SVGPathElement | null>(null);

  // Sprint 131 Phase 4: Manga indicator group refs
  const sparkleRef = useRef<SVGGElement | null>(null);
  const thoughtRef = useRef<SVGGElement | null>(null);
  const sweatRef = useRef<SVGGElement | null>(null);
  const musicRef = useRef<SVGGElement | null>(null);
  // Sprint 143: New manga indicator refs
  const heartRef = useRef<SVGGElement | null>(null);
  const exclaimRef = useRef<SVGGElement | null>(null);
  const questionRef = useRef<SVGGElement | null>(null);
  // Sprint 143b: New manga indicator refs
  const angerVeinRef = useRef<SVGGElement | null>(null);
  const gloomRef = useRef<SVGGElement | null>(null);
  const spiralRef = useRef<SVGGElement | null>(null);
  const flowerRef = useRef<SVGGElement | null>(null);
  const zzzRef = useRef<SVGGElement | null>(null);
  const fireRef = useRef<SVGGElement | null>(null);

  // Sprint 143: Star/heart pupil overlay refs
  const leftStarRef = useRef<SVGPathElement | null>(null);
  const rightStarRef = useRef<SVGPathElement | null>(null);
  const leftHeartRef = useRef<SVGPathElement | null>(null);
  const rightHeartRef = useRef<SVGPathElement | null>(null);
  // Sprint 144: Knocked-out eye (×) overlay refs
  const leftKORef = useRef<SVGPathElement | null>(null);
  const rightKORef = useRef<SVGPathElement | null>(null);
  // Sprint 143+144: Anime eye overlay state — tracks which overlay is active + fade progress
  const animeEyeRef = useRef<{ type: "none" | "star" | "heart" | "cross"; opacity: number }>({ type: "none", opacity: 0 });

  // Sprint 144: Mouth interior refs
  const teethRef = useRef<SVGPathElement | null>(null);
  const tongueRef = useRef<SVGPathElement | null>(null);
  const mouthGlintRef = useRef<SVGCircleElement | null>(null);
  // Sprint 144: Tear + moisture refs
  const leftTearRef = useRef<SVGPathElement | null>(null);
  const rightTearRef = useRef<SVGPathElement | null>(null);
  const leftMoistureRef = useRef<SVGCircleElement | null>(null);
  const rightMoistureRef = useRef<SVGCircleElement | null>(null);

  // Sprint 144: Gaze controller (replaces noise drift)
  const gazeControllerRef = useRef(new GazeController());
  // Sprint 144: Reaction chain playback
  const chainPlaybackRef = useRef<ChainPlayback | null>(null);
  // Sprint 144: Emotion residual (momentum from previous mood)
  const emotionResidualRef = useRef<{ mood: MoodType; startIntensity: number; elapsed: number; decayDuration: number } | null>(null);
  // Sprint 144: Eye moisture state
  const moistureRef = useRef<EyeMoistureState>(createMoistureState());

  // Sprint 129: Blink controller + face expression tracking
  const blinkCtrlRef = useRef(new BlinkController(FACE_EXPRESSIONS[state]?.blinkRate ?? 15));
  const fromFaceRef = useRef<FaceExpression>(FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle);
  const toFaceRef = useRef<FaceExpression>(FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle);

  // Sprint 130: Spring transition tracking
  const springProgressRef = useRef(1); // 1 = fully settled

  // Sprint 131 Phase 6: Micro-expression timers
  const browBounceRef = useRef(0); // 0 = no bounce, >0 = decaying bounce amount
  const shinePulseRef = useRef(0); // accumulated time for periodic pulse

  // Sprint 132: Mood transition tracking
  const prevMoodRef = useRef<MoodType>(mood);
  const moodTransitionRef = useRef(1); // 1 = settled
  const fromMoodRef = useRef<MoodType>(mood);
  const toMoodRef = useRef<MoodType>(mood);

  // Sprint 130: Mouse tracking (normalized target for pupil)
  const mouseTargetRef = useRef<{ x: number; y: number; influence: number }>({ x: 0, y: 0, influence: 0 });

  // Sprint 133: Idle personality — spontaneous micro-expressions
  const idleTimerRef = useRef(randomIdleInterval());
  const idlePoseRef = useRef<IdlePoseState>({ pose: "none", elapsed: 0, blendIn: 0, hold: 0, blendOut: 0 });
  // Sprint 133: Track previous iris filter to avoid redundant style writes
  const prevIrisFilterRef = useRef("");

  // Sprint 142: Micro-reactions — brief transient flashes on state entry
  const microReactionRef = useRef<MicroReaction | null>(null);
  // Sprint 143b: Expression echo — aftershock replaying reduced reaction
  const echoRef = useRef<ExpressionEcho | null>(null);

  // Sprint 142: Transition elapsed time tracking (ms) for staggered lerp
  const transitionElapsedMsRef = useRef(0);

  // Sprint 135: Soul emotion — LLM-driven expression override (highest priority layer)
  const soulTargetRef = useRef<Partial<FaceExpression>>({});
  const soulIntensityRef = useRef(0);
  const soulTransitionRef = useRef(0); // 0→1 blend-in progress
  const soulDecayTimerRef = useRef(0); // seconds since last emotion update

  // Per-instance seed (assigned once on mount)
  const seedRef = useRef<number>(0);

  // Animation state
  const timeRef = useRef(0);
  const rafRef = useRef<number>(0);
  const lastFrameRef = useRef(0);
  const visibleRef = useRef(true);
  const particlesRef = useRef<Particle[]>([]);
  // Sprint 134: Burst particles (one-shot on state entry)
  const burstRef = useRef<BurstParticle[]>([]);
  const burstEmittedRef = useRef(true); // true = no burst pending

  // State transition tracking
  const prevStateRef = useRef(state);
  const transitionRef = useRef(1); // 1 = fully transitioned
  const fromVisualsRef = useRef(STATE_CONFIG[state] || STATE_CONFIG.idle);
  const toVisualsRef = useRef(STATE_CONFIG[state] || STATE_CONFIG.idle);

  // Derived values for React rendering (glow, color, scale)
  const [renderState, setRenderState] = useState(() => {
    const v = STATE_CONFIG[state] || STATE_CONFIG.idle;
    return {
      glowOpacity: v.glowIntensity,
      glowColor: v.glowColor,
      blobColor: v.blobColor,
      scale: v.scale,
      indicatorColor: v.indicatorColor,
      indicatorVisible: v.indicatorVisible,
    };
  });

  const tier = getSizeTier(size);
  const resolution = getBlobResolution(tier);

  // Sprint 119: Detect prefers-reduced-motion (WCAG 2.2)
  const prefersReducedMotionRef = useRef(false);
  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    prefersReducedMotionRef.current = mql.matches;
    const handler = (e: MediaQueryListEvent) => {
      prefersReducedMotionRef.current = e.matches;
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  // Assign unique seed on mount
  useEffect(() => {
    seedRef.current = _seedCounter++;
  }, []);

  // Sprint 130: Mouse tracking listener
  useEffect(() => {
    if (tier !== "large") return;

    const handleMouseMove = (e: MouseEvent) => {
      const svg = svgRef.current;
      if (!svg) {
        mouseTargetRef.current = { x: 0, y: 0, influence: 0 };
        return;
      }
      const rect = svg.getBoundingClientRect();
      const avatarCx = rect.left + rect.width / 2;
      const avatarCy = rect.top + rect.height / 2;
      const dx = e.clientX - avatarCx;
      const dy = e.clientY - avatarCy;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Normalize direction to -1..1 range
      const maxOffset = 1;
      const normX = dist > 0 ? (dx / dist) * Math.min(dist / 200, maxOffset) : 0;
      const normY = dist > 0 ? (dy / dist) * Math.min(dist / 200, maxOffset) : 0;

      // Disinterest zone: fade out beyond threshold
      const influence = dist < MOUSE_DISINTEREST_DISTANCE
        ? 1.0
        : Math.max(0, 1 - (dist - MOUSE_DISINTEREST_DISTANCE) / MOUSE_DISINTEREST_DISTANCE);

      mouseTargetRef.current = { x: normX, y: normY, influence };
    };

    document.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => document.removeEventListener("mousemove", handleMouseMove);
  }, [tier]);

  // Detect state changes and start transition
  useEffect(() => {
    if (state !== prevStateRef.current) {
      // Snapshot current interpolated visuals as the "from" state
      const t = easeInOutCubic(Math.min(transitionRef.current, 1));
      fromVisualsRef.current = lerpVisuals(
        fromVisualsRef.current,
        toVisualsRef.current,
        t,
      );
      toVisualsRef.current = STATE_CONFIG[state] || STATE_CONFIG.idle;

      // Sprint 129: Also transition face expression
      fromFaceRef.current = lerpFaceExpression(
        fromFaceRef.current,
        toFaceRef.current,
        easeInOutCubic(t),
      );
      toFaceRef.current = FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle;
      blinkCtrlRef.current.setRate(toFaceRef.current.blinkRate);
      blinkCtrlRef.current.triggerBlink(); // Blink on state change for natural feel

      // Sprint 130: Slow contentment blink for complete state
      if (state === "complete") {
        blinkCtrlRef.current.setDuration(0.4);
      } else {
        blinkCtrlRef.current.setDuration(0.15);
      }

      // Sprint 130: Enable squint for thinking state
      blinkCtrlRef.current.squintEnabled = state === "thinking";

      transitionRef.current = 0;
      prevStateRef.current = state;

      // Sprint 130: Reset spring for squash-and-stretch
      springProgressRef.current = 0;

      // Sprint 133: Reset idle personality on state change
      idleTimerRef.current = randomIdleInterval();
      idlePoseRef.current = { pose: "none", elapsed: 0, blendIn: 0, hold: 0, blendOut: 0 };

      // Sprint 134: Mark burst pending for state entry
      burstEmittedRef.current = false;

      // Sprint 142: Reset staggered transition elapsed time
      transitionElapsedMsRef.current = 0;

      // Sprint 142: Trigger micro-reaction on state entry
      switch (state) {
        case "listening":
          microReactionRef.current = { type: "surprise", elapsed: 0, duration: 0.18 };
          break;
        case "complete":
          microReactionRef.current = { type: "nod", elapsed: 0, duration: 0.3 };
          break;
        case "error":
          microReactionRef.current = { type: "flinch", elapsed: 0, duration: 0.2 };
          break;
        case "speaking":
          microReactionRef.current = { type: "perk", elapsed: 0, duration: 0.15 };
          break;
        default:
          microReactionRef.current = null;
      }

      // Sprint 131 Phase 6: Trigger brow bounce on listening state
      if (state === "listening") {
        browBounceRef.current = 0.5; // Initial bounce magnitude
      }

      // Sprint 144: Update gaze controller state
      gazeControllerRef.current.setState(state);

      // Sprint 144: Trigger reaction chains on specific state entries
      if (state === "error") {
        chainPlaybackRef.current = createChainPlayback("panic_to_relief");
      }
    }
  }, [state]);

  // Sprint 132: Detect mood changes and start mood transition
  useEffect(() => {
    if (mood !== prevMoodRef.current) {
      // Sprint 144: Capture previous mood as emotion residual (momentum)
      const prevMood = prevMoodRef.current;
      if (prevMood !== "neutral") {
        emotionResidualRef.current = {
          mood: prevMood,
          startIntensity: moodTransitionRef.current, // current blend level
          elapsed: 0,
          decayDuration: MOOD_DECAY_DURATIONS[prevMood] || 1.5,
        };
      }

      fromMoodRef.current = prevMoodRef.current;
      toMoodRef.current = mood;
      moodTransitionRef.current = 0;
      prevMoodRef.current = mood;

      // Sprint 143: Trigger micro-reaction on mood entry
      switch (mood) {
        case "excited":
          microReactionRef.current = { type: "sparkle_eyes", elapsed: 0, duration: 0.35 };
          break;
        case "warm":
          microReactionRef.current = { type: "doki", elapsed: 0, duration: 0.4 };
          break;
        case "concerned":
          microReactionRef.current = { type: "panic", elapsed: 0, duration: 0.25 };
          break;
        case "gentle":
          microReactionRef.current = { type: "dreamy", elapsed: 0, duration: 0.5 };
          break;
      }

      // Sprint 144: Trigger reaction chains on mood+context
      if (mood === "warm" && soulEmotion && soulEmotion.face.blush && (soulEmotion.face.blush as number) > 0.5) {
        chainPlaybackRef.current = createChainPlayback("love_struck");
      }
    }
  }, [mood]);

  // Sprint 135: Detect soul emotion changes and reset transition + decay
  useEffect(() => {
    if (soulEmotion) {
      // Guard: reject NaN/Infinity intensity from malformed backend data
      const intensity = typeof soulEmotion.intensity === "number" && isFinite(soulEmotion.intensity)
        ? Math.max(0, Math.min(1, soulEmotion.intensity))
        : 0.8;
      soulTargetRef.current = soulEmotion.face as Partial<FaceExpression>;
      soulIntensityRef.current = intensity;
      soulTransitionRef.current = 0; // restart blend-in
      soulDecayTimerRef.current = 0; // reset decay timer

      // Sprint 143b: Trigger micro-reactions from high-intensity soul emotions
      if (intensity > 0.6) {
        const f = soulEmotion.face;
        if (f.blush && f.blush > 0.5) {
          microReactionRef.current = { type: "blush_deep", elapsed: 0, duration: 0.45 };
        } else if (f.mouthCurve && f.mouthCurve > 0.4 && f.eyeShape && f.eyeShape > 0.3) {
          microReactionRef.current = { type: "giggle", elapsed: 0, duration: 0.5 };
        } else if (f.browRaise && f.browRaise > 0.3 && f.mouthCurve && f.mouthCurve < -0.1) {
          microReactionRef.current = { type: "tear_up", elapsed: 0, duration: 0.6 };
        } else if (f.eyeOpenness && f.eyeOpenness < 0.8 && f.mouthOpenness && f.mouthOpenness > 0) {
          microReactionRef.current = { type: "sigh", elapsed: 0, duration: 0.7 };
        }
      }
    } else {
      // Cleared — start immediate decay
      soulIntensityRef.current = 0;
    }
  }, [soulEmotion]);

  // rAF animation loop
  const animate = useCallback(
    (timestamp: number) => {
      // Sprint 119: Skip ALL animation when user prefers reduced motion
      if (prefersReducedMotionRef.current) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }

      if (!visibleRef.current) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }

      // Delta time with cap (max 100ms to prevent jumps after tab switch)
      const dt = lastFrameRef.current
        ? Math.min((timestamp - lastFrameRef.current) / 1000, 0.1)
        : 0.016;
      lastFrameRef.current = timestamp;

      // Advance state transition (0.4s duration)
      if (transitionRef.current < 1) {
        transitionRef.current = Math.min(transitionRef.current + dt / 0.4, 1);
      }

      // Sprint 130: Advance spring progress (0.5s duration)
      if (springProgressRef.current < 1) {
        springProgressRef.current = Math.min(springProgressRef.current + dt / 0.5, 1);
      }

      let visuals = lerpVisuals(
        fromVisualsRef.current,
        toVisualsRef.current,
        transitionRef.current,
      );

      // Sprint 132: Advance mood transition (0.6s crossfade)
      if (moodTransitionRef.current < 1) {
        moodTransitionRef.current = Math.min(moodTransitionRef.current + dt / 0.6, 1);
      }

      // Sprint 132: Apply mood modifiers to visuals (crossfade old→new)
      const moodT = easeInOutCubic(moodTransitionRef.current);
      if (fromMoodRef.current !== "neutral" && moodT < 1) {
        visuals = applyMoodToVisuals(visuals, fromMoodRef.current, 1 - moodT, lerpHexColor);
      }
      if (toMoodRef.current !== "neutral") {
        visuals = applyMoodToVisuals(visuals, toMoodRef.current, moodT, lerpHexColor);
      }

      // Advance animation time
      timeRef.current += dt * visuals.timeSpeed;

      const cx = size / 2;
      const cy = size / 2;
      const blobRadius = (size / 2) * 0.82;

      // Sprint 130: Squash-and-stretch scale on state change
      let springScale = 1.0;
      if (springProgressRef.current < 1) {
        const sp = springEase(springProgressRef.current);
        // Scale overshoots: 0.97 → 1.03 → 1.0
        springScale = 0.97 + 0.03 * sp;
      }

      // Update SVG blob path via direct DOM (bypasses React reconciliation)
      if (tier !== "tiny" && pathRef.current && resolution > 0) {
        // Sprint 130: Brief noise amplitude spike during spring transition
        let noiseAmp = visuals.noiseAmplitude;
        if (springProgressRef.current < 1) {
          const wobble = Math.sin(springProgressRef.current * Math.PI) * 0.04;
          noiseAmp += wobble;
        }

        const d = generateBlobPath(
          cx, cy, blobRadius, resolution,
          timeRef.current, visuals.noiseFrequency,
          noiseAmp, seedRef.current,
        );
        pathRef.current.setAttribute("d", d);
        // Sprint 134: Smooth blob color transition via hex interpolation
        pathRef.current.setAttribute("fill", visuals.blobColorHex);
      }

      // Sprint 130: Canvas expansion for particles
      const padPx = Math.round(size * VIEWBOX_PAD_RATIO);

      // Update canvas particles (large tier only)
      if (tier === "large" && canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const dpr = window.devicePixelRatio || 1;
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.save();
          ctx.scale(dpr, dpr);

          // Particle center shifted by padding
          const particleCx = cx + padPx;
          const particleCy = cy + padPx;

          // Sprint 134: Environmental aura — mood-colored ambient glow behind blob
          if (visuals.glowIntensity > 0.03) {
            const auraRadius = blobRadius * 2.2;
            const auraAlpha = visuals.glowIntensity * 0.25;
            const gradient = ctx.createRadialGradient(
              particleCx, particleCy, blobRadius * 0.4,
              particleCx, particleCy, auraRadius,
            );
            gradient.addColorStop(0, `${visuals.glowColor}${Math.round(auraAlpha * 255).toString(16).padStart(2, "0")}`);
            gradient.addColorStop(1, `${visuals.glowColor}00`);
            ctx.globalCompositeOperation = "screen";
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(particleCx, particleCy, auraRadius, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalCompositeOperation = "source-over";
          }

          // Spawn particles to meet target count
          while (particlesRef.current.length < visuals.particleCount) {
            particlesRef.current.push(spawnParticle(particleCx, particleCy, blobRadius));
          }

          // Update and render
          particlesRef.current = updateParticles(
            particlesRef.current, particleCx, particleCy, dt,
            visuals.particleOrbitSpeed, visuals.particleDriftSpeed,
          );
          renderParticles(ctx, particlesRef.current, visuals.particleColor);

          // Sprint 134: Burst particles — one-shot shaped particles on state entry
          if (!burstEmittedRef.current) {
            burstEmittedRef.current = true;
            const burstState = state;
            if (burstState === "complete") {
              burstRef.current = spawnBurst(particleCx, particleCy, 15, "star", "#fbbf24");
            } else if (burstState === "error") {
              burstRef.current = spawnFallingBurst(particleCx, particleCy, 6, "teardrop", "#60a5fa");
            } else if (burstState === "listening") {
              burstRef.current = spawnBurst(particleCx, particleCy, 5, "ring", visuals.particleColor, [20, 40], [2, 3]);
            } else if (burstState === "speaking") {
              burstRef.current = spawnBurst(particleCx, particleCy, 8, "heart", "#ff6b9d", [30, 60], [2, 4]);
            }
          }
          if (burstRef.current.length > 0) {
            burstRef.current = updateBurstParticles(burstRef.current, dt);
            renderBurstParticles(ctx, burstRef.current);
          }

          ctx.restore();
        }
      }

      // Sprint 129+130: Update face features via direct DOM (large tier only)
      if (tier === "large" && faceGroupRef.current) {
        // Sprint 142: Track elapsed ms for staggered lerp
        if (transitionRef.current < 1) {
          transitionElapsedMsRef.current += dt * 1000;
        }
        // Sprint 142: Use staggered lerp instead of uniform lerp
        let face = staggeredLerpFace(
          fromFaceRef.current, toFaceRef.current,
          transitionElapsedMsRef.current, 400,
        );

        // Sprint 132: Apply mood expression modifiers (crossfade)
        if (fromMoodRef.current !== "neutral" && moodT < 1) {
          face = applyMoodToExpression(face, fromMoodRef.current, 1 - moodT);
        }
        if (toMoodRef.current !== "neutral") {
          face = applyMoodToExpression(face, toMoodRef.current, moodT);
        }

        // Sprint 133: Idle personality — spontaneous micro-expressions
        if (state === "idle") {
          const idlePose = idlePoseRef.current;
          if (idlePose.pose === "none") {
            // Countdown to next spontaneous pose
            idleTimerRef.current -= dt;
            if (idleTimerRef.current <= 0) {
              idlePoseRef.current = pickIdlePose(toMoodRef.current);
              idleTimerRef.current = randomIdleInterval();
            }
          } else {
            // Advance current pose
            idlePose.elapsed += dt;
            const intensity = idlePoseIntensity(idlePose);
            if (intensity > 0) {
              const mod = IDLE_POSE_MODS[idlePose.pose as Exclude<IdlePose, "none">];
              if (mod) {
                for (const key of Object.keys(mod) as string[]) {
                  if (key.startsWith("_")) continue; // skip special keys
                  const delta = (mod[key as keyof typeof mod] ?? 0) as number;
                  (face[key as keyof FaceExpression] as number) += delta * intensity;
                }
                // Apply pupil overrides
                if (mod._pupilX !== undefined) face.pupilOffsetX += mod._pupilX * intensity;
                if (mod._pupilY !== undefined) face.pupilOffsetY += mod._pupilY * intensity;
              }
            }
            // Check if pose is finished
            if (idlePose.elapsed >= idlePoseDuration(idlePose)) {
              idlePoseRef.current = { pose: "none", elapsed: 0, blendIn: 0, hold: 0, blendOut: 0 };
            }
          }
        }

        // ── Sprint 135: Soul Emotion Layer (highest priority) ──
        // Blend LLM-driven face overrides on top of state+mood+idle layers
        if (soulIntensityRef.current > 0) {
          // Advance blend-in transition
          if (soulTransitionRef.current < 1) {
            soulTransitionRef.current = Math.min(soulTransitionRef.current + dt / SOUL_BLEND_DURATION, 1);
          }

          // Advance decay timer (counts up from last emotion update)
          soulDecayTimerRef.current += dt;

          // Calculate decay factor (0 = full, 1 = fully decayed)
          let decayFactor = 0;
          if (soulDecayTimerRef.current > SOUL_DECAY_START) {
            const decayElapsed = soulDecayTimerRef.current - SOUL_DECAY_START;
            decayFactor = Math.min(decayElapsed / SOUL_DECAY_DURATION, 1);
          }

          const soulBlendT =
            easeInOutCubic(soulTransitionRef.current) *
            soulIntensityRef.current *
            (1 - decayFactor);

          if (soulBlendT > 0.001) {
            const target = soulTargetRef.current;
            for (const key of Object.keys(target)) {
              const val = target[key as keyof FaceExpression] as number | undefined;
              if (val !== undefined && key in face) {
                (face[key as keyof FaceExpression] as number) = lerp(
                  face[key as keyof FaceExpression] as number,
                  val,
                  soulBlendT,
                );
              }
            }
            // Clamp all values to valid ranges
            face.eyeOpenness = Math.max(0.5, Math.min(1.5, face.eyeOpenness));
            face.pupilSize = Math.max(0.5, Math.min(1.5, face.pupilSize));
            face.mouthCurve = Math.max(-1, Math.min(1, face.mouthCurve));
            face.mouthOpenness = Math.max(0, Math.min(1, face.mouthOpenness));
            face.mouthWidth = Math.max(0.5, Math.min(1.5, face.mouthWidth));
            face.browRaise = Math.max(-1, Math.min(1, face.browRaise));
            face.browTilt = Math.max(-1, Math.min(1, face.browTilt));
            face.blush = Math.max(0, Math.min(1, face.blush));
            face.eyeShape = Math.max(0, Math.min(1, face.eyeShape));
            face.mouthShape = Math.max(0, Math.min(4, Math.round(face.mouthShape)));
          }
        }

        // ── Sprint 144: Reaction chain playback ──
        // Chains feed individual reactions into the micro-reaction slot
        let reactionFromChain = false;
        if (chainPlaybackRef.current) {
          const chain = REACTION_CHAINS[chainPlaybackRef.current.chainId];
          if (chain) {
            const result = advanceChain(chainPlaybackRef.current, chain, dt);
            if (result.finished) {
              chainPlaybackRef.current = null;
            } else if (result.reaction) {
              // Override micro-reaction with chain step
              microReactionRef.current = result.reaction;
              reactionFromChain = true;
            }
          } else {
            chainPlaybackRef.current = null;
          }
        }

        // ── Sprint 142/143b: Micro-reaction overlay (data-driven registry) ──
        // Sprint 144: Track squash-stretch from reaction
        let reactionScaleX = 1, reactionScaleY = 1;
        const reaction = microReactionRef.current;
        if (reaction && reaction.elapsed < reaction.duration) {
          if (!reactionFromChain) reaction.elapsed += dt;
          const def = REACTION_REGISTRY[reaction.type];
          if (def) {
            const intensity = computeReactionIntensity(
              reaction.elapsed, reaction.duration,
              def.modifier.easing, def.modifier.pulseHz,
            );
            for (const [key, delta] of Object.entries(def.modifier.face)) {
              if (key in face) {
                (face[key as keyof FaceExpression] as number) += (delta as number) * intensity;
              }
            }
            // Sprint 144: Squash & Stretch (Disney Principle #1)
            if (def.modifier.squash) {
              reactionScaleX = 1 + (def.modifier.squash.scaleX - 1) * intensity;
              reactionScaleY = 1 + (def.modifier.squash.scaleY - 1) * intensity;
            }
          }
        }
        // Sprint 143b: Queue echo when primary reaction completes
        if (reaction && reaction.elapsed >= reaction.duration && !reactionFromChain) {
          const def = REACTION_REGISTRY[reaction.type];
          if (def?.echo && !echoRef.current) {
            echoRef.current = {
              parentType: reaction.type,
              delay: def.echo.delay,
              duration: def.echo.duration,
              scale: def.echo.scale,
              countdown: def.echo.delay,
            };
          }
          microReactionRef.current = null;
        }
        // Sprint 143b: Expression echo — aftershock at reduced scale
        if (echoRef.current) {
          const echo = echoRef.current;
          echo.countdown -= dt;
          if (echo.countdown <= 0) {
            const echoElapsed = -echo.countdown; // time since echo started
            if (echoElapsed < echo.duration) {
              const def = REACTION_REGISTRY[echo.parentType];
              if (def) {
                const echoIntensity = (1 - echoElapsed / echo.duration) * echo.scale;
                for (const [key, delta] of Object.entries(def.modifier.face)) {
                  if (key in face) {
                    (face[key as keyof FaceExpression] as number) += (delta as number) * echoIntensity;
                  }
                }
              }
            } else {
              echoRef.current = null;
            }
          }
        }

        // ── Sprint 144: Emotion Momentum (residual from previous mood) ──
        if (emotionResidualRef.current) {
          const residual = emotionResidualRef.current;
          residual.elapsed += dt;
          const residualIntensity = residual.startIntensity * Math.exp(-residual.elapsed / (residual.decayDuration * 0.4));
          if (residualIntensity > 0.01) {
            face = applyMoodToExpression(face, residual.mood, residualIntensity * 0.5);
          } else {
            emotionResidualRef.current = null;
          }
        }

        const dims = getFaceDimensions(blobRadius);

        // Blink
        const blinkScale = blinkCtrlRef.current.advance(dt);
        const eyeScaleY = face.eyeOpenness * blinkScale;

        // Sprint 144: Gaze controller (replaces noise drift + saccade + mouse blend)
        const noise3D = getNoiseGenerator();
        const noiseTime = timeRef.current;
        const seed = seedRef.current;
        const mouse = mouseTargetRef.current;
        const gazeResult = gazeControllerRef.current.advance(dt, mouse);
        // Micro-saccades: tiny involuntary noise on top of gaze
        const saccadeX = noise3D(noiseTime * 8, seed + 900, 0) * dims.pupilMaxOffset * 0.03;
        const saccadeY = noise3D(noiseTime * 8, 0, seed + 900) * dims.pupilMaxOffset * 0.03;

        let pupilDx = gazeResult.x * dims.pupilMaxOffset + saccadeX;
        let pupilDy = gazeResult.y * dims.pupilMaxOffset + saccadeY;

        // Sprint 143b: Pupil tremor — involuntary micro-shake during distress
        if (toMoodRef.current === "concerned" || (soulIntensityRef.current > 0.5 && soulTargetRef.current.browTilt !== undefined && soulTargetRef.current.browTilt < -0.2)) {
          const tremorIntensity = toMoodRef.current === "concerned" ? 0.3 : 0.2;
          const tremorX = noise3D(noiseTime * 15, seed + 1100, 0) * dims.pupilMaxOffset * 0.04 * tremorIntensity;
          const tremorY = noise3D(noiseTime * 15, 0, seed + 1100) * dims.pupilMaxOffset * 0.04 * tremorIntensity;
          pupilDx += tremorX;
          pupilDy += tremorY;
        }

        // Sprint 134/140/143b: Breathing — mood-responsive rhythm + depth
        // Sprint 143b: Mood affects breathing rate and depth
        let breathMultiplier = 1.0;
        let moodBreathBoost = 1.0;
        switch (toMoodRef.current) {
          case "excited": breathMultiplier = 1.4; moodBreathBoost = 1.3; break;
          case "concerned": breathMultiplier = 1.25; moodBreathBoost = 1.5; break;
          case "gentle": breathMultiplier = 0.75; moodBreathBoost = 1.0; break;
          case "warm": breathMultiplier = 0.9; moodBreathBoost = 1.0; break;
        }
        const breathFreq = (1.25 + noise3D(noiseTime * 0.05, seed + 700, 0) * 0.3) * breathMultiplier;
        const breathDepth = (0.020 + noise3D(noiseTime * 0.03, seed + 800, 0) * 0.005) * moodBreathBoost;
        const breathRaw = Math.sin(noiseTime * breathFreq);
        const breathY = Math.sign(breathRaw) * Math.pow(Math.abs(breathRaw), 1.3) * blobRadius * breathDepth;
        const headTilt = noise3D(noiseTime * 0.15, seed + 500, 0) * 1.5; // degrees

        // Face micro-motion (swim with blob) + breathing
        const microX = noise3D(noiseTime * 0.5, seed + 200, 0) * blobRadius * 0.02;
        const microY = noise3D(noiseTime * 0.5, 0, seed + 200) * blobRadius * 0.02 + breathY;

        // Sprint 131 Phase 6: Cheek puff — subtle horizontal face scale during thinking
        let cheekPuff = 1.0;
        if (state === "thinking") {
          const puffPhase = noiseTime % 2.5;
          if (puffPhase < 0.3) {
            cheekPuff = 1 + Math.sin((puffPhase / 0.3) * Math.PI) * 0.015;
          }
        }

        // Sprint 130+144: Apply spring scale + cheek puff + reaction squash to face group
        const combinedScaleX = springScale * cheekPuff * reactionScaleX;
        const combinedScaleY = springScale * reactionScaleY;
        const needsScale = combinedScaleX !== 1.0 || combinedScaleY !== 1.0;
        const faceScaleStr = needsScale ? ` scale(${combinedScaleX.toFixed(4)}, ${combinedScaleY.toFixed(4)})` : "";
        const facePosX = cx + microX;
        const facePosY = cy + microY;
        faceGroupRef.current.setAttribute("transform",
          `translate(${facePosX.toFixed(1)}, ${facePosY.toFixed(1)}) rotate(${headTilt.toFixed(2)})${faceScaleStr}`);

        // Happy eye crossfade — steeper curve to avoid ghost overlap
        // At eyeShape=0.85 (complete): normalEye=0, happyEye=1 (no overlap)
        // At eyeShape=0.05 (idle): normalEye=0.9, happyEye~0 (clean)
        const happyOpacity = Math.min(1, face.eyeShape * 1.5);
        const normalEyeOpacity = Math.max(0, 1 - face.eyeShape * 2);

        // Sprint 131+144: Eye group — blink + stress-driven asymmetry
        // Sprint 144 Phase 3: Asymmetry amplifies under stress
        let stressLevel = 0;
        if (toMoodRef.current === "concerned") stressLevel += 0.5;
        if (state === "error") stressLevel += 0.4;
        if (soulIntensityRef.current > 0.7 && soulTargetRef.current.browTilt !== undefined && soulTargetRef.current.browTilt < -0.2) stressLevel += 0.3;
        const activeReaction = microReactionRef.current;
        if (activeReaction && ["panic", "flinch", "startle"].includes(activeReaction.type)) stressLevel += 0.3;
        stressLevel = Math.min(1, stressLevel);
        const eyeAsym = lerp(0.03, 0.15, stressLevel);
        if (leftEyeRef.current) {
          leftEyeRef.current.setAttribute("transform",
            `scale(1, ${(eyeScaleY * (1 + eyeAsym)).toFixed(3)})`);
          leftEyeRef.current.setAttribute("opacity", normalEyeOpacity.toFixed(3));
        }
        if (rightEyeRef.current) {
          rightEyeRef.current.setAttribute("transform",
            `scale(1, ${(eyeScaleY * (1 - eyeAsym)).toFixed(3)})`);
          rightEyeRef.current.setAttribute("opacity", normalEyeOpacity.toFixed(3));
        }

        // Sprint 131: Iris group — gaze tracking (translate), clipped to sclera
        if (leftIrisRef.current) {
          leftIrisRef.current.setAttribute("transform",
            `translate(${pupilDx.toFixed(2)}, ${pupilDy.toFixed(2)})`);
        }
        if (rightIrisRef.current) {
          rightIrisRef.current.setAttribute("transform",
            `translate(${pupilDx.toFixed(2)}, ${pupilDy.toFixed(2)})`);
        }

        // Sprint 134: Pupil dilation — live pupilSize → actual SVG radius
        const activePupilR = dims.pupilR * face.pupilSize;
        if (leftIrisRef.current) {
          const pupil = leftIrisRef.current.querySelector(".wiii-face-pupil");
          if (pupil) pupil.setAttribute("r", activePupilR.toFixed(2));
        }
        if (rightIrisRef.current) {
          const pupil = rightIrisRef.current.querySelector(".wiii-face-pupil");
          if (pupil) pupil.setAttribute("r", activePupilR.toFixed(2));
        }

        // Sprint 143: Anime eye overlays — star/heart pupils triggered by micro-reactions
        {
          const ae = animeEyeRef.current;
          // Determine target overlay from active micro-reaction or sustained state
          let targetType: "none" | "star" | "heart" | "cross" = "none";
          if (reaction && reaction.elapsed < reaction.duration) {
            if (reaction.type === "sparkle_eyes") targetType = "star";
            else if (reaction.type === "doki") targetType = "heart";
            else if (reaction.type === "flinch" || reaction.type === "startle") targetType = "cross";
          }
          // Sprint 144: Error state sustains × eyes even after chain ends
          if (targetType === "none" && prevStateRef.current === "error") targetType = "cross";
          // Transition overlay opacity
          if (targetType !== "none") {
            ae.type = targetType;
            ae.opacity = Math.min(1, ae.opacity + dt / 0.1); // fade in 0.1s
          } else if (ae.opacity > 0) {
            ae.opacity = Math.max(0, ae.opacity - dt / 0.15); // fade out 0.15s
            if (ae.opacity <= 0) ae.type = "none";
          }
          // Apply to SVG elements
          const starOp = ae.type === "star" ? ae.opacity : 0;
          const heartOp = ae.type === "heart" ? ae.opacity : 0;
          const crossOp = ae.type === "cross" ? ae.opacity : 0;
          // When overlay active, fade down normal pupil
          const pupilFade = 1 - Math.max(starOp, heartOp, crossOp) * 0.7;
          if (leftStarRef.current) leftStarRef.current.setAttribute("opacity", starOp.toFixed(3));
          if (rightStarRef.current) rightStarRef.current.setAttribute("opacity", starOp.toFixed(3));
          if (leftHeartRef.current) leftHeartRef.current.setAttribute("opacity", heartOp.toFixed(3));
          if (rightHeartRef.current) rightHeartRef.current.setAttribute("opacity", heartOp.toFixed(3));
          // Sprint 144: Knocked-out × eyes
          if (leftKORef.current) {
            leftKORef.current.setAttribute("opacity", crossOp.toFixed(3));
            if (crossOp > 0) leftKORef.current.setAttribute("d", generateKnockedOutEyePath(-dims.eyeSpacing, dims.eyeY, dims.pupilR));
          }
          if (rightKORef.current) {
            rightKORef.current.setAttribute("opacity", crossOp.toFixed(3));
            if (crossOp > 0) rightKORef.current.setAttribute("d", generateKnockedOutEyePath(dims.eyeSpacing, dims.eyeY, dims.pupilR));
          }
          // Dim normal pupil when overlay active
          if (leftIrisRef.current) {
            const pupil = leftIrisRef.current.querySelector(".wiii-face-pupil");
            if (pupil) pupil.setAttribute("opacity", pupilFade.toFixed(3));
          }
          if (rightIrisRef.current) {
            const pupil = rightIrisRef.current.querySelector(".wiii-face-pupil");
            if (pupil) pupil.setAttribute("opacity", pupilFade.toFixed(3));
          }
        }

        // Sprint 134: Moving eye shine — highlights drift opposite to gaze direction
        // Creates impression of 3D eye surface (light source stays fixed as eye moves)
        {
          const shineCounterX = -pupilDx * 0.35; // 35% opposite drift
          const shineCounterY = -pupilDy * 0.35;
          const shineNoiseX = noise3D(noiseTime * 0.3, seed + 900, 0) * dims.shineR1 * 0.8;
          const shineNoiseY = noise3D(noiseTime * 0.3, 0, seed + 900) * dims.shineR1 * 0.6;
          const shineDx = shineCounterX + shineNoiseX;
          const shineDy = shineCounterY + shineNoiseY;
          // Apply to shine circles (both eyes)
          [leftIrisRef, rightIrisRef].forEach((ref) => {
            if (!ref.current) return;
            const shines = ref.current.querySelectorAll(".wiii-face-shine");
            shines.forEach((s) => {
              // Use transform instead of cx/cy to avoid React value conflicts
              (s as SVGElement).style.transform = `translate(${shineDx.toFixed(2)}px, ${shineDy.toFixed(2)}px)`;
            });
          });
        }

        // Sprint 133: Iris mood tinting — CSS filter for emotional eye coloring
        {
          const fromFilter = MOOD_IRIS_FILTER[fromMoodRef.current] || "";
          const toFilter = MOOD_IRIS_FILTER[toMoodRef.current] || "";
          // Use target filter once transition is past midpoint, else keep from
          const irisFilter = moodT >= 0.5 ? toFilter : fromFilter;
          if (irisFilter !== prevIrisFilterRef.current) {
            prevIrisFilterRef.current = irisFilter;
            if (leftIrisRef.current) leftIrisRef.current.style.filter = irisFilter;
            if (rightIrisRef.current) rightIrisRef.current.style.filter = irisFilter;
          }
        }

        // Happy eye arcs — fade in as eyeShape increases
        if (leftHappyRef.current) {
          leftHappyRef.current.setAttribute("opacity", happyOpacity.toFixed(3));
        }
        if (rightHappyRef.current) {
          rightHappyRef.current.setAttribute("opacity", happyOpacity.toFixed(3));
        }

        // Blush opacity (ellipses + hash lines share same opacity)
        // Sprint 143: Blush pulse — anime-style breathing blush when blush > 0.3
        const baseBlushOpacity = face.blush * 0.5; // Max 0.5 opacity for subtlety
        let leftBlushOp = baseBlushOpacity;
        let rightBlushOp = baseBlushOpacity;
        if (face.blush > 0.3) {
          const pulseIntensity = (face.blush - 0.3) / 0.7; // 0→1 as blush 0.3→1.0
          const pulseL = Math.sin(noiseTime * 2.5) * 0.08 * pulseIntensity;
          const pulseR = Math.sin(noiseTime * 2.5 + 0.8) * 0.08 * pulseIntensity; // phase offset
          leftBlushOp = baseBlushOpacity + pulseL;
          rightBlushOp = baseBlushOpacity + pulseR;
        }
        if (leftBlushRef.current) {
          leftBlushRef.current.setAttribute("opacity", leftBlushOp.toFixed(3));
        }
        if (rightBlushRef.current) {
          rightBlushRef.current.setAttribute("opacity", rightBlushOp.toFixed(3));
        }
        // Sprint 131+143: Animate blush hash lines (pulse in sync with ellipses)
        if (faceGroupRef.current) {
          const hashLines = faceGroupRef.current.querySelectorAll(".wiii-face-blush-hash");
          let hashIdx = 0;
          hashLines.forEach((el) => {
            // First 3 hash lines = left cheek, next 3 = right cheek
            const op = hashIdx < 3 ? leftBlushOp : rightBlushOp;
            el.setAttribute("opacity", op.toFixed(3));
            hashIdx++;
          });
        }

        // Sprint 131 Phase 4 + Sprint 143: Manga indicator animation (mood-aware)
        const activeIndicator: MangaIndicatorType = getIndicatorForState(state, toMoodRef.current);
        const indicatorOpacity = transitionRef.current < 1 ? easeInOutCubic(transitionRef.current) : 1;

        // Show active indicator, hide others
        if (sparkleRef.current) {
          if (activeIndicator === "sparkle") {
            sparkleRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            // Rotate sparkles slowly + scale pulse
            const sparkleScale = 1 + Math.sin(noiseTime * 3) * 0.15;
            const sparkleRot = noiseTime * 40;
            sparkleRef.current.setAttribute("transform", `rotate(${sparkleRot.toFixed(1)}, 0, 0) scale(${sparkleScale.toFixed(3)})`);
          } else {
            sparkleRef.current.setAttribute("opacity", "0");
          }
        }

        if (thoughtRef.current) {
          if (activeIndicator === "thought") {
            thoughtRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            // Gentle bob
            const bobY = Math.sin(noiseTime * 1.5) * blobRadius * 0.02;
            thoughtRef.current.setAttribute("transform", `translate(0, ${bobY.toFixed(2)})`);
            // Animate thought dots (sequential appearance)
            const dots = thoughtRef.current.querySelectorAll(".wiii-thought-dot");
            const cycle = noiseTime % 1.5;
            dots.forEach((dot, i) => {
              const dotOpacity = cycle >= i * 0.5 && cycle < (i + 1) * 0.5 ? 1 : 0.3;
              dot.setAttribute("opacity", dotOpacity.toFixed(1));
            });
          } else {
            thoughtRef.current.setAttribute("opacity", "0");
          }
        }

        if (sweatRef.current) {
          if (activeIndicator === "sweat") {
            // Sweat drop slides down and resets
            const sweatCycle = noiseTime % 2.0;
            const sweatSlide = sweatCycle * blobRadius * 0.08;
            const sweatFade = Math.max(0, 1 - sweatCycle / 2.0);
            sweatRef.current.setAttribute("opacity", (sweatFade * indicatorOpacity).toFixed(3));
            const wobble = Math.sin(noiseTime * 5) * blobRadius * 0.01;
            sweatRef.current.setAttribute("transform", `translate(${wobble.toFixed(2)}, ${sweatSlide.toFixed(2)})`);
          } else {
            sweatRef.current.setAttribute("opacity", "0");
          }
        }

        if (musicRef.current) {
          if (activeIndicator === "music") {
            const musicOp = Math.min(0.6, indicatorOpacity * 0.6);
            musicRef.current.setAttribute("opacity", musicOp.toFixed(3));
            // Gentle bob + slight rotation
            const musicBob = Math.sin(noiseTime * 2) * blobRadius * 0.03;
            const musicRot = Math.sin(noiseTime * 1.5) * 6;
            musicRef.current.setAttribute("transform", `translate(0, ${musicBob.toFixed(2)}) rotate(${musicRot.toFixed(1)})`);
          } else {
            musicRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143: Heart indicator ♥ — pulsing heartbeat + staggered bob
        if (heartRef.current) {
          if (activeIndicator === "heart") {
            heartRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            // Heartbeat rhythm: quick expand → slow shrink
            const heartBeat = Math.pow(Math.abs(Math.sin(noiseTime * 3)), 0.6);
            const heartScale = 0.9 + heartBeat * 0.2;
            // Staggered bob between the 2 hearts
            const bob1 = Math.sin(noiseTime * 1.8) * blobRadius * 0.025;
            const bob2 = Math.sin(noiseTime * 1.8 + 1.2) * blobRadius * 0.025;
            const hearts = heartRef.current.querySelectorAll("path");
            if (hearts[0]) hearts[0].setAttribute("transform", `translate(0, ${bob1.toFixed(2)}) scale(${heartScale.toFixed(3)})`);
            if (hearts[1]) hearts[1].setAttribute("transform", `translate(0, ${bob2.toFixed(2)}) scale(${(heartScale * 0.85).toFixed(3)})`);
          } else {
            heartRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143: Exclaim indicator ❗ — flash in then gentle bob
        if (exclaimRef.current) {
          if (activeIndicator === "exclaim") {
            // Flash in: scale 0→1.2→1 over first 0.2s of transition
            const flashT = Math.min(transitionRef.current / 0.5, 1); // 0→1 over first 50% of transition
            const flashScale = flashT < 0.5 ? 1.2 * (flashT / 0.5) : 1.2 - 0.2 * ((flashT - 0.5) / 0.5);
            const exclaimBob = Math.sin(noiseTime * 2.5) * blobRadius * 0.015;
            exclaimRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            exclaimRef.current.setAttribute("transform", `translate(0, ${exclaimBob.toFixed(2)}) scale(${flashScale.toFixed(3)})`);
          } else {
            exclaimRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143: Question indicator ❓ — wobble left-right + bob
        if (questionRef.current) {
          if (activeIndicator === "question") {
            const wobble = Math.sin(noiseTime * 3) * 8; // degrees
            const qBob = Math.sin(noiseTime * 1.5) * blobRadius * 0.02;
            questionRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            questionRef.current.setAttribute("transform", `translate(0, ${qBob.toFixed(2)}) rotate(${wobble.toFixed(1)})`);
          } else {
            questionRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Anger vein 💢 — throb scale + rotation wobble
        if (angerVeinRef.current) {
          if (activeIndicator === "anger_vein") {
            const throb = 1 + Math.sin(noiseTime * 4 * Math.PI * 2) * 0.15;
            const rotWobble = Math.sin(noiseTime * 6) * 5;
            angerVeinRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            angerVeinRef.current.setAttribute("transform", `scale(${throb.toFixed(3)}) rotate(${rotWobble.toFixed(1)})`);
          } else {
            angerVeinRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Gloom lines ||| — slow downward drift + fade oscillation
        if (gloomRef.current) {
          if (activeIndicator === "gloom_lines") {
            const driftDown = (noiseTime % 3.0) * blobRadius * 0.015;
            const fadePulse = 0.5 + Math.sin(noiseTime * 1.2) * 0.2;
            gloomRef.current.setAttribute("opacity", (indicatorOpacity * fadePulse).toFixed(3));
            gloomRef.current.setAttribute("transform", `translate(0, ${driftDown.toFixed(2)})`);
          } else {
            gloomRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Spiral @_@ — continuous rotation + gentle scale pulse
        if (spiralRef.current) {
          if (activeIndicator === "spiral_eyes") {
            const spiralRot = noiseTime * 120; // 120°/s
            const spiralScale = 1 + Math.sin(noiseTime * 2) * 0.1;
            spiralRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            spiralRef.current.setAttribute("transform", `rotate(${(spiralRot % 360).toFixed(1)}) scale(${spiralScale.toFixed(3)})`);
          } else {
            spiralRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Flower bloom ✿ — petals unfurl + gentle rotation + particle drift
        if (flowerRef.current) {
          if (activeIndicator === "flower_bloom") {
            const bloomT = Math.min(transitionRef.current / 0.4, 1); // scale 0→1 over 0.4s
            const bloomScale = bloomT;
            const bloomRot = noiseTime * 15;
            const bloomDrift = Math.sin(noiseTime * 0.8) * blobRadius * 0.015;
            flowerRef.current.setAttribute("opacity", (indicatorOpacity * bloomScale).toFixed(3));
            flowerRef.current.setAttribute("transform", `translate(0, ${bloomDrift.toFixed(2)}) rotate(${bloomRot.toFixed(1)}) scale(${bloomScale.toFixed(3)})`);
          } else {
            flowerRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Zzz 💤 — sequential letter appearance + upward float + fade
        if (zzzRef.current) {
          if (activeIndicator === "zzz") {
            const zzzCycle = noiseTime % 2.0; // 2s per cycle
            const zzzPhase = Math.min(zzzCycle / 1.5, 1); // letters appear over 1.5s
            const zzzFloat = -zzzCycle * blobRadius * 0.03; // drift upward
            const zzzFade = Math.max(0, 1 - zzzCycle / 2.0);
            zzzRef.current.setAttribute("opacity", (indicatorOpacity * zzzFade * zzzPhase).toFixed(3));
            zzzRef.current.setAttribute("transform", `translate(0, ${zzzFloat.toFixed(2)})`);
          } else {
            zzzRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 143b: Fire spirit 🔥 — flickering scale + upward drift
        if (fireRef.current) {
          if (activeIndicator === "fire_spirit") {
            const flicker = 0.85 + noise3D(noiseTime * 12, seed + 1200, 0) * 0.3;
            const fireDrift = Math.sin(noiseTime * 2) * blobRadius * 0.015;
            const fireScaleY = 1 + Math.sin(noiseTime * 5) * 0.08;
            fireRef.current.setAttribute("opacity", indicatorOpacity.toFixed(3));
            fireRef.current.setAttribute("transform", `translate(0, ${fireDrift.toFixed(2)}) scale(${flicker.toFixed(3)}, ${fireScaleY.toFixed(3)})`);
          } else {
            fireRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 131 Phase 6: Micro-expressions
        // Brow bounce — rapid raise then settle on listening state
        if (browBounceRef.current > 0.01) {
          browBounceRef.current *= Math.pow(0.05, dt); // Exponential decay (~0.3s)
        } else {
          browBounceRef.current = 0;
        }
        // Shine pulse — periodic highlight brightness boost
        shinePulseRef.current += dt;
        const shinePulsePhase = shinePulseRef.current % 3.5; // Every 3.5s
        const shineBoost = shinePulsePhase < 0.3 ? Math.sin((shinePulsePhase / 0.3) * Math.PI) * 0.25 : 0;
        // Apply shine boost to highlight elements
        if (leftIrisRef.current && shineBoost > 0) {
          const shines = leftIrisRef.current.querySelectorAll(".wiii-face-shine");
          shines.forEach((s) => {
            const baseOp = parseFloat(s.getAttribute("opacity") || "0.9");
            s.setAttribute("opacity", Math.min(1, baseOp + shineBoost).toFixed(3));
          });
        }
        if (rightIrisRef.current && shineBoost > 0) {
          const shines = rightIrisRef.current.querySelectorAll(".wiii-face-shine");
          shines.forEach((s) => {
            const baseOp = parseFloat(s.getAttribute("opacity") || "0.9");
            s.setAttribute("opacity", Math.min(1, baseOp + shineBoost).toFixed(3));
          });
        }
        // Eyebrows — GPU-accelerated transforms + Sprint 144: stress-driven asymmetry
        const browAsym = lerp(0.08, 0.18, stressLevel);
        const browRaiseBase = (face.browRaise + browBounceRef.current) * -dims.eyeRy * 0.5;
        if (leftBrowRef.current) {
          const tiltAngle = face.browTilt * 12;
          const leftBrowY = browRaiseBase * (1 + browAsym);
          leftBrowRef.current.setAttribute("transform",
            `translate(0, ${leftBrowY.toFixed(2)}) rotate(${(-tiltAngle).toFixed(1)})`);
        }
        if (rightBrowRef.current) {
          const tiltAngle = face.browTilt * 12;
          const rightBrowY = browRaiseBase * (1 - browAsym);
          rightBrowRef.current.setAttribute("transform",
            `translate(0, ${rightBrowY.toFixed(2)}) rotate(${tiltAngle.toFixed(1)})`);
        }

        // Mouth — shape dispatch + speaking rhythm
        let mouthOpenness = face.mouthOpenness;
        let mouthCurve = face.mouthCurve;
        if (state === "speaking") {
          // Sprint 142: Vietnamese syllable rhythm — open-hold-close cycles
          const syllableDuration = 0.15 + noise3D(noiseTime * 0.5, seed + 600, 0) * 0.05;
          const syllablePhase = (noiseTime % syllableDuration) / syllableDuration;
          const envelope = Math.sin(syllablePhase * Math.PI); // smooth open-close
          const emphasis = 0.5 + noise3D(noiseTime * 1.5, seed + 650, 0) * 0.3; // stress variation
          mouthOpenness = envelope * emphasis * 0.45;
          const widthNoise = noise3D(noiseTime * 2, seed + 400, 0);
          mouthCurve = 0.15 + widthNoise * 0.1;
        }
        if (mouthRef.current) {
          // Sprint 131 Phase 2: Select mouth shape
          const shape = Math.round(face.mouthShape);
          let mouthPath: string;
          let mouthFill: string;
          switch (shape) {
            case 1: // cat ω
              mouthPath = generateCatMouthPath(0, dims.mouthY, dims.mouthBaseWidth, face.mouthWidth);
              mouthFill = "none";
              break;
            case 2: // dot ·
              mouthPath = generateDotMouthPath(0, dims.mouthY, dims.mouthBaseWidth);
              mouthFill = "white";
              break;
            case 3: // wavy ～
              mouthPath = generateWavyMouthPath(0, dims.mouthY, dims.mouthBaseWidth, face.mouthWidth);
              mouthFill = "none";
              break;
            case 4: // pout ε
              mouthPath = generatePoutMouthPath(0, dims.mouthY, dims.mouthBaseWidth, face.mouthWidth);
              mouthFill = "rgba(255,180,200,0.5)";
              break;
            default: // normal bezier
              mouthPath = generateMouthPath(0, dims.mouthY, {
                curve: mouthCurve,
                openness: mouthOpenness,
                width: face.mouthWidth,
              }, dims.mouthBaseWidth);
              mouthFill = mouthOpenness >= 0.05 ? "rgba(0,0,0,0.3)" : "none";
              break;
          }
          mouthRef.current.setAttribute("d", mouthPath);
          mouthRef.current.setAttribute("fill", mouthFill);
          // Dot mouth: no stroke, just fill. Others: white stroke
          mouthRef.current.setAttribute("stroke", shape === 2 ? "none" : "white");

          // Sprint 144 Phase 4: Mouth interior — teeth + tongue + glint
          // Only for shapes that open (0=default, 1=cat ω). Shapes 2-4 (dot/wavy/pout) are closed forms.
          if (shape <= 1 && mouthOpenness > 0.15) {
            const interiorOpacity = Math.min(1, (mouthOpenness - 0.15) / 0.85);
            if (teethRef.current) {
              teethRef.current.setAttribute("d", generateTeethPath(0, dims.mouthY, dims.mouthBaseWidth, face.mouthWidth, mouthOpenness));
              teethRef.current.setAttribute("opacity", interiorOpacity.toFixed(3));
            }
            if (tongueRef.current) {
              tongueRef.current.setAttribute("d", generateTonguePath(0, dims.mouthY, dims.mouthBaseWidth, mouthOpenness));
              tongueRef.current.setAttribute("opacity", (interiorOpacity * 0.8).toFixed(3));
            }
            if (mouthGlintRef.current) {
              const glintShimmer = Math.sin(noiseTime * 4) * 0.3 + 0.7;
              mouthGlintRef.current.setAttribute("opacity", (interiorOpacity * 0.3 * glintShimmer).toFixed(3));
              mouthGlintRef.current.setAttribute("cx", (dims.mouthBaseWidth * 0.1).toFixed(2));
              mouthGlintRef.current.setAttribute("cy", (dims.mouthY + mouthOpenness * dims.mouthBaseWidth * 0.1).toFixed(2));
            }
          } else {
            if (teethRef.current) teethRef.current.setAttribute("opacity", "0");
            if (tongueRef.current) tongueRef.current.setAttribute("opacity", "0");
            if (mouthGlintRef.current) mouthGlintRef.current.setAttribute("opacity", "0");
          }
        }

        // Sprint 144 Phase 7: Eye moisture — accumulation + visual effects + tear drops
        {
          const moist = moistureRef.current;
          const isTearUp = reaction && reaction.type === "tear_up" && reaction.elapsed < reaction.duration;
          const isSigh = reaction && reaction.type === "sigh" && reaction.elapsed < reaction.duration;
          const soulSad = soulIntensityRef.current > 0.3 &&
            soulTargetRef.current.browRaise !== undefined && soulTargetRef.current.browRaise > 0.2 &&
            soulTargetRef.current.mouthCurve !== undefined && soulTargetRef.current.mouthCurve < -0.1;
          updateMoisture(moist, {
            tearUpActive: !!isTearUp,
            sighActive: !!isSigh,
            isConcerned: toMoodRef.current === "concerned",
            soulSadness: soulSad,
          }, dt);
          const effects = getMoistureEffects(moist.moisture);

          // Moisture shine under eyes
          if (leftMoistureRef.current) {
            leftMoistureRef.current.setAttribute("opacity", (effects.lowerShine * 0.4).toFixed(3));
          }
          if (rightMoistureRef.current) {
            rightMoistureRef.current.setAttribute("opacity", (effects.lowerShine * 0.4).toFixed(3));
          }

          // Tear drop
          if (moist.tearDrop && moist.tearDrop.side === "left" && leftTearRef.current) {
            const tearPath = generateTearDropPath(-dims.eyeSpacing - dims.eyeRx * 0.8, dims.eyeY + dims.eyeRy * 0.3, moist.tearDrop.progress, blobRadius);
            leftTearRef.current.setAttribute("d", tearPath);
            leftTearRef.current.setAttribute("opacity", (1 - moist.tearDrop.progress * 0.5).toFixed(3));
          } else if (leftTearRef.current) {
            leftTearRef.current.setAttribute("opacity", "0");
          }
          if (moist.tearDrop && moist.tearDrop.side === "right" && rightTearRef.current) {
            const tearPath = generateTearDropPath(dims.eyeSpacing + dims.eyeRx * 0.8, dims.eyeY + dims.eyeRy * 0.3, moist.tearDrop.progress, blobRadius);
            rightTearRef.current.setAttribute("d", tearPath);
            rightTearRef.current.setAttribute("opacity", (1 - moist.tearDrop.progress * 0.5).toFixed(3));
          } else if (rightTearRef.current) {
            rightTearRef.current.setAttribute("opacity", "0");
          }
        }

      }

      // Update React state (throttled — only when values change meaningfully)
      setRenderState((prev) => {
        const changed =
          Math.abs(prev.glowOpacity - visuals.glowIntensity) > 0.005 ||
          prev.glowColor !== visuals.glowColor ||
          prev.blobColor !== visuals.blobColor ||
          Math.abs(prev.scale - visuals.scale) > 0.002 ||
          prev.indicatorColor !== visuals.indicatorColor ||
          prev.indicatorVisible !== visuals.indicatorVisible;
        if (!changed) return prev;
        return {
          glowOpacity: visuals.glowIntensity,
          glowColor: visuals.glowColor,
          blobColor: visuals.blobColor,
          scale: visuals.scale,
          indicatorColor: visuals.indicatorColor,
          indicatorVisible: visuals.indicatorVisible,
        };
      });

      rafRef.current = requestAnimationFrame(animate);
    },
    [size, tier, resolution, state, mood, soulEmotion],
  );

  // Start/stop rAF loop + IntersectionObserver
  useEffect(() => {
    // Tiny tier: no animation loop needed (CSS-only)
    if (tier === "tiny") return;

    // Sprint 130: Setup canvas DPI for large tier (expanded size)
    if (tier === "large" && canvasRef.current) {
      const canvas = canvasRef.current;
      const dpr = window.devicePixelRatio || 1;
      const padPx = Math.round(size * VIEWBOX_PAD_RATIO);
      const expandedSize = size + padPx * 2;
      canvas.width = expandedSize * dpr;
      canvas.height = expandedSize * dpr;
      canvas.style.width = `${expandedSize}px`;
      canvas.style.height = `${expandedSize}px`;
    }

    // Start rAF
    rafRef.current = requestAnimationFrame(animate);

    // IntersectionObserver to pause when off-screen
    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = entry.isIntersecting;
      },
      { threshold: 0.1 },
    );

    const el = svgRef.current;
    if (el) observer.observe(el);

    return () => {
      cancelAnimationFrame(rafRef.current);
      observer.disconnect();
    };
  }, [tier, size, animate]);

  return {
    svgRef,
    canvasRef,
    pathRef,
    faceGroupRef,
    leftEyeRef,
    rightEyeRef,
    leftIrisRef,
    rightIrisRef,
    leftBrowRef,
    rightBrowRef,
    mouthRef,
    leftBlushRef,
    rightBlushRef,
    leftHappyRef,
    rightHappyRef,
    sparkleRef,
    thoughtRef,
    sweatRef,
    musicRef,
    heartRef,
    exclaimRef,
    questionRef,
    angerVeinRef,
    gloomRef,
    spiralRef,
    flowerRef,
    zzzRef,
    fireRef,
    leftStarRef,
    rightStarRef,
    leftHeartRef,
    rightHeartRef,
    leftKORef,
    rightKORef,
    teethRef,
    tongueRef,
    mouthGlintRef,
    leftTearRef,
    rightTearRef,
    leftMoistureRef,
    rightMoistureRef,
    ...renderState,
  };
}
