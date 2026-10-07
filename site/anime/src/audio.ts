type Kind = "spark" | "flight" | "wrap" | "impact" | "slash" | "open" | "tick" | "quiet";

export class Sfx {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  enabled = false;

  async toggle(): Promise<boolean> {
    if (!this.ctx) {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new Ctx();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.35;
      this.master.connect(this.ctx.destination);
      const length = this.ctx.sampleRate * 2;
      const buffer = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
      this.noise = buffer;
    }
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.enabled = !this.enabled;
    if (this.enabled) this.play("tick");
    return this.enabled;
  }

  play(kind: Kind): void {
    if (!this.enabled || !this.ctx || !this.master || !this.noise) return;
    if (kind === "impact") {
      this.tone(78, 0.28, 0.28, "sine");
      this.burst(180, 0.9, 0.22, 0.09);
      return;
    }
    if (kind === "slash") {
      this.burst(900, 0.4, 0.12, 0.12);
      this.tone(240, 0.12, 0.08, "triangle");
      return;
    }
    if (kind === "open") {
      this.burst(200, 0.25, 0.16, 0.45);
      this.tone(140, 0.4, 0.08, "sine");
      return;
    }
    if (kind === "flight") {
      this.sweep(500, 1800, 0.35, 0.07);
      return;
    }
    if (kind === "wrap") {
      this.tone(320, 0.22, 0.06, "sine");
      this.sweep(700, 180, 0.28, 0.05);
      return;
    }
    if (kind === "spark" || kind === "tick") {
      this.tone(kind === "spark" ? 1680 : 880, 0.07, 0.05, "sine");
      return;
    }
    if (kind === "quiet") {
      this.tone(220, 0.18, 0.03, "sine");
      return;
    }
  }

  private tone(freq: number, dur: number, peak: number, type: OscillatorType): void {
    if (!this.ctx || !this.master) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    const now = this.ctx.currentTime;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(peak, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    osc.connect(gain);
    gain.connect(this.master);
    osc.start(now);
    osc.stop(now + dur + 0.02);
  }

  private burst(freq: number, q: number, peak: number, dur: number): void {
    if (!this.ctx || !this.master || !this.noise) return;
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const filter = this.ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = freq;
    filter.Q.value = q;
    const gain = this.ctx.createGain();
    const now = this.ctx.currentTime;
    gain.gain.setValueAtTime(peak, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(this.master);
    src.start(now);
    src.stop(now + dur);
  }

  private sweep(from: number, to: number, dur: number, peak: number): void {
    if (!this.ctx || !this.master || !this.noise) return;
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const filter = this.ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.Q.value = 0.7;
    const now = this.ctx.currentTime;
    filter.frequency.setValueAtTime(from, now);
    filter.frequency.exponentialRampToValueAtTime(Math.max(40, to), now + dur);
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(peak, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(this.master);
    src.start(now);
    src.stop(now + dur);
  }
}
