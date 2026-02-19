/**
 * State visual configurations — Sprint 115: Living Avatar Foundation.
 * 6 states x 15 visual parameters each.
 */
import type { SizeTier, StateVisuals } from "./types";

/** Determine rendering tier from pixel size */
export function getSizeTier(size: number): SizeTier {
  if (size <= 20) return "tiny";
  if (size <= 36) return "medium";
  return "large";
}

/** Blob vertex count per tier (quality vs performance) */
export function getBlobResolution(tier: SizeTier): number {
  switch (tier) {
    case "tiny": return 0;     // CSS only, no blob
    case "medium": return 48;
    case "large": return 64;
  }
}

const ORANGE = "var(--accent-orange, #f97316)";
const GREEN = "var(--accent-green, #22c55e)";
const AMBER = "var(--accent-amber, #f59e0b)";

const ORANGE_HEX = "#f97316";
const GREEN_HEX = "#22c55e";
const AMBER_HEX = "#f59e0b";

/** Visual configuration for each avatar state */
export const STATE_CONFIG: Record<string, StateVisuals> = {
  idle: {
    noiseAmplitude: 0.06,
    noiseFrequency: 1.2,
    timeSpeed: 0.3,
    glowIntensity: 0.08,
    glowColor: ORANGE_HEX,
    blobColor: ORANGE,
    blobColorHex: ORANGE_HEX,
    scale: 1.0,
    indicatorColor: GREEN_HEX,
    indicatorVisible: true,
    particleCount: 3,
    particleColor: ORANGE_HEX,
    particleOrbitSpeed: 0.2,
    particleDriftSpeed: 0,
    tinyBorderRadius: "30%",
  },
  listening: {
    noiseAmplitude: 0.04,
    noiseFrequency: 0.8,
    timeSpeed: 0.15,
    glowIntensity: 0.18,
    glowColor: ORANGE_HEX,
    blobColor: ORANGE,
    blobColorHex: ORANGE_HEX,
    scale: 1.05,
    indicatorColor: GREEN_HEX,
    indicatorVisible: true,
    particleCount: 2,
    particleColor: ORANGE_HEX,
    particleOrbitSpeed: 0.1,
    particleDriftSpeed: 0,
    tinyBorderRadius: "30%",
  },
  thinking: {
    noiseAmplitude: 0.12,
    noiseFrequency: 1.8,
    timeSpeed: 0.8,
    glowIntensity: 0.35,
    glowColor: ORANGE_HEX,
    blobColor: ORANGE,
    blobColorHex: ORANGE_HEX,
    scale: 1.0,
    indicatorColor: ORANGE_HEX,
    indicatorVisible: true,
    particleCount: 8,
    particleColor: ORANGE_HEX,
    particleOrbitSpeed: 1.5,
    particleDriftSpeed: 0.3,
    tinyBorderRadius: "30%",
  },
  speaking: {
    noiseAmplitude: 0.09,
    noiseFrequency: 1.4,
    timeSpeed: 0.6,
    glowIntensity: 0.25,
    glowColor: ORANGE_HEX,
    blobColor: ORANGE,
    blobColorHex: ORANGE_HEX,
    scale: 1.02,
    indicatorColor: GREEN_HEX,
    indicatorVisible: true,
    particleCount: 5,
    particleColor: ORANGE_HEX,
    particleOrbitSpeed: 0.8,
    particleDriftSpeed: 0.5,
    tinyBorderRadius: "30%",
  },
  complete: {
    noiseAmplitude: 0.03,
    noiseFrequency: 1.0,
    timeSpeed: 0.2,
    glowIntensity: 0.40,
    glowColor: GREEN_HEX,
    blobColor: GREEN,
    blobColorHex: GREEN_HEX,
    scale: 1.0,
    indicatorColor: GREEN_HEX,
    indicatorVisible: true,
    particleCount: 0,
    particleColor: GREEN_HEX,
    particleOrbitSpeed: 0,
    particleDriftSpeed: 0,
    tinyBorderRadius: "30%",
  },
  error: {
    noiseAmplitude: 0.08,
    noiseFrequency: 1.6,
    timeSpeed: 0.5,
    glowIntensity: 0.20,
    glowColor: AMBER_HEX,
    blobColor: AMBER,
    blobColorHex: AMBER_HEX,
    scale: 1.0,
    indicatorColor: AMBER_HEX,
    indicatorVisible: false,
    particleCount: 0,
    particleColor: AMBER_HEX,
    particleOrbitSpeed: 0,
    particleDriftSpeed: 0,
    tinyBorderRadius: "30%",
  },
};
