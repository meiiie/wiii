// Adapted from Neko Core, Copyright (c) 2026 Meiiie and Neko Core contributors.
// SPDX-License-Identifier: AGPL-3.0-only
// Neko Bubble v6 source and attribution: docs/research/neko-completion-sound.md.

export function buildNekoCompletionWav(): Uint8Array {
  const rate = 48_000;
  const duration = 0.23;
  const samples = new Float64Array(Math.floor(rate * duration));
  let phase = 0;
  let peak = 0;
  for (let i = 0; i < samples.length; i++) {
    const t = i / rate;
    const attack = Math.sin(Math.min(1, t / 0.016) * Math.PI / 2) ** 2;
    const decay = Math.exp(-Math.max(0, t - 0.012) / 0.055);
    const fade = Math.sin(Math.min(1, (duration - t) / 0.022) * Math.PI / 2) ** 2;
    phase += 2 * Math.PI * (390 + 860 * (1 - Math.exp(-t / 0.060))) / rate;
    samples[i] = attack * decay * fade * (Math.sin(phase + 0.045 * Math.sin(2 * Math.PI * 5 * t))
      + 0.035 * Math.sin(2 * phase + 0.50));
    peak = Math.max(peak, Math.abs(samples[i]));
  }
  const wav = new Uint8Array(44 + samples.length * 4);
  const view = new DataView(wav.buffer);
  const text = (offset: number, value: string) => wav.set(new TextEncoder().encode(value), offset);
  text(0, "RIFF"); view.setUint32(4, wav.length - 8, true); text(8, "WAVE");
  text(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 2, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 4, true); view.setUint16(32, 4, true);
  view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, samples.length * 4, true);
  const gain = peak > 0 ? 0.66 / peak : 1;
  for (let i = 0; i < samples.length; i++) {
    const value = Math.round(Math.max(-1, Math.min(1, samples[i] * gain)) * 32767);
    view.setInt16(44 + i * 4, value, true);
    view.setInt16(46 + i * 4, value, true);
  }
  return wav;
}

export function createCompletionPlayer(createContext: () => AudioContext = () => new AudioContext()) {
  let context: AudioContext | null = null;
  let buffer: Promise<AudioBuffer> | null = null;
  let lastPlay = -Infinity;
  return {
    async prepare(): Promise<boolean> {
      try {
        context ??= createContext();
        await context.resume();
        buffer ??= context.decodeAudioData(buildNekoCompletionWav().buffer as ArrayBuffer);
        await buffer;
        return context.state === "running";
      } catch { buffer = null; return false; }
    },
    async play(): Promise<boolean> {
      if (!context || context.state !== "running" || !buffer) return false;
      try {
        const audioBuffer = await buffer;
        if (!context || context.state !== "running") return false;
        const now = performance.now();
        if (now - lastPlay < 1000) return true;
        const source = context.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(context.destination);
        source.onended = () => source.disconnect();
        source.start();
        lastPlay = now;
        return true;
      } catch { return false; }
    },
    dispose() {
      void context?.close().catch(() => {});
      context = null;
      buffer = null;
      lastPlay = -Infinity;
    },
  };
}

export const completionPlayer = createCompletionPlayer();
