export type HitMode = "hit" | "slash" | "soft" | "quiet";

export class StageFX {
  private ctx: CanvasRenderingContext2D | null;
  private w = 1;
  private h = 1;
  private rafFlash = 0;

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
    const ctx = this.ctx;
    if (!ctx) return;
    ctx.globalCompositeOperation = "destination-out";
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.fillRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = "source-over";
  }

  hit(x: number, y: number, text: string, rot: number, mode: HitMode): void {
    this.glyph.style.setProperty("--rot", `${rot}deg`);
    this.glyph.style.left = `${x}px`;
    this.glyph.style.top = `${y}px`;
    this.glyph.textContent = text;
    this.glyph.classList.toggle("quiet", mode === "quiet");
    this.glyph.classList.remove("on");
    void this.glyph.offsetWidth;
    this.glyph.classList.add("on");

    if (mode === "hit" || mode === "slash") {
      this.flash.style.opacity = "1";
      window.clearTimeout(this.rafFlash);
      this.rafFlash = window.setTimeout(() => {
        this.flash.style.opacity = "0";
      }, 70);
    }
    if (mode === "hit") this.shade.style.opacity = "0.78";
    if (mode === "quiet") this.grain.style.opacity = "0.38";
    window.setTimeout(() => {
      this.shade.style.opacity = "0";
      if (mode === "quiet") this.grain.style.opacity = "";
    }, mode === "hit" ? 280 : 180);

    const count = mode === "quiet" ? 18 : mode === "soft" ? 28 : 56;
    this.burst(x, y, count, mode === "slash" ? 0.15 : 1);
  }

  streaks(strength: number): void {
    const ctx = this.ctx;
    if (!ctx || strength < 0.08) return;
    const n = Math.floor(8 + strength * 24);
    ctx.strokeStyle = `rgba(245,240,230,${0.15 + strength * 0.35})`;
    ctx.lineWidth = 1;
    for (let i = 0; i < n; i++) {
      const y = Math.random() * this.h;
      const len = 40 + Math.random() * 180 * strength;
      const x = Math.random() * this.w;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + len, y + (Math.random() - 0.5) * 6);
      ctx.stroke();
    }
  }

  radial(x: number, y: number, amount: number): void {
    const ctx = this.ctx;
    if (!ctx || amount <= 0.02) return;
    const n = 36;
    ctx.strokeStyle = `rgba(245,240,230,${0.08 + amount * 0.18})`;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + amount;
      const inner = 40 + (i % 5) * 16;
      const outer = inner + 80 + amount * 220 * ((i * 7) % 5) / 5;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * inner, y + Math.sin(a) * inner);
      ctx.lineTo(x + Math.cos(a) * outer, y + Math.sin(a) * outer);
      ctx.stroke();
    }
  }

  private burst(x: number, y: number, count: number, red: number): void {
    const ctx = this.ctx;
    if (!ctx) return;
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2 + Math.random() * 0.2;
      const len = 70 + Math.random() * 220;
      const inner = 8 + Math.random() * 30;
      ctx.strokeStyle = i % 7 === 0 && red > 0.2 ? "rgba(225,6,0,0.9)" : "rgba(245,240,230,0.85)";
      ctx.lineWidth = i % 4 === 0 ? 2.5 : 1;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * inner, y + Math.sin(a) * inner);
      ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
      ctx.stroke();
    }
    for (let i = 0; i < 8; i++) {
      const a = Math.random() * Math.PI * 2;
      const d = 30 + Math.random() * 90;
      ctx.fillStyle = "rgba(245,240,230,0.8)";
      ctx.fillRect(x + Math.cos(a) * d, y + Math.sin(a) * d, 3 + Math.random() * 7, 2);
    }
  }
}
