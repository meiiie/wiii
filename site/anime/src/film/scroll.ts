import { MasterTimeline } from "./timeline";

const WHEEL_K = 30;
const TOUCH_K = 3.2;
const CLAMP = 500;
const INERTIA_TC = 0.32;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export class VirtualScroll {
  target = 0;
  pos = 0;
  cam = 0;
  inertia = 0;
  rigX = 0;
  rigY = 0;
  aimX = 0;
  aimY = 0;
  locked = false;
  strikes = 0;
  private ema = 0;
  private lastY = 0;
  private lastT = 0;
  private tracking = false;
  private moved = 0;
  private originT = 0;
  private pointers = 0;

  constructor(
    private timeline: MasterTimeline,
    private onStrike: () => void,
  ) {}

  bind(): void {
    window.addEventListener("wheel", this.onWheel, { passive: false });
    window.addEventListener("touchstart", this.onStart, { passive: true });
    window.addEventListener("touchmove", this.onMove, { passive: false });
    window.addEventListener("touchend", this.onEnd, { passive: true });
    window.addEventListener("touchcancel", this.onCancel, { passive: true });
    window.addEventListener("keydown", this.onKey);
    window.addEventListener("pointermove", this.onPointer);
    window.addEventListener("deviceorientation", this.onGyro);
    document.addEventListener("visibilitychange", this.onHide);
  }

  destroy(): void {
    window.removeEventListener("wheel", this.onWheel);
    window.removeEventListener("touchstart", this.onStart);
    window.removeEventListener("touchmove", this.onMove);
    window.removeEventListener("touchend", this.onEnd);
    window.removeEventListener("touchcancel", this.onCancel);
    window.removeEventListener("keydown", this.onKey);
    window.removeEventListener("pointermove", this.onPointer);
    window.removeEventListener("deviceorientation", this.onGyro);
    document.removeEventListener("visibilitychange", this.onHide);
  }

  snap(x: number): void {
    this.target = this.pos = this.cam = x;
    this.inertia = 0;
    this.timeline.energy = 0;
    this.timeline.playhead = x;
  }

  update(dt: number, now: number): void {
    if (document.hidden) {
      this.inertia = 0;
      this.ema = 0;
    }
    if (!this.locked && this.inertia !== 0) {
      this.timeline.absorb(this.inertia * dt, now);
      this.inertia *= Math.exp(-dt / INERTIA_TC);
      if (Math.abs(this.inertia) < 5) this.inertia = 0;
    }
    if (!this.locked) this.target = this.timeline.release(this.target);
    const k = 1 - Math.exp(-dt / 0.214);
    if (!this.locked) {
      this.pos += (this.target - this.pos) * k;
      if (Math.abs(this.pos - this.target) < 0.5) this.pos = this.target;
    }
    const kc = 1 - Math.exp(-dt / 0.2);
    this.cam += (this.pos - this.cam) * kc;
    if (Math.abs(this.cam - this.pos) < 0.5) this.cam = this.pos;
    const kr = 1 - Math.exp(-dt / 0.12);
    this.rigX += (this.aimX - this.rigX) * kr;
    this.rigY += (this.aimY - this.rigY) * kr;
    this.timeline.playhead = this.cam;
    const done = this.timeline.update(dt, this.pos, now);
    this.locked = this.timeline.gate !== null;
    if (done) {
      this.pos = this.cam = this.target = done.snap;
      this.timeline.playhead = done.snap;
      this.inertia = 0;
      this.locked = false;
    }
    if (window.scrollY !== 0) window.scrollTo(0, 0);
  }

  private deltaPx(e: WheelEvent): number {
    let dy = e.deltaY;
    if (e.deltaMode === 1) dy *= 16;
    else if (e.deltaMode === 2) dy *= window.innerHeight;
    return clamp(dy, -CLAMP, CLAMP);
  }

  private onWheel = (e: WheelEvent): void => {
    e.preventDefault();
    this.timeline.absorb(this.deltaPx(e) * WHEEL_K, performance.now());
  };

  private onStart = (e: TouchEvent): void => {
    if (e.touches.length !== 1) {
      this.tracking = false;
      this.inertia = 0;
      this.ema = 0;
      return;
    }
    const t = e.touches[0];
    this.tracking = true;
    this.pointers = 1;
    this.lastY = t.clientY;
    this.originT = performance.now();
    this.lastT = this.originT;
    this.moved = 0;
    this.inertia = 0;
    this.aimX = clamp((t.clientX / window.innerWidth - 0.5) * 0.03, -0.015, 0.015);
    this.aimY = clamp((t.clientY / window.innerHeight - 0.5) * 0.03, -0.015, 0.015);
  };

  private onMove = (e: TouchEvent): void => {
    if (!this.tracking || e.touches.length !== 1) return;
    e.preventDefault();
    const t = e.touches[0];
    const now = performance.now();
    const dy = clamp(this.lastY - t.clientY, -CLAMP, CLAMP);
    const dt = Math.max(0.008, (now - this.lastT) / 1000);
    const inst = (this.lastY - t.clientY) / dt;
    this.ema += (inst - this.ema) * (1 - Math.exp(-dt / 0.08));
    this.moved += Math.abs(dy);
    this.lastY = t.clientY;
    this.lastT = now;
    if (this.moved >= 10) this.timeline.absorb(dy * TOUCH_K, now);
  };

  private onEnd = (e: TouchEvent): void => {
    if (e.touches.length > 0) return;
    const now = performance.now();
    const tap = this.tracking && this.moved < 10 && now - this.originT < 250 && this.pointers === 1;
    if (tap) {
      this.strikes += 1;
      this.onStrike();
      this.ema = 0;
      this.inertia = 0;
    } else if (this.tracking && Math.abs(this.ema) > 8) {
      if (this.locked) this.timeline.absorb(this.ema * TOUCH_K * INERTIA_TC, now);
      else this.inertia = this.ema * TOUCH_K;
    }
    this.tracking = false;
    this.ema = 0;
    this.pointers = 0;
  };

  private onCancel = (): void => {
    this.tracking = false;
    this.inertia = 0;
    this.ema = 0;
    this.pointers = 0;
  };

  private onHide = (): void => {
    if (document.hidden) {
      this.inertia = 0;
      this.ema = 0;
      this.tracking = false;
    }
  };

  private onPointer = (e: PointerEvent): void => {
    if (e.pointerType === "touch") return;
    this.aimX = clamp((e.clientX / window.innerWidth - 0.5) * 0.03, -0.015, 0.015);
    this.aimY = clamp((e.clientY / window.innerHeight - 0.5) * 0.03, -0.015, 0.015);
  };

  private onGyro = (e: DeviceOrientationEvent): void => {
    if (e.gamma == null || e.beta == null) return;
    this.aimX = clamp(e.gamma / 20, -1, 1) * 0.015;
    this.aimY = clamp((e.beta - 45) / 20, -1, 1) * 0.015;
  };

  private onKey = (e: KeyboardEvent): void => {
    const tag = (e.target as HTMLElement | null)?.tagName;
    if (tag === "BUTTON" || tag === "A" || tag === "INPUT" || tag === "TEXTAREA") {
      if (e.key === " " || e.key === "Enter") return;
    }
    const view = window.innerHeight;
    const now = performance.now();
    let delta = 0;
    if (e.key === "ArrowDown") delta = view * 0.6;
    else if (e.key === "ArrowUp") delta = -view * 0.6;
    else if (e.key === "PageDown") delta = view;
    else if (e.key === "PageUp") delta = -view;
    else if (e.key === " ") delta = e.shiftKey ? -view * 0.6 : view * 0.6;
    else if (e.key === "Home") {
      e.preventDefault();
      this.snap(this.timeline.floor());
      return;
    } else if (e.key === "End") {
      e.preventDefault();
      this.snap(this.timeline.cap());
      return;
    } else return;
    e.preventDefault();
    this.timeline.absorb(delta, now);
  };
}
