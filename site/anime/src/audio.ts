type Kind = "spark" | "flight" | "wrap" | "impact" | "slash" | "open" | "tick" | "quiet" | "whoosh" | "sub";

export class Sfx {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  enabled = false;
  private bedAct = "";
  private bedStop: (() => void) | null = null;
  private windFilter: BiquadFilterNode | null = null;
  private windGain: GainNode | null = null;
  private windSrc: AudioBufferSourceNode | null = null;
  private ready: Promise<void> | null = null;

  /** Resume the context on a user gesture so a later unmute works on iOS. */
  unlock(): void {
    void this.ensure().then(async () => {
      if (this.ctx && this.ctx.state === "suspended") await this.ctx.resume();
    });
  }

  async toggle(): Promise<boolean> {
    await this.ensure();
    if (this.ctx && this.ctx.state === "suspended") await this.ctx.resume();
    this.enabled = !this.enabled;
    if (!this.enabled) {
      this.bed(null);
      this.stopWind();
    }
    if (this.enabled) this.play("tick");
    return this.enabled;
  }

  private ensure(): Promise<void> {
    if (!this.ready) this.ready = this.build();
    return this.ready;
  }

  private async build(): Promise<void> {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.32;
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -16;
    comp.knee.value = 8;
    comp.ratio.value = 3;
    comp.attack.value = 0.003;
    comp.release.value = 0.12;
    this.master.connect(comp);
    comp.connect(this.ctx.destination);
    const length = this.ctx.sampleRate * 2;
    const buffer = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
    this.noise = buffer;
  }

  /** Filtered noise whose cutoff and gain follow the wind field. Silent while muted. */
  wind(strength: number, ember = false): void {
    if (!this.enabled || !this.ctx || !this.master || !this.noise) {
      this.stopWind();
      return;
    }
    if (!this.windSrc) {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noise;
      src.loop = true;
      const filter = this.ctx.createBiquadFilter();
      filter.type = "lowpass";
      const gain = this.ctx.createGain();
      gain.gain.value = 0.0001;
      src.connect(filter);
      filter.connect(gain);
      gain.connect(this.master);
      src.start();
      this.windSrc = src;
      this.windFilter = filter;
      this.windGain = gain;
    }
    const now = this.ctx.currentTime;
    const cutoff = ember ? 700 + strength * 1600 : 140 + strength * 980;
    const level = Math.min(0.07, (ember ? 0.015 : 0.006) + strength * 0.05);
    this.windFilter?.frequency.setTargetAtTime(Math.max(40, cutoff), now, 0.08);
    this.windGain?.gain.setTargetAtTime(Math.max(0.0001, level), now, 0.08);
  }

  /** The silence is the hit. Restores the master a moment later. */
  silence(seconds = 0.25): void {
    if (!this.ctx || !this.master) return;
    const now = this.ctx.currentTime;
    const back = this.enabled ? 0.32 : 0.0001;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(Math.max(0.0001, this.master.gain.value), now);
    this.master.gain.linearRampToValueAtTime(0.0001, now + 0.02);
    this.master.gain.setValueAtTime(0.0001, now + seconds);
    this.master.gain.linearRampToValueAtTime(back, now + seconds + 0.06);
  }

  crystal(): void {
    this.tone(2400, 0.045, 0.035, "sine");
  }

  crackle(): void {
    this.burst(480, 1.1, 0.04, 0.05);
  }

  private stopWind(): void {
    try {
      this.windSrc?.stop();
    } catch {
      /* already stopped */
    }
    this.windSrc?.disconnect();
    this.windFilter?.disconnect();
    this.windGain?.disconnect();
    this.windSrc = null;
    this.windFilter = null;
    this.windGain = null;
  }

  /** Quiet loop that changes with the act. No-ops when the act is unchanged. */
  bed(act: string | null): void {
    if (!this.enabled || !act || !this.ctx || !this.master || !this.noise) {
      this.stopBed();
      return;
    }
    if (act === this.bedAct && this.bedStop) return;
    this.stopBed();
    const freqs: Record<string, number> = {
      awaken: 196,
      intrusion: 98,
      clash: 146,
      observe: 262,
      neko: 330,
      kakoi: 52,
      still: 174,
      return: 146,
    };
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const filter = this.ctx.createBiquadFilter();
    filter.type = act === "kakoi" ? "lowpass" : "bandpass";
    filter.frequency.value = freqs[act] ?? 180;
    filter.Q.value = act === "kakoi" ? 0.65 : 0.55;
    const gain = this.ctx.createGain();
    const now = this.ctx.currentTime;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(act === "kakoi" ? 0.055 : 0.026, now + 0.18);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(this.master);
    src.start();
    this.bedAct = act;
    this.bedStop = () => {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
      src.disconnect();
      filter.disconnect();
      gain.disconnect();
    };
  }

  private stopBed(): void {
    this.bedStop?.();
    this.bedStop = null;
    this.bedAct = "";
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
    if (kind === "flight" || kind === "whoosh") {
      this.sweep(kind === "whoosh" ? 220 : 500, kind === "whoosh" ? 1600 : 1800, kind === "whoosh" ? 0.22 : 0.35, kind === "whoosh" ? 0.11 : 0.07);
      return;
    }
    if (kind === "sub") {
      this.drop();
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
    osc.frequency.value = freq * (0.94 + Math.random() * 0.12);
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

  private drop(): void {
    if (!this.ctx || !this.master) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = "sine";
    const now = this.ctx.currentTime;
    osc.frequency.setValueAtTime(72, now);
    osc.frequency.exponentialRampToValueAtTime(32, now + 0.62);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.5, now + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.15);
    osc.connect(gain);
    gain.connect(this.master);
    osc.start(now);
    osc.stop(now + 1.2);
    this.burst(80, 0.55, 0.18, 0.2);
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
