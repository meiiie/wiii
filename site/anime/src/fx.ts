export type HitMode = "major" | "micro" | "quiet";

export class StageFX {
  private ctx: CanvasRenderingContext2D | null;
  private w = 1;
  private h = 1;
  private timers: number[] = [];
  private lastFull = -1e9;
  private cool = 0;
  /** While true, the director must not overwrite the inversion frames. */
  holding = false;

  constructor(
    private canvas: HTMLCanvasElement,
    private flash: HTMLElement,
    private shade: HTMLElement,
    private glyph: HTMLElement,
    private grain: HTMLElement,
  ) {
    this.ctx = canvas.getContext("2d");
  }

  resize(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    this.w = window.innerWidth;
    this.h = window.innerHeight;
    this.canvas.width = Math.floor(this.w * dpr);
    this.canvas.height = Math.floor(this.h * dpr);
    this.ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  fade(): void {
    if (this.holding || performance.now() < this.cool) return;
    const ctx = this.ctx;
    if (!ctx) return;
    ctx.globalCompositeOperation = "destination-out";
    ctx.fillStyle = "rgba(0,0,0,0.22)";
    ctx.fillRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = "source-over";
  }

  clear(): void {
    if (this.holding) return;
    this.ctx?.clearRect(0, 0, this.w, this.h);
  }

  /**
   * A major strike is two full-screen inversions (white, then black), then a
   * held drawing. A second major inside 1.1s is downgraded so the page stays
   * under three flashes in any one second.
   */
  strike(x: number, y: number, text: string, rot: number, mode: HitMode): HitMode {
    const now = performance.now();
    let resolved: HitMode = mode;
    if (mode === "major" && now - this.lastFull < 1100) resolved = "micro";
    this.paintGlyph(x, y, text, rot, resolved);
    this.cool = now + (resolved === "major" ? 0 : 780);
    if (resolved === "major") {
      this.lastFull = now;
      this.invert(x, y);
    } else {
      this.burst(x, y, resolved === "quiet" ? 14 : 36, resolved === "quiet" ? 0 : 0.7);
      if (resolved === "quiet") {
        this.grain.style.opacity = "0.42";
        this.later(() => {
          this.grain.style.opacity = "";
        }, 480);
      }
    }
    return resolved;
  }

  streaks(strength: number): void {
    if (this.holding) return;
    const ctx = this.ctx;
    if (!ctx || strength < 0.08) return;
    const n = Math.floor(6 + strength * 16);
    ctx.strokeStyle = `rgba(245,240,230,${0.18 + strength * 0.4})`;
    ctx.lineWidth = 1.25;
    for (let i = 0; i < n; i++) {
      const y = Math.random() * this.h;
      const len = 60 + Math.random() * 200 * strength;
      const x = Math.random() * this.w;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + len, y + (Math.random() - 0.5) * 4);
      ctx.stroke();
    }
  }

  radial(x: number, y: number, amount: number): void {
    if (this.holding) return;
    const ctx = this.ctx;
    if (!ctx || amount <= 0.02) return;
    const n = 28;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      const inner = 30 + (i % 4) * 18;
      const outer = inner + 90 + amount * 260 * ((i * 5) % 4) / 4;
      ctx.strokeStyle = i % 9 === 0 ? "rgba(224,38,31,0.85)" : `rgba(245,240,230,${0.12 + amount * 0.2})`;
      ctx.lineWidth = i % 5 === 0 ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * inner, y + Math.sin(a) * inner);
      ctx.lineTo(x + Math.cos(a) * outer, y + Math.sin(a) * outer);
      ctx.stroke();
    }
  }

  private paintGlyph(x: number, y: number, text: string, rot: number, mode: HitMode): void {
    if (!text) return;
    this.glyph.style.setProperty("--rot", `${rot}deg`);
    this.glyph.style.left = `${x}px`;
    this.glyph.style.top = `${y}px`;
    this.glyph.textContent = text;
    this.glyph.classList.toggle("quiet", mode === "quiet");
    this.glyph.classList.remove("on");
    void this.glyph.offsetWidth;
    this.glyph.classList.add("on");
  }

  private invert(x: number, y: number): void {
    const root = document.documentElement;
    this.clearTimers();
    this.holding = true;
    this.flash.style.opacity = "1";
    this.shade.style.opacity = "0";
    root.classList.add("is-chroma");
    this.burst(x, y, 72, 1);
    this.later(() => {
      this.flash.style.opacity = "0";
      this.shade.style.opacity = "1";
      root.classList.remove("is-chroma");
    }, 80);
    // Two flashes, then a black plate long enough to survive a fast scroll
    // and video compression. The plate is a hold, not another flash.
    this.later(() => {
      this.shade.style.opacity = "0";
      this.holding = false;
    }, 620);
  }

  private later(fn: () => void, ms: number): void {
    this.timers.push(window.setTimeout(fn, ms));
  }

  private clearTimers(): void {
    for (const timer of this.timers) window.clearTimeout(timer);
    this.timers = [];
  }

  private burst(x: number, y: number, count: number, red: number): void {
    const ctx = this.ctx;
    if (!ctx) return;
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2;
      const len = 90 + ((i * 47) % 180);
      const inner = 6 + (i % 5) * 10;
      ctx.strokeStyle = i % 3 === 0 && red > 0 ? "rgba(224,38,31,0.96)" : i % 3 === 1 ? "rgba(11,11,13,0.9)" : "rgba(245,240,230,0.94)";
      ctx.lineWidth = i % 4 === 0 ? 5 : 2;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * inner, y + Math.sin(a) * inner);
      ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
      ctx.stroke();
    }
  }
}
