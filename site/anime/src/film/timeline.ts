import { ACTS, type ActId } from "./plates";

export type GateKind = "ink" | "smear" | "shatter";

const VH = 2.15;
const SEAL_AT = 0.64;
const SEAL_SECONDS = 0.85;

const GATES: { kind: GateKind; dur: number }[] = [
  { kind: "ink", dur: 0.62 },
  { kind: "ink", dur: 0.6 },
  { kind: "smear", dur: 0.78 },
  { kind: "ink", dur: 0.62 },
  { kind: "shatter", dur: 1.05 },
  { kind: "ink", dur: 0.7 },
  { kind: "ink", dur: 0.6 },
];

export type Segment = { id: ActId; start: number; end: number };

export type Gate = {
  from: number;
  to: number;
  kind: GateKind;
  dur: number;
  t: number;
  dir: 1 | -1;
};

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

export class MasterTimeline {
  segments: Segment[] = [];
  active = 0;
  gate: Gate | null = null;
  seal = 0;
  sealed = false;
  holding = false;
  playhead = 0;
  energy = 0;
  private recent = 0;
  private viewH = 800;

  constructor() {
    this.layout(800, true);
  }

  layout(viewH: number, first = false): number {
    const keep = first ? 0 : this.progress;
    const sealed = this.sealed;
    const seal = this.seal;
    this.viewH = Math.max(1, viewH);
    let cursor = 0;
    this.segments = ACTS.map((id) => {
      const len = VH * this.viewH;
      const seg = { id, start: cursor, end: cursor + len };
      cursor += len;
      return seg;
    });
    if (first) return 0;
    const x = this.seekProgress(keep);
    this.sealed = sealed || this.sealed;
    this.seal = Math.max(seal, this.seal);
    return x;
  }

  get total(): number {
    return this.segments[this.segments.length - 1]?.end ?? 1;
  }

  get progress(): number {
    return clamp01(this.playhead / Math.max(1, this.total));
  }

  get act(): ActId {
    return this.segments[this.active]?.id ?? "awaken";
  }

  floor(index = this.active): number {
    return this.segments[index]?.start ?? 0;
  }

  cap(index = this.active): number {
    const seg = this.segments[index];
    if (!seg) return 0;
    if (seg.id === "kakoi" && !this.sealed) return seg.start + (seg.end - seg.start) * SEAL_AT;
    return seg.end;
  }

  clamp(v: number): number {
    return Math.min(this.cap(), Math.max(this.floor(), v));
  }

  absorb(delta: number, now: number): void {
    this.recent = now;
    this.energy += delta;
    const span = this.total;
    if (this.energy > span) this.energy = span;
    if (this.energy < -span) this.energy = -span;
  }

  /** Move the scroll target by stored swipe energy, up to the active clamp. */
  release(target: number): number {
    if (this.gate || this.energy === 0) return this.clamp(target);
    const next = this.clamp(target + this.energy);
    this.energy -= next - target;
    if (Math.abs(this.energy) < 0.5) this.energy = 0;
    if (this.energy < 0 && next <= this.floor() + 0.5 && this.active === 0) this.energy = 0;
    if (this.energy > 0 && next >= this.total - 0.5) this.energy = 0;
    return next;
  }

  update(dt: number, pos: number, now: number): { snap: number } | null {
    const seg = this.segments[this.active];
    if (!seg) return null;
    if (!this.sealed && seg.id === "kakoi") {
      const line = seg.start + (seg.end - seg.start) * SEAL_AT;
      const pressed = this.holding || this.energy > 12 || now - this.recent < 480;
      if (pos >= line - 6 && pressed) {
        this.seal = Math.min(1, this.seal + dt / SEAL_SECONDS);
        if (this.seal >= 1) {
          this.sealed = true;
          this.seal = 1;
          try {
            navigator.vibrate?.(18);
          } catch {
            /* no haptics */
          }
        }
      }
    }
    if (this.gate) {
      this.gate.t += dt / this.gate.dur;
      if (this.gate.t >= 1) {
        const to = this.gate.to;
        const dir = this.gate.dir;
        this.gate = null;
        this.active = to;
        const snap = dir < 0 ? this.cap(to) - 12 : this.floor(to);
        return { snap: Math.max(this.floor(to), snap) };
      }
      return null;
    }
    const cap = this.cap();
    const floor = this.floor();
    const forward = pos >= cap - 3 && this.energy >= -1 && this.active < this.segments.length - 1;
    const blocked = seg.id === "kakoi" && !this.sealed && cap < seg.end - 2;
    if (forward && !blocked) {
      const g = GATES[this.active];
      this.gate = { from: this.active, to: this.active + 1, kind: g.kind, dur: g.dur, t: 0, dir: 1 };
      return null;
    }
    if (pos <= floor + 3 && this.energy < -8 && this.active > 0) {
      const g = GATES[this.active - 1];
      this.gate = { from: this.active, to: this.active - 1, kind: g.kind, dur: Math.min(0.7, g.dur), t: 0, dir: -1 };
    }
    return null;
  }

  localT(pos: number): number {
    const seg = this.segments[this.active];
    if (!seg) return 0;
    return clamp01((pos - seg.start) / Math.max(1, seg.end - seg.start));
  }

  seekAct(id: string, t: number): number {
    const raw = id.replace(/^act-/, "");
    if (raw === "colophon") return this.seekAct("return", 1);
    const index = ACTS.indexOf(raw as ActId);
    if (index < 0) return 0;
    this.gate = null;
    this.energy = 0;
    this.active = index;
    if (index > ACTS.indexOf("kakoi") || (raw === "kakoi" && t >= SEAL_AT)) {
      this.sealed = true;
      this.seal = 1;
    }
    const seg = this.segments[index];
    return seg.start + (seg.end - seg.start) * clamp01(t);
  }

  seekProgress(p: number): number {
    const x = clamp01(p) * this.total;
    this.gate = null;
    this.energy = 0;
    let i = 0;
    for (; i < this.segments.length - 1; i++) if (x < this.segments[i].end) break;
    this.active = i;
    const kakoi = ACTS.indexOf("kakoi");
    if (this.active > kakoi) {
      this.sealed = true;
      this.seal = 1;
    }
    return this.clamp(x);
  }

  /** Authored film clock: each act is 1.15s plus its outgoing gate. */
  sampleFilm(u: number): { act: ActId; local: number; gate: Gate | null } {
    const beats: { act: number; dur: number; gate?: { kind: GateKind; dur: number; to: number } }[] = [];
    for (let i = 0; i < ACTS.length; i++) {
      beats.push({ act: i, dur: 1.15 });
      if (i < GATES.length) beats.push({ act: i, dur: GATES[i].dur, gate: { kind: GATES[i].kind, dur: GATES[i].dur, to: i + 1 } });
    }
    const sum = beats.reduce((s, b) => s + b.dur, 0);
    let left = clamp01(u) * sum;
    for (const beat of beats) {
      if (left > beat.dur) {
        left -= beat.dur;
        continue;
      }
      const local = beat.gate ? 1 : beat.dur <= 0 ? 0 : left / beat.dur;
      this.active = beat.act;
      if (beat.act > ACTS.indexOf("kakoi") || (this.act === "kakoi" && local >= SEAL_AT)) {
        this.sealed = true;
        this.seal = 1;
      } else if (this.act === "kakoi") this.seal = clamp01(local / SEAL_AT);
      const seg = this.segments[beat.act];
      this.playhead = seg.start + (seg.end - seg.start) * (beat.gate ? 1 : local);
      if (!beat.gate) {
        this.gate = null;
        return { act: ACTS[beat.act], local, gate: null };
      }
      const gate: Gate = { from: beat.act, to: beat.gate.to, kind: beat.gate.kind, dur: beat.gate.dur, t: left / beat.dur, dir: 1 };
      this.gate = gate;
      return { act: ACTS[beat.act], local: 1, gate };
    }
    this.active = ACTS.length - 1;
    this.gate = null;
    this.playhead = this.total;
    return { act: "return", local: 1, gate: null };
  }
}
