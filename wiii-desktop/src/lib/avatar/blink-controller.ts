/**
 * Blink controller — Sprint 129: SVG Face on Blob.
 * Natural blink timing using lognormal distribution.
 * Returns eyeScale for use with scaleY transform on eye groups.
 */

/** Blink animation duration in seconds */
const BLINK_DURATION = 0.15;

/** Minimum squeeze during blink (0.1 = nearly closed) */
const BLINK_SQUEEZE = 0.1;

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

  constructor(blinksPerMinute: number = 15) {
    this.blinkRate = blinksPerMinute;
    this.countdown = nextBlinkInterval(blinksPerMinute);
    this.blinkProgress = 0;
    this.blinking = false;
  }

  /** Update blink rate (e.g. when state changes) */
  setRate(blinksPerMinute: number): void {
    this.blinkRate = blinksPerMinute;
  }

  /**
   * Advance the blink timer by dt seconds.
   * @returns eyeScale: 1.0 (open) → BLINK_SQUEEZE (closed) → 1.0 (open)
   */
  advance(dt: number): number {
    if (this.blinking) {
      this.blinkProgress += dt;
      if (this.blinkProgress >= BLINK_DURATION) {
        // Blink finished
        this.blinking = false;
        this.blinkProgress = 0;
        this.countdown = nextBlinkInterval(this.blinkRate);
        return 1.0;
      }
      // Blink animation: squash then return
      // t goes 0→1 over BLINK_DURATION
      const t = this.blinkProgress / BLINK_DURATION;
      // Parabola: 1 → BLINK_SQUEEZE → 1
      // eyeScale = 1 - (1-BLINK_SQUEEZE) * sin(PI * t)
      const squeeze = 1 - (1 - BLINK_SQUEEZE) * Math.sin(Math.PI * t);
      return squeeze;
    }

    this.countdown -= dt;
    if (this.countdown <= 0) {
      this.blinking = true;
      this.blinkProgress = 0;
    }
    return 1.0;
  }

  /** Force an immediate blink (e.g. on state transition) */
  triggerBlink(): void {
    this.blinking = true;
    this.blinkProgress = 0;
  }
}
