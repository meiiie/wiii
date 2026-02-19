/**
 * Sprint 144: Eye Saccade State Machine — Naturalistic Gaze Behavior.
 * Replaces noise-based drift with intentional fixate→saccade→fixate pattern.
 * Based on real eye movement research: fixations last 200ms-2s,
 * saccades are 30-80ms rapid jumps between targets.
 */
import type { AvatarState } from "./types";

export type GazeTarget = "user" | "away_left" | "away_right" | "up_think" | "down" | "center";

export const GAZE_TARGETS: Record<GazeTarget, { x: number; y: number }> = {
  user:       { x: 0,    y: 0.1  },
  away_left:  { x: -0.6, y: -0.1 },
  away_right: { x: 0.6,  y: -0.1 },
  up_think:   { x: 0.3,  y: -0.5 },
  down:       { x: 0,    y: 0.4  },
  center:     { x: 0,    y: 0    },
};

/** Per-state weight tables: probability of each gaze target */
const STATE_GAZE_WEIGHTS: Record<AvatarState, Record<GazeTarget, number>> = {
  idle:      { user: 60, away_left: 15, away_right: 15, up_think: 0, down: 0, center: 10 },
  listening: { user: 80, away_left: 5, away_right: 5, up_think: 5, down: 0, center: 5 },
  thinking:  { user: 10, away_left: 25, away_right: 25, up_think: 30, down: 0, center: 10 },
  speaking:  { user: 50, away_left: 20, away_right: 20, up_think: 0, down: 0, center: 10 },
  error:     { user: 30, away_left: 20, away_right: 20, up_think: 0, down: 20, center: 10 },
  complete:  { user: 70, away_left: 5, away_right: 5, up_think: 0, down: 10, center: 10 },
};

/** Per-state fixation duration ranges [min, max] in seconds */
const FIXATION_DURATIONS: Record<AvatarState, [number, number]> = {
  idle:      [1.0, 2.0],
  listening: [1.5, 2.5],
  thinking:  [0.3, 1.0],
  speaking:  [0.5, 1.5],
  error:     [0.2, 0.8],
  complete:  [1.5, 2.0],
};

/** Saccade (rapid eye jump) duration range in seconds */
const SACCADE_DURATION_MIN = 0.03;
const SACCADE_DURATION_MAX = 0.08;

type GazePhase = "fixation" | "saccade";

function pickWeightedTarget(weights: Record<GazeTarget, number>, excludeTarget?: GazeTarget): GazeTarget {
  const entries = Object.entries(weights) as [GazeTarget, number][];
  // Reduce weight of current target to encourage variety
  const adjusted = entries.map(([t, w]) => [t, t === excludeTarget ? w * 0.2 : w] as [GazeTarget, number]);
  const total = adjusted.reduce((s, [, w]) => s + w, 0);
  if (total <= 0) return "center";
  let roll = Math.random() * total;
  for (const [target, weight] of adjusted) {
    roll -= weight;
    if (roll <= 0) return target;
  }
  return adjusted[adjusted.length - 1][0];
}

function randomRange(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

export class GazeController {
  private state: AvatarState = "idle";
  private phase: GazePhase = "fixation";
  private currentTarget: GazeTarget = "user";
  private nextTarget: GazeTarget = "user";
  private phaseTimer = 0;
  private phaseDuration = 1.5;

  // Smooth positions (current interpolated)
  private currentX = 0;
  private currentY = 0.1;
  // Saccade start position
  private saccadeFromX = 0;
  private saccadeFromY = 0;

  setState(newState: AvatarState): void {
    if (newState !== this.state) {
      this.state = newState;
      // Start a new fixation cycle for the new state
      this.triggerSaccade();
    }
  }

  triggerSaccade(): void {
    const weights = STATE_GAZE_WEIGHTS[this.state] || STATE_GAZE_WEIGHTS.idle;
    this.nextTarget = pickWeightedTarget(weights, this.currentTarget);
    this.phase = "saccade";
    this.phaseTimer = 0;
    this.phaseDuration = randomRange(SACCADE_DURATION_MIN, SACCADE_DURATION_MAX);
    this.saccadeFromX = this.currentX;
    this.saccadeFromY = this.currentY;
  }

  /**
   * Advance the gaze controller by dt seconds.
   * @param dt - Delta time
   * @param mouse - Optional mouse position override
   * @returns Normalized gaze offset { x, y } in range ~[-1, 1]
   */
  advance(dt: number, mouse?: { x: number; y: number; influence: number }): { x: number; y: number } {
    this.phaseTimer += dt;

    if (this.phase === "saccade") {
      // Rapid jump to new target
      const t = Math.min(this.phaseTimer / this.phaseDuration, 1);
      // Ease-out for saccade (fast start, decelerate)
      const eased = 1 - Math.pow(1 - t, 3);
      const target = GAZE_TARGETS[this.nextTarget];
      this.currentX = this.saccadeFromX + (target.x - this.saccadeFromX) * eased;
      this.currentY = this.saccadeFromY + (target.y - this.saccadeFromY) * eased;

      if (t >= 1) {
        // Saccade complete → enter fixation
        this.currentTarget = this.nextTarget;
        this.currentX = target.x;
        this.currentY = target.y;
        this.phase = "fixation";
        this.phaseTimer = 0;
        const [min, max] = FIXATION_DURATIONS[this.state] || [1, 2];
        this.phaseDuration = randomRange(min, max);
      }
    } else {
      // Fixation — hold with micro-drift
      if (this.phaseTimer >= this.phaseDuration) {
        // Time for a new saccade
        this.triggerSaccade();
      }
    }

    // Mouse tracking blends on top (when available and not thinking)
    let outX = this.currentX;
    let outY = this.currentY;
    if (mouse && mouse.influence > 0 && this.state !== "thinking") {
      const blend = 0.6 * mouse.influence;
      outX = outX * (1 - blend) + mouse.x * blend;
      outY = outY * (1 - blend) + mouse.y * blend;
    } else if (mouse && mouse.influence > 0 && this.state === "thinking") {
      const blend = 0.12 * mouse.influence;
      outX = outX * (1 - blend) + mouse.x * blend;
      outY = outY * (1 - blend) + mouse.y * blend;
    }

    return { x: outX, y: outY };
  }

  getCurrentTarget(): GazeTarget {
    return this.currentTarget;
  }

  getPhase(): GazePhase {
    return this.phase;
  }
}
