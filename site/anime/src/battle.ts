import type { Sfx } from "./audio";

export type ActName =
  | "awaken"
  | "intrusion"
  | "clash"
  | "observe"
  | "neko"
  | "kakoi"
  | "still"
  | "return";

type Pt = { x: number; y: number };
type Mark = { x: number; y: number; r: number; hit: boolean; rot: number };
type Zone = { x: number; y: number; w: number; h: number };

const CHASE: ActName[] = ["intrusion", "clash", "observe", "neko"];

const ZONES: Partial<Record<ActName, Zone[]>> = {
  intrusion: [
    { x: 0.02, y: 0.05, w: 0.46, h: 0.9 },
    { x: 0.48, y: 0.12, w: 0.22, h: 0.55 },
  ],
  clash: [{ x: 0.42, y: 0.04, w: 0.56, h: 0.78 }],
  observe: [{ x: 0.5, y: 0.08, w: 0.48, h: 0.84 }],
  neko: [{ x: 0.0, y: 0.18, w: 0.42, h: 0.7 }],
  kakoi: [{ x: 0.0, y: 0.12, w: 0.4, h: 0.76 }],
};

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export function mountBattle(sfx: Sfx, onWord: (text: string, x: number, y: number) => void): {
  setAct: (id: ActName, p: number) => void;
  draw: (now: number, vel: number) => void;
} {
  const root = document.documentElement;
  const wash = document.getElementById("wash") as HTMLCanvasElement;
  const ctx = wash.getContext("2d");
  const spark = document.getElementById("spark") as HTMLElement;
  const ghosts = [...document.querySelectorAll<HTMLElement>("#ghosts i")];
  const drift = document.getElementById("drift-cut") as HTMLElement;
  const wiii = document.getElementById("wiii-cut") as HTMLElement;
  const live = document.getElementById("strike-live");
  const tips: Pt[] = [];
  const trail: Pt[] = [];
  const marks = new Map<ActName, Mark[]>();
  let act: ActName = "awaken";
  let progress = 0;
  let pointer: Pt = { x: window.innerWidth * 0.72, y: window.innerHeight * 0.42 };
  let down: Pt | null = null;
  let downAt = 0;
  let combo: number[] = [];
  let lastInput = performance.now();
  let hitUntil = 0;
  let shed: { x: number; y: number; vx: number; vy: number; life: number }[] = [];
  let frozenTips: Pt[] | null = null;
  let trailBucket = -1;

  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
    wash.width = Math.floor(window.innerWidth * dpr);
    wash.height = Math.floor(window.innerHeight * dpr);
    ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener("resize", resize);

  const note = () => {
    lastInput = performance.now();
    root.classList.remove("is-idle");
  };

  const anchor = (): Pt => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    if (act === "clash") return { x: w * 0.78, y: h * 0.42 };
    if (act === "observe") return { x: w * 0.8, y: h * 0.48 };
    if (act === "neko") return { x: w * 0.22, y: h * 0.5 };
    if (act === "kakoi") return { x: w * 0.16, y: h * 0.48 };
    return { x: w * 0.16, y: h * 0.58 };
  };

  const chasing = () => CHASE.includes(act) && !(act === "kakoi");

  const reach = () => {
    if (act === "kakoi" || act === "still" || act === "return" || act === "awaken") return 0;
    if (act === "observe") return 0.72;
    if (act === "neko") return progress < 0.45 ? 0.8 : 0.22;
    if (act === "clash") return 0.55 + progress * 0.25;
    return 0.42 + progress * 0.35;
  };

  const fingerTips = (): Pt[] => {
    if (!chasing() || reach() <= 0.02) return [];
    if (act === "observe" && frozenTips) return frozenTips;
    const a = anchor();
    const r = reach();
    const out: Pt[] = [];
    for (let i = 0; i < 5; i++) {
      const spread = (i - 2) * 28;
      const aim = {
        x: a.x + (pointer.x - a.x) * r + spread,
        y: a.y + (pointer.y - a.y) * r + spread * 0.35,
      };
      out.push(aim);
    }
    if (act === "observe") frozenTips = out.map((p) => ({ ...p }));
    else frozenTips = null;
    return out;
  };

  const hitDrift = (pt: Pt): boolean => {
    const zones = ZONES[act] ?? [];
    const w = window.innerWidth;
    const h = window.innerHeight;
    for (const zone of zones) {
      if (pt.x >= zone.x * w && pt.x <= (zone.x + zone.w) * w && pt.y >= zone.y * h && pt.y <= (zone.y + zone.h) * h) {
        return true;
      }
    }
    if (Number(getComputedStyle(drift).opacity) > 0.25) {
      const rect = drift.getBoundingClientRect();
      if (pt.x >= rect.left && pt.x <= rect.right && pt.y >= rect.top && pt.y <= rect.bottom) return true;
    }
    return tips.some((tip) => Math.hypot(tip.x - pt.x, tip.y - pt.y) < 36);
  };

  const splash = (pt: Pt, hit: boolean, big: boolean) => {
    const list = marks.get(act) ?? [];
    list.push({ x: pt.x, y: pt.y, r: big ? 54 : hit ? 28 : 16, hit, rot: Math.random() * 0.6 - 0.3 });
    if (list.length > 8) list.shift();
    marks.set(act, list);
    if (hit) {
      hitUntil = performance.now() + 220;
      drift.classList.add("is-hit");
      window.setTimeout(() => drift.classList.remove("is-hit"), 220);
      for (let i = 0; i < (big ? 18 : 10); i++) {
        const a = (i / 12) * Math.PI * 2;
        shed.push({
          x: pt.x,
          y: pt.y,
          vx: Math.cos(a) * (2 + (i % 4)),
          vy: Math.sin(a) * (2 + (i % 3)) - 1,
          life: 1,
        });
      }
    }
  };

  const strike = (pt: Pt, dash = false) => {
    const now = performance.now();
    combo = combo.filter((t) => now - t < 680);
    combo.push(now);
    const finisher = combo.length >= 3;
    if (finisher) combo = [];
    const hit = hitDrift(pt);
    splash(pt, hit, finisher || dash);
    root.classList.add("is-tap");
    window.setTimeout(() => root.classList.remove("is-tap"), finisher ? 180 : 90);
    sfx.play(finisher ? "impact" : hit ? "slash" : "tick");
    if (finisher) onWord("ズバッ", pt.x, pt.y);
    else if (hit) onWord("トンッ", pt.x, pt.y);
    if (live) live.textContent = hit ? (finisher ? "Finisher. Drift recoils." : "Hit. Drift recoils.") : "Miss. The ink stays.";
  };

  const onDown = (event: PointerEvent) => {
    const target = event.target as Element | null;
    if (target?.closest("a, button")) return;
    note();
    down = { x: event.clientX, y: event.clientY };
    downAt = performance.now();
    root.classList.add("is-wind");
  };

  const onUp = (event: PointerEvent) => {
    if (!down) return;
    const start = down;
    const held = performance.now() - downAt;
    const end = { x: event.clientX, y: event.clientY };
    down = null;
    const dist = Math.hypot(end.x - start.x, end.y - start.y);
    const dash = held > 280 && dist > 36;
    const wait = Math.max(0, 80 - held);
    window.setTimeout(() => {
      root.classList.remove("is-wind");
      root.classList.remove("is-charge");
      spark.style.scale = "1";
      if (dash) {
        const steps = 4;
        for (let i = 1; i <= steps; i++) {
          const t = i / steps;
          if (hitDrift({ x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t })) {
            strike(end, true);
            return;
          }
        }
        strike(end, true);
        return;
      }
      strike(end, false);
    }, wait);
  };

  window.addEventListener("pointerdown", onDown);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointermove", (event) => {
    pointer = { x: event.clientX, y: event.clientY };
    note();
    if (down && performance.now() - downAt > 180) {
      const k = clamp((performance.now() - downAt) / 700, 0, 1);
      spark.style.scale = String(1 + k * 0.9);
      root.classList.toggle("is-charge", k > 0.25);
    }
  });
  window.addEventListener("wheel", note, { passive: true });
  window.addEventListener("keydown", note);

  const drawFingers = (pts: Pt[]) => {
    if (!ctx) return;
    const a = anchor();
    ctx.lineCap = "round";
    pts.forEach((tip, i) => {
      const wobble = act === "observe" ? 0 : Math.sin(performance.now() / 180 + i) * 6;
      ctx.strokeStyle = "rgba(11,11,13,0.85)";
      ctx.lineWidth = 7;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo((a.x + tip.x) / 2 + wobble, (a.y + tip.y) / 2 - 40, tip.x, tip.y);
      ctx.stroke();
      ctx.strokeStyle = "#2A2928";
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.fillStyle = "#E0261F";
      ctx.fillRect(tip.x - 3, tip.y - 16, 7, 22);
      ctx.fillStyle = "rgba(224,38,31,0.35)";
      ctx.fillRect(tip.x + 6, tip.y - 10, 4, 14);
    });
  };

  const drawMarks = () => {
    if (!ctx) return;
    const list = marks.get(act) ?? [];
    for (const mark of list) {
      const g = ctx.createRadialGradient(mark.x, mark.y, 2, mark.x, mark.y, mark.r);
      g.addColorStop(0, mark.hit ? "rgba(224,38,31,0.85)" : "rgba(243,238,227,0.9)");
      g.addColorStop(0.45, mark.hit ? "rgba(224,38,31,0.25)" : "rgba(243,238,227,0.28)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(mark.x, mark.y, mark.r, mark.r * 0.72, mark.rot, 0, Math.PI * 2);
      ctx.fill();
      if (mark.hit) {
        ctx.strokeStyle = "rgba(224,38,31,0.8)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(mark.x - mark.r * 0.4, mark.y);
        ctx.lineTo(mark.x + mark.r * 0.7, mark.y - mark.r * 0.5);
        ctx.stroke();
      }
    }
  };

  const drawShed = () => {
    if (!ctx) return;
    shed = shed.filter((bit) => bit.life > 0);
    for (const bit of shed) {
      bit.x += bit.vx * 3;
      bit.y += bit.vy * 3;
      bit.vy += 0.18;
      bit.life -= 0.06;
      ctx.globalAlpha = Math.max(0, bit.life);
      ctx.fillStyle = bit.life > 0.5 ? "#E0261F" : "#F3EEE3";
      ctx.fillRect(bit.x, bit.y, 4, 3);
    }
    ctx.globalAlpha = 1;
  };

  const drawSpeed = (vel: number) => {
    if (!ctx || vel < 0.12) return;
    const n = Math.floor(8 + vel * 18);
    ctx.strokeStyle = `rgba(243,238,227,${0.15 + vel * 0.35})`;
    for (let i = 0; i < n; i++) {
      const y = ((i * 97) % window.innerHeight);
      const len = 40 + vel * 220;
      ctx.lineWidth = i % 4 === 0 ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo((i * 130) % window.innerWidth, y);
      ctx.lineTo(((i * 130) % window.innerWidth) + len, y + (i % 2 ? 2 : -2));
      ctx.stroke();
    }
  };

  const drawSpecks = (now: number) => {
    if (!ctx || act !== "still") return;
    const t = now / 1000;
    for (let i = 0; i < 9; i++) {
      const x = (0.08 + ((i * 0.17) % 0.84)) * window.innerWidth;
      const y = ((0.12 + ((i * 0.23) % 0.76) + t * 0.004) % 1) * window.innerHeight;
      const r = 8 + (i % 4) * 7;
      const g = ctx.createRadialGradient(x, y, 1, x, y, r);
      g.addColorStop(0, "rgba(11,11,13,0.72)");
      g.addColorStop(1, "rgba(11,11,13,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      if (i % 3 === 0) {
        ctx.strokeStyle = "rgba(11,11,13,0.45)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.quadraticCurveTo(x + r, y - r * 0.2, x + r * 2.1, y + r);
        ctx.stroke();
      }
    }
  };

  return {
    setAct(id, p) {
      if (id !== act) frozenTips = null;
      act = id;
      progress = p;
      const freed = id === "kakoi" || id === "still" || id === "return";
      root.classList.toggle("is-freed", freed);
      wiii.style.opacity = id === "clash" && p < 0.34 ? "1" : id === "return" && p > 0.55 ? "0.9" : "0";
      drift.style.opacity = id === "intrusion" ? "1" : id === "clash" && p < 0.28 ? "0.9" : id === "neko" && p < 0.55 ? "0.75" : "0";
      if (id === "clash" && p < 0.34) {
        wiii.style.transform = `translate(${-18 + p * 90}vw, 8vh)`;
      } else if (id === "return") {
        wiii.style.transform = "translate(34vw, 18vh) scale(0.72)";
      }
      if (id === "intrusion") drift.style.transform = "translate(-4vw, 4vh)";
      else if (id === "neko") drift.style.transform = `translate(${-8 - p * 20}vw, 6vh) rotate(${-6 - p * 8}deg)`;
      else drift.style.transform = "translate(48vw, 0)";
    },
    draw(now, vel) {
      if (now - lastInput > 5000) root.classList.add("is-idle");
      tips.length = 0;
      const pts = fingerTips();
      for (const pt of pts) tips.push(pt);
      if (ctx) {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        drawSpeed(vel);
        drawFingers(pts);
        drawMarks();
        drawShed();
        drawSpecks(now);
      }
      const bucket = Math.floor(now / (chasing() ? 80 : 32));
      if (bucket !== trailBucket) {
        trailBucket = bucket;
        trail.unshift({ ...pointer });
        if (trail.length > 8) trail.pop();
      }
      const sparkPt = trail[0] ?? pointer;
      spark.style.transform = `translate(${sparkPt.x}px, ${sparkPt.y}px)`;
      const freed = root.classList.contains("is-freed");
      ghosts.forEach((ghost, i) => {
        const src = trail[Math.min(trail.length - 1, 2 + i * 2)] ?? sparkPt;
        if (freed) {
          ghost.style.opacity = "0";
          ghost.style.transform = `translate(${src.x + (i - 1) * 80}px, ${src.y - 40}px) rotate(${20 * (i - 1)}deg)`;
          return;
        }
        ghost.style.opacity = chasing() ? String(0.55 - i * 0.12) : "0";
        ghost.style.transform = `translate(${src.x + 10}px, ${src.y + 8}px)`;
      });
      if (performance.now() < hitUntil) drift.classList.add("is-hit");
    },
  };
}
