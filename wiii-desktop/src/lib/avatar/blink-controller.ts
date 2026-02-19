/**
 * Blink controller — Sprint 129: SVG Face on Blob.
 * Sprint 130: Double-blink, adjustable duration, half-squint hold.
 * Natural blink timing using lognormal distribution.
 * Returns eyeScale for use with scaleY transform on eye groups.
 */

/** Default blink animation duration in seconds */
const DEFAULT_BLINK_DURATION = 0.15;

/** Minimum squeeze during blink (0.1 = nearly closed) */
const BLINK_SQUEEZE = 0.1;

/** Sprint 130: Probability of a double-blink after completing a blink */
const DOUBLE_BLINK_CHANCE = 0.20;

/** Sprint 130: Gap between double-blink in seconds (150-250ms) */
const DOUBLE_BLINK_GAP_MIN = 0.15;
const DOUBLE_BLINK_GAP_MAX = 0.25;

/** Sprint 130: Half-squint closure level (0.7 = 70% closed) */
const SQUINT_CLOSURE = 0.3;

/** Sprint 130: Half-squint hold duration in seconds */
const SQUINT_HOLD_DURATION = 0.3;

/** Sprint 130: Probability of squint during thinking (per blink cycle) */
const SQUINT_CHANCE = 0.10;

/**
 * Generate a lognormal-distributed inter-blink interval.
 * Natural blink rate ~15/min → mean interval ~4s,
 * with occasional rapid double-blinks and longer pauses.
 *
 * @param blinksPerMinute - Target blink rate
 * @returns Interval in seconds until next blink
 */
function nextBlinkInterval(blinksPerMinute: number): number {
  // Mean interval from blink rate
  const meanInterval = 60 / Math.max(1, blinksPerMinute);
  // Lognormal: exp(mu + sigma * Z) where Z ~ N(0,1)
  // Use Box-Muller transform for normal distribution
  const u1 = Math.random() || 0.001;
  const u2 = Math.random();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  // mu and sigma chosen so median ≈ meanInterval
  const mu = Math.log(meanInterval);
  const sigma = 0.4;
  const interval = Math.exp(mu + sigma * z);
  // Clamp to reasonable range (0.3s to 12s)
  return Math.max(0.3, Math.min(12, interval));
}

/**
 * Stateful blink controller. Call advance(dt) each frame to get
 * the current eye scaleY value (1.0 = open, 0.1 = blink squeeze).
 */
export class BlinkController {
  private countdown: number;
  private blinkProgress: number;
  private blinking: boolean;
  private blinkRate: number;
  private blinkDuration: number;

  /** Sprint 130: Double-blink state */
  isDoubleBlink: boolean;
  private doubleBlinkGap: number;
  private doubleBlinkCountdown: number;
  private awaitingDoubleBlink: boolean;

  /** Sprint 130: Half-squint state */
  squintEnabled: boolean;
  squintHold: boolean;
  private squintProgress: number;

  /** Sprint 143b: Follow-through — brief overshoot after blink (Disney Principle #8) */
  private followThrough: number;
  private readonly followThroughDuration: number = 0.08;

  constructor(blinksPerMinute: number = 15) {
    this.blinkRate = blinksPerMinute;
    this.countdown = nextBlinkInterval(blinksPerMinute);
    this.blinkProgress = 0;
    this.blinking = false;
    this.blinkDuration = DEFAULT_BLINK_DURATION;

    // Double-blink
    this.isDoubleBlink = false;
    this.doubleBlinkGap = 0;
    this.doubleBlinkCountdown = 0;
    this.awaitingDoubleBlink = false;

    // Squint
    this.squintEnabled = false;
    this.squintHold = false;
    this.squintProgress = 0;

    // Sprint 143b: Follow-through
    this.followThrough = 0;
  }

  /** Update blink rate (e.g. when state changes) */
  setRate(blinksPerMinute: number): void {
    this.blinkRate = blinksPerMinute;
  }

  /** Sprint 130: Set custom blink duration (e.g. 0.4s for slow contentment blinks) */
  setDuration(seconds: number): void {
    this.blinkDuration = Math.max(0.05, Math.min(1.0, seconds));
  }

  /**
   * Advance the blink timer by dt seconds.
   * @returns eyeScale: 1.0 (open) → BLINK_SQUEEZE (closed) → 1.0 (open)
   */
  advance(dt: number): number {
    // Sprint 130: Half-squint hold (thinking state)
    if (this.squintHold) {
      this.squintProgress += dt;
      if (this.squintProgress >= SQUINT_HOLD_DURATION) {
        this.squintHold = false;
        this.squintProgress = 0;
        this.countdown = nextBlinkInterval(this.blinkRate);
        return 1.0;
      }
      return SQUINT_CLOSURE;
    }

    // Sprint 130: Waiting for double-blink gap
    if (this.awaitingDoubleBlink) {
      this.doubleBlinkCountdown -= dt;
      if (this.doubleBlinkCountdown <= 0) {
        this.awaitingDoubleBlink = false;
        this.isDoubleBlink = true;
        this.blinking = true;
        this.blinkProgress = 0;
      }
      return 1.0;
    }

    // Sprint 143b: Follow-through overshoot after blink completes
    if (this.followThrough > 0) {
      this.followThrough -= dt;
      const ftProgress = 1 - (this.followThrough / this.followThroughDuration);
      return 1.0 + 0.05 * Math.sin(ftProgress * Math.PI);
    }

    if (this.blinking) {
      this.blinkProgress += dt;
      if (this.blinkProgress >= this.blinkDuration) {
        // Blink finished
        this.blinking = false;
        this.blinkProgress = 0;

        // Sprint 143b: Activate follow-through
        this.followThrough = this.followThroughDuration;

        // Sprint 130: Check for double-blink (only if this wasn't already a double)
        if (!this.isDoubleBlink && Math.random() < DOUBLE_BLINK_CHANCE) {
          this.awaitingDoubleBlink = true;
          this.doubleBlinkGap = DOUBLE_BLINK_GAP_MIN +
            Math.random() * (DOUBLE_BLINK_GAP_MAX - DOUBLE_BLINK_GAP_MIN);
          this.doubleBlinkCountdown = this.doubleBlinkGap;
          return 1.0;
        }

        this.isDoubleBlink = false;
        this.countdown = nextBlinkInterval(this.blinkRate);
        return 1.0;
      }
      // Blink animation: squash then return
      // t goes 0→1 over blinkDuration
      const t = this.blinkProgress / this.blinkDuration;
      // Parabola: 1 → BLINK_SQUEEZE → 1
      const squeeze = 1 - (1 - BLINK_SQUEEZE) * Math.sin(Math.PI * t);
      return squeeze;
    }

    this.countdown -= dt;
    if (this.countdown <= 0) {
      // Sprint 130: Chance of squint instead of blink (when enabled)
      if (this.squintEnabled && Math.random() < SQUINT_CHANCE) {
        this.squintHold = true;
        this.squintProgress = 0;
        return SQUINT_CLOSURE;
      }

      this.blinking = true;
      this.blinkProgress = 0;
    }
    return 1.0;
  }

  /** Force an immediate blink (e.g. on state transition) */
  triggerBlink(): void {
    this.blinking = true;
    this.blinkProgress = 0;
    this.isDoubleBlink = false;
    this.awaitingDoubleBlink = false;
    this.squintHold = false;
  }
}
