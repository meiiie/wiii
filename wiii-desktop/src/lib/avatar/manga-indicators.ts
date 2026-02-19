/**
 * Manga emotional indicators — Sprint 131 Phase 4.
 * SVG path generators and state mapping for emotional symbols
 * that appear around the blob avatar (sparkles, thought bubble, sweat, music).
 */
import type { AvatarState } from "./types";
import type { MoodType } from "./mood-theme";

/** Types of manga indicators — Sprint 143b: added anger_vein, gloom_lines, spiral_eyes, flower_bloom, zzz, fire_spirit */
export type MangaIndicatorType = "none" | "sparkle" | "thought" | "sweat" | "music"
  | "heart" | "exclaim" | "question"
  | "anger_vein" | "gloom_lines" | "spiral_eyes" | "flower_bloom" | "zzz" | "fire_spirit";

/** Map avatar state (+ optional mood) to the appropriate manga indicator.
 *  Sprint 143: Mood-aware — mood overrides default state mapping in specific combos. */
export function getIndicatorForState(state: AvatarState, mood?: MoodType): MangaIndicatorType {
  // Sprint 143b: New mood+state combos (checked before existing mood overrides)
  if (mood === "concerned" && state === "thinking") return "spiral_eyes";
  if (mood === "concerned" && state === "speaking") return "sweat";
  if (mood === "excited" && state === "complete") return "flower_bloom";
  if (mood === "gentle" && state === "idle") return "zzz";
  if (mood === "excited" && state === "thinking") return "fire_spirit";
  // Sprint 144: Wire anger_vein and gloom_lines
  if (mood === "concerned" && state === "error") return "anger_vein";
  if (mood === "concerned" && state === "listening") return "gloom_lines";
  // Mood-aware overrides (Sprint 143)
  if (mood === "excited" && (state === "idle" || state === "speaking")) return "heart";
  if (mood === "warm" && state === "idle") return "heart";
  if (mood === "concerned" && state === "idle") return "sweat";
  // Existing state-based defaults
  switch (state) {
    case "complete":  return "sparkle";
    case "thinking":  return "thought";
    case "error":     return "sweat";
    case "idle":      return "music";
    case "listening": return "exclaim";
    default:          return "none";
  }
}

/** Position config for each indicator relative to blob center (as ratio of blobRadius) */
export interface IndicatorPosition {
  x: number;
  y: number;
}

/** Sparkle star positions (3 stars scattered around blob) */
export const SPARKLE_POSITIONS: IndicatorPosition[] = [
  { x: 0.85, y: -0.70 },
  { x: -0.55, y: -0.90 },
  { x: 0.95, y: 0.20 },
];

/** Thought bubble position */
export const THOUGHT_POSITION: IndicatorPosition = { x: 0.80, y: -0.90 };

/** Sweat drop position (right temple) */
export const SWEAT_POSITION: IndicatorPosition = { x: 0.80, y: -0.20 };

/** Music note position */
export const MUSIC_POSITION: IndicatorPosition = { x: -0.70, y: -0.85 };

/** Sprint 143: Heart positions (2 floating hearts) */
export const HEART_POSITIONS: IndicatorPosition[] = [
  { x: -0.75, y: -0.85 },
  { x: 0.60, y: -0.95 },
];

/** Sprint 143: Exclamation mark position (right side) */
export const EXCLAIM_POSITION: IndicatorPosition = { x: 0.90, y: -0.80 };

/** Sprint 143: Question mark position (right side) */
export const QUESTION_POSITION: IndicatorPosition = { x: 0.85, y: -0.85 };

/** Sprint 143b: Anger vein 💢 position (upper-right forehead) */
export const ANGER_VEIN_POSITION: IndicatorPosition = { x: 0.75, y: -0.75 };

/** Sprint 143b: Gloom lines ||| position (above head, centered) */
export const GLOOM_POSITION: IndicatorPosition = { x: 0, y: -1.1 };

/** Sprint 143b: Spiral @_@ position (right side) */
export const SPIRAL_POSITION: IndicatorPosition = { x: 0.85, y: -0.70 };

/** Sprint 143b: Flower bloom ✿ positions (scattered, like sparkle) */
export const FLOWER_POSITIONS: IndicatorPosition[] = [
  { x: -0.80, y: -0.85 },
  { x: 0.65, y: -0.95 },
  { x: 0.90, y: -0.30 },
];

/** Sprint 143b: Zzz 💤 position (upper-right, floating away) */
export const ZZZ_POSITION: IndicatorPosition = { x: 0.80, y: -0.90 };

/** Sprint 143b: Fire spirit 🔥 position (left side) */
export const FIRE_POSITION: IndicatorPosition = { x: -0.85, y: -0.75 };

/**
 * Generate a 4-pointed star path for sparkle indicator.
 * @param cx - center X
 * @param cy - center Y
 * @param outerR - outer point radius
 * @param innerR - inner notch radius (typically outerR * 0.35)
 */
export function generateSparklePath(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number = outerR * 0.35,
): string {
  return [
    `M ${cx} ${cy - outerR}`,
    `L ${cx + innerR} ${cy - innerR}`,
    `L ${cx + outerR} ${cy}`,
    `L ${cx + innerR} ${cy + innerR}`,
    `L ${cx} ${cy + outerR}`,
    `L ${cx - innerR} ${cy + innerR}`,
    `L ${cx - outerR} ${cy}`,
    `L ${cx - innerR} ${cy - innerR}`,
    "Z",
  ].join(" ");
}

/**
 * Generate a teardrop/sweat drop path.
 * Pointed at top, rounded at bottom.
 */
export function generateSweatDropPath(
  cx: number,
  cy: number,
  width: number,
  height: number,
): string {
  const hw = width / 2;
  const top = cy - height / 2;
  const bottom = cy + height / 2;
  return [
    `M ${cx} ${top}`,
    `Q ${cx + hw * 1.4} ${cy * 1 + 0}, ${cx} ${bottom}`,
    `Q ${cx - hw * 1.4} ${cy * 1 + 0}, ${cx} ${top}`,
    "Z",
  ].join(" ");
}

/**
 * Generate a music note (♪) path — note head + stem + flag.
 */
export function generateMusicNotePath(
  cx: number,
  cy: number,
  size: number,
): string {
  const r = size * 0.3;
  const stemH = size * 0.8;
  const flagW = size * 0.4;
  // Note head (filled ellipse via arc)
  const head = `M ${cx + r} ${cy} A ${r} ${r * 0.7} 0 1 1 ${cx - r} ${cy} A ${r} ${r * 0.7} 0 1 1 ${cx + r} ${cy}`;
  // Stem (vertical line from right of head upward)
  const stem = `M ${cx + r} ${cy} L ${cx + r} ${cy - stemH}`;
  // Flag (curved line from stem top)
  const flag = `M ${cx + r} ${cy - stemH} Q ${cx + r + flagW} ${cy - stemH + size * 0.3}, ${cx + r} ${cy - stemH + size * 0.5}`;
  return `${head} ${stem} ${flag}`;
}

/**
 * Sprint 143: Generate a heart ♥ path — classic manga heart shape.
 * Two cubic bezier curves forming a symmetric heart.
 */
export function generateHeartPath(
  cx: number,
  cy: number,
  size: number,
): string {
  const w = size * 0.5;
  const h = size * 0.55;
  const top = cy - h * 0.35;
  const bottom = cy + h * 0.65;
  return [
    `M ${cx} ${bottom}`,
    `C ${cx - w * 1.3} ${cy - h * 0.1}, ${cx - w * 0.5} ${top - h * 0.3}, ${cx} ${top + h * 0.15}`,
    `C ${cx + w * 0.5} ${top - h * 0.3}, ${cx + w * 1.3} ${cy - h * 0.1}, ${cx} ${bottom}`,
    "Z",
  ].join(" ");
}

/**
 * Sprint 143: Generate an exclamation mark ❗ path — double-line bar + dot.
 */
export function generateExclaimPath(
  cx: number,
  cy: number,
  height: number,
): string {
  const barW = height * 0.15;
  const barH = height * 0.65;
  const dotR = height * 0.1;
  const gap = height * 0.08;
  const barTop = cy - height * 0.5;
  // Tapered bar (wider at top, narrower at bottom)
  const bar = `M ${cx - barW} ${barTop} L ${cx + barW} ${barTop} L ${cx + barW * 0.65} ${barTop + barH} L ${cx - barW * 0.65} ${barTop + barH} Z`;
  // Dot (circle via arc)
  const dotCy = barTop + barH + gap + dotR;
  const dot = `M ${cx + dotR} ${dotCy} A ${dotR} ${dotR} 0 1 1 ${cx - dotR} ${dotCy} A ${dotR} ${dotR} 0 1 1 ${cx + dotR} ${dotCy}`;
  return `${bar} ${dot}`;
}

/**
 * Sprint 143: Generate a question mark ? path — curved top + dot.
 */
export function generateQuestionPath(
  cx: number,
  cy: number,
  height: number,
): string {
  const r = height * 0.22;
  const dotR = height * 0.1;
  const top = cy - height * 0.5;
  // Curved hook of the question mark
  const hook = [
    `M ${cx - r * 0.6} ${top + r * 0.8}`,
    `C ${cx - r * 0.6} ${top - r * 0.3}, ${cx + r * 1.2} ${top - r * 0.3}, ${cx + r * 1.2} ${top + r * 1.2}`,
    `C ${cx + r * 1.2} ${top + r * 2}, ${cx} ${top + r * 1.8}, ${cx} ${top + r * 2.4}`,
  ].join(" ");
  // Dot below
  const dotCy = cy + height * 0.35;
  const dot = `M ${cx + dotR} ${dotCy} A ${dotR} ${dotR} 0 1 1 ${cx - dotR} ${dotCy} A ${dotR} ${dotR} 0 1 1 ${cx + dotR} ${dotCy}`;
  return `${hook} ${dot}`;
}
