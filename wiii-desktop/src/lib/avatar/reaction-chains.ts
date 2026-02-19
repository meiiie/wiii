/**
 * Sprint 144: Reaction Chain System — Sequential Compound Emotions.
 * Instead of single micro-reactions, chains play sequential steps
 * for cinematic emotion arcs (e.g., surprise → sparkle → nod).
 */
import type { MicroReaction } from "./types";
import { REACTION_REGISTRY } from "./micro-reaction-registry";

export interface ReactionChainStep {
  type: MicroReaction["type"];
  duration?: number;   // override registry default duration
  gapBefore?: number;  // pause before this step (seconds)
}

export interface ReactionChain {
  steps: ReactionChainStep[];
}

export const REACTION_CHAINS: Record<string, ReactionChain> = {
  surprise_to_smile: {
    steps: [
      { type: "surprise", duration: 0.15 },
      { type: "sparkle_eyes", gapBefore: 0.05, duration: 0.25 },
      { type: "nod", gapBefore: 0.08, duration: 0.3 },
    ],
  },
  panic_to_relief: {
    steps: [
      { type: "panic", duration: 0.2 },
      { type: "flinch", gapBefore: 0.05, duration: 0.35 },
      { type: "sigh", gapBefore: 0.1, duration: 0.5 },
    ],
  },
  love_struck: {
    steps: [
      { type: "doki", duration: 0.3 },
      { type: "blush_deep", gapBefore: 0.05, duration: 0.4 },
      { type: "shy", gapBefore: 0.05, duration: 0.35 },
    ],
  },
  false_alarm: {
    steps: [
      { type: "startle", duration: 0.12 },
      { type: "perk", gapBefore: 0.1, duration: 0.2 },
      { type: "giggle", gapBefore: 0.08, duration: 0.4 },
    ],
  },
  frustration: {
    steps: [
      { type: "hmph", duration: 0.25 },
      { type: "eye_twitch", gapBefore: 0.2, duration: 0.15 },
      { type: "sigh", gapBefore: 0.15, duration: 0.5 },
    ],
  },
};

export interface ChainPlayback {
  chainId: string;
  currentStepIndex: number;
  stepElapsed: number;
  gapElapsed: number;
  inGap: boolean;
}

export function createChainPlayback(chainId: string): ChainPlayback {
  return {
    chainId,
    currentStepIndex: 0,
    stepElapsed: 0,
    gapElapsed: 0,
    inGap: false,
  };
}

/**
 * Advance a chain playback by dt seconds.
 * Returns the current active reaction (or null if in gap/finished).
 */
export function advanceChain(
  playback: ChainPlayback,
  chain: ReactionChain,
  dt: number,
): { reaction: MicroReaction | null; finished: boolean } {
  if (playback.currentStepIndex >= chain.steps.length) {
    return { reaction: null, finished: true };
  }

  const step = chain.steps[playback.currentStepIndex];
  const stepDuration = step.duration ?? REACTION_REGISTRY[step.type]?.duration ?? 0.3;

  // Handle gap before step
  if (playback.inGap) {
    playback.gapElapsed += dt;
    const gap = step.gapBefore ?? 0;
    if (playback.gapElapsed >= gap) {
      playback.inGap = false;
      playback.stepElapsed = 0;
    }
    return { reaction: null, finished: false };
  }

  // Advance step
  playback.stepElapsed += dt;

  if (playback.stepElapsed >= stepDuration) {
    // Step complete — move to next
    playback.currentStepIndex++;
    if (playback.currentStepIndex >= chain.steps.length) {
      return { reaction: null, finished: true };
    }
    // Check if next step has a gap
    const nextStep = chain.steps[playback.currentStepIndex];
    if (nextStep.gapBefore && nextStep.gapBefore > 0) {
      playback.inGap = true;
      playback.gapElapsed = 0;
    } else {
      playback.stepElapsed = 0;
    }
    return { reaction: null, finished: false };
  }

  // Active step — return current reaction
  return {
    reaction: {
      type: step.type,
      elapsed: playback.stepElapsed,
      duration: stepDuration,
    },
    finished: false,
  };
}
