import type { Sfx } from "./audio";
import { viewSize, weatherGust, weatherPuff, weatherRibbon } from "./weather";

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
  recoil: () => void;
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
  const armsRoot = document.getElementById("drift-arms") as HTMLElement;
  const ARMS = [
    { src: "/art/drift-arm-0.webp", w: 244, h: 387, ox: 0.8156, oy: 0.1189, rest: 2.0156 },
    { src: "/art/drift-arm-1.webp", w: 291, h: 520, ox: 0.8454, oy: 0.0865, rest: 1.9812 },
    { src: "/art/drift-arm-2.webp", w: 320, h: 498, ox: 0.1406, oy: 0.0924, rest: 1.0808 },
    { src: "/art/drift-arm-3.webp", w: 252, h: 583, ox: 0.1667, oy: 0.0755, rest: 1.2634 },
    { src: "/art/drift-arm-4.webp", w: 349, h: 365, ox: 0.1347, oy: 0.1288, rest: 0.7563 },
  ];
  const face = document.getElementById("drift-face") as HTMLElement;
  const eye = document.getElementById("drift-eye") as HTMLElement;
  let maskHits = 0;
  type Box = { l: number; t: number; r: number; b: number };
  let boxes: Box[] = [];
  const armEls = ARMS.map((arm) => {
    const img = document.createElement("img");
    img.src = arm.src;
    img.srcset = `${arm.src} 1x, ${arm.src.replace(".webp", "-2x.webp")} 2x, ${arm.src.replace(".webp", "-3x.webp")} 3x`;
    img.alt = "";
    img.width = arm.w;
    img.height = arm.h;
    armsRoot.appendChild(img);
    return img;
  });
  let frozenAngles: number[] | null = null;
  let finisherUntil = 0;
  const tips: Pt[] = [];
  const trail: Pt[] = [];
  const marks = new Map<ActName, Mark[]>();
  let act: ActName = "awaken";
  let progress = 0;
  let pointer: Pt = { x: viewSize().w * 0.72, y: viewSize().h * 0.42 };
  let aimPointer: Pt = { ...pointer };
  let poseTick = -1;
  const holdPose = (now: number) => {
    const tick = Math.floor(now / 83);
    if (tick === poseTick) return false;
    poseTick = tick;
    aimPointer = { ...pointer };
    return true;
  };
  let down: Pt | null = null;
  let downAt = 0;
  let combo: number[] = [];
  let lastInput = performance.now();
  let hitUntil = 0;
  let shed: { x: number; y: number; vx: number; vy: number; life: number; s: number }[] = [];
  let frozenTips: Pt[] | null = null;
  let trailBucket = -1;

  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    wash.width = Math.floor(viewSize().w * dpr);
    wash.height = Math.floor(viewSize().h * dpr);
    ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener("resize", resize);

  const note = () => {
    lastInput = performance.now();
    root.classList.remove("is-idle");
  };

  const anchor = (): Pt => {
    const w = viewSize().w;
    const h = viewSize().h;
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
    const w = viewSize().w;
    const h = viewSize().h;
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
    list.push({ x: pt.x, y: pt.y, r: big ? 64 : hit ? 40 : 30, hit, rot: Math.random() * 0.4 - 0.2 });
    if (list.length > 8) list.shift();
    marks.set(act, list);
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * Math.PI * 2 + 0.4;
      shed.push({
        x: pt.x + Math.cos(a) * 8,
        y: pt.y + Math.sin(a) * 6,
        vx: Math.cos(a) * (0.8 + (i % 3) * 0.45),
        vy: Math.sin(a) * 0.7 - 0.55,
        life: 0.9,
        s: 6 + (i % 3) * 3,
      });
    }
    if (hit) {
      hitUntil = performance.now() + 380;
      drift.classList.remove("is-hit");
      void drift.offsetWidth;
      drift.classList.add("is-hit");
      for (let i = 0; i < (big ? 18 : 10); i++) {
        const a = (i / 12) * Math.PI * 2;
        shed.push({
          x: pt.x,
          y: pt.y,
          vx: Math.cos(a) * (2 + (i % 4)),
          vy: Math.sin(a) * (2 + (i % 3)) - 1,
          life: 1,
          s: 4,
        });
      }
    }
  };

  let hintOnce = false;
  const tickHint = () => {
    if (hintOnce) return;
    hintOnce = true;
    const how = document.querySelector(".how");
    if (!how) return;
    how.classList.add("is-ticked", "is-ticking");
    window.setTimeout(() => how.classList.remove("is-ticking"), 200);
  };

  const strike = (pt: Pt, dash = false, vx = 0, vy = 0) => {
    window.__WIII && (window.__WIII.strikes += 1);
    const now = performance.now();
    const hit = hitDrift(pt);
    weatherGust(pt.x, pt.y, vx, vy);
    const mask = onMask(pt);
    if (mask) {
      maskHits = Math.min(5, maskHits + 1);
      face.dataset.crack = String(maskHits);
      face.classList.toggle("is-across", maskHits >= 5);
      face.classList.remove("is-crack");
      void face.offsetWidth;
      face.classList.add("is-crack");
    }
    if (now < finisherUntil && !mask) {
      splash(pt, hit, true);
      onWord("ズバッ", pt.x, pt.y);
      return;
    }
    combo = combo.filter((t) => now - t < 680);
    combo.push(now);
    const finisher = combo.length >= 3 && !mask;
    if (finisher) {
      combo = [];
      finisherUntil = now + 760;
    }
    splash(pt, hit || mask, finisher || dash || mask);
    root.classList.add("is-tap");
    window.setTimeout(() => root.classList.remove("is-tap"), finisher ? 180 : 90);
    const sound = dash ? (hit || mask ? "slash" : "whoosh") : finisher || maskHits >= 5 ? "impact" : hit || mask ? "slash" : "tick";
    sfx.play(sound);
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && /Android/i.test(navigator.userAgent)) {
      navigator.vibrate?.(hit || mask ? [10, 24, 16] : 8);
    }
    if (mask && maskHits >= 5) onWord("囲", pt.x, pt.y);
    else if (finisher || mask) onWord("ズバッ", pt.x, pt.y);
    else if (hit) onWord("トンッ", pt.x, pt.y);
    else onWord("ピタッ", pt.x, pt.y);
    if (live) {
      live.textContent = mask && maskHits >= 5
        ? "The crack reaches across."
        : mask
          ? "The mask cracks."
          : hit
            ? (finisher ? "Finisher. Drift recoils." : "Hit. Drift recoils.")
            : "The ink stays.";
    }
  };

  const onMask = (pt: Pt): boolean => {
    if (Number(drift.style.opacity) < 0.2) return false;
    const rect = drift.getBoundingClientRect();
    const head = { l: rect.left + rect.width * 0.34, t: rect.top + rect.height * 0.05, r: rect.left + rect.width * 0.62, b: rect.top + rect.height * 0.22 };
    return pt.x >= head.l && pt.x <= head.r && pt.y >= head.t && pt.y <= head.b;
  };

  let scrollAtDown = 0;
  let gesture = 0;
  let touchArmed = false;
  const touchLike = (event: PointerEvent) => event.pointerType === "touch" || event.pointerType === "pen";
  const releaseCharge = () => {
    gesture += 1;
    down = null;
    touchArmed = false;
    root.classList.remove("is-wind");
    root.classList.remove("is-charge");
    spark.style.scale = "1";
  };
  const onDown = (event: PointerEvent) => {
    const target = event.target as Element | null;
    if (target?.closest("a, button")) return;
    note();
    sfx.unlock();
    down = { x: event.clientX, y: event.clientY };
    downAt = performance.now();
    scrollAtDown = window.scrollY;
    touchArmed = false;
    if (!touchLike(event)) root.classList.add("is-wind");
  };

  const onUp = (event: PointerEvent) => {
    if (!down) return;
    const start = down;
    const held = performance.now() - downAt;
    const end = { x: event.clientX, y: event.clientY };
    const dist = Math.hypot(end.x - start.x, end.y - start.y);
    const scrolled = Math.abs(window.scrollY - scrollAtDown) > 10;
    const touch = touchLike(event);
    const armed = touchArmed;
    releaseCharge();
    if (touch) {
      const tap = dist < 10 && held < 250 && !scrolled;
      const dash = armed && dist >= 10 && !scrolled;
      if (!tap && !dash) return;
      if (tap) {
        weatherPuff(end.x, end.y);
        tickHint();
      }
      const vx = end.x - start.x;
      const vy = end.y - start.y;
      if (dash) {
        strike(end, true, vx, vy);
        return;
      }
      strike(end, false, vx, vy);
      return;
    }
    const dash = held > 280 && dist > 36;
    if (!dash && dist < 10 && held < 250) tickHint();
    const token = gesture;
    const wait = Math.max(0, 80 - held);
    window.setTimeout(() => {
      if (token !== gesture) return;
      const vx = end.x - start.x;
      const vy = end.y - start.y;
      if (dash) {
        const steps = 4;
        for (let i = 1; i <= steps; i++) {
          const t = i / steps;
          if (hitDrift({ x: start.x + vx * t, y: start.y + vy * t })) {
            strike(end, true, vx, vy);
            return;
          }
        }
        strike(end, true, vx, vy);
        return;
      }
      strike(end, false, vx, vy);
    }, wait);
  };

  window.addEventListener("pointerdown", onDown);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", releaseCharge);
  window.addEventListener("lostpointercapture", () => {
    if (down) releaseCharge();
  });
  window.addEventListener("scroll", () => {
    if (down && Math.abs(window.scrollY - scrollAtDown) > 10) releaseCharge();
  }, { passive: true });
  window.addEventListener("pointermove", (event) => {
    pointer = { x: event.clientX, y: event.clientY };
    note();
    if (!down) return;
    const dist = Math.hypot(event.clientX - down.x, event.clientY - down.y);
    const held = performance.now() - downAt;
    if (touchLike(event)) {
      if (!touchArmed) {
        if (dist > 10 || Math.abs(window.scrollY - scrollAtDown) > 10) {
          releaseCharge();
          return;
        }
        if (held > 450) {
          touchArmed = true;
          root.classList.add("is-wind");
        }
        return;
      }
      const k = clamp((held - 450) / 500, 0, 1);
      spark.style.scale = String(1 + k * 0.9);
      root.classList.toggle("is-charge", k > 0.25);
      return;
    }
    if (held > 180) {
      const k = clamp(held / 700, 0, 1);
      spark.style.scale = String(1 + k * 0.9);
      root.classList.toggle("is-charge", k > 0.25);
    }
  });
  window.addEventListener("wheel", note, { passive: true });
  window.addEventListener("keydown", note);

  const collectBoxes = () => {
    boxes = [...document.querySelectorAll<HTMLElement>(".plate, .panel.is-in, .rule.is-now, .rule.is-debris, .ono, .tate")]
      .filter((el) => {
        if (el.hidden) return false;
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) < 0.2) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 12 && rect.height > 12;
      })
      .map((el) => {
        const rect = el.getBoundingClientRect();
        return { l: rect.left - 18, t: rect.top - 14, r: rect.right + 18, b: rect.bottom + 14 };
      });
  };
  const blocked = (x: number, y: number) => boxes.some((box) => x >= box.l && x <= box.r && y >= box.t && y <= box.b);
  const dodge = (from: Pt, to: Pt): Pt => {
    let aim = to;
    for (const box of boxes) {
      const inside = aim.x >= box.l && aim.x <= box.r && aim.y >= box.t && aim.y <= box.b;
      if (!inside && !segmentHits(from, aim, box)) continue;
      const pad = 36;
      const corners = [
        { x: box.l - pad, y: box.t - pad },
        { x: box.r + pad, y: box.t - pad },
        { x: box.l - pad, y: box.b + pad },
        { x: box.r + pad, y: box.b + pad },
      ];
      let best = corners[0];
      let bestD = Infinity;
      for (const corner of corners) {
        if (segmentHits(from, corner, box)) continue;
        const dist = Math.hypot(corner.x - to.x, corner.y - to.y);
        if (dist < bestD) {
          bestD = dist;
          best = corner;
        }
      }
      aim = bestD < Infinity ? best : { x: from.x + (box.l - from.x) * 0.92, y: from.y + (box.t - from.y) * 0.92 };
    }
    return aim;
  };
  const segmentHits = (from: Pt, to: Pt, box: Box) => {
    const steps = 6;
    for (let i = 1; i <= steps; i++) {
      const x = from.x + (to.x - from.x) * (i / steps);
      const y = from.y + (to.y - from.y) * (i / steps);
      if (x >= box.l && x <= box.r && y >= box.t && y <= box.b) return true;
    }
    return false;
  };

  // Rotation changes the axis-aligned box. Size from the layout box, then
  // map a local point through the linear part of the transform.
  const placedOn = (el: HTMLElement, fx: number, fy: number) => {
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const raw = getComputedStyle(el).transform;
    const m = new DOMMatrix(raw === "none" ? undefined : raw);
    const linear = new DOMMatrix([m.a, m.b, m.c, m.d, 0, 0]);
    const p = new DOMPoint(fx * w - w / 2, fy * h - h / 2).matrixTransform(linear);
    return { x: cx + p.x, y: cy + p.y, w, h };
  };

  const placeArms = () => {
    const layout = placedOn(drift, 318 / 640, 250 / 871);
    const show = chasing() && Number(drift.style.opacity) > 0.2 && layout.w > 8;
    drift.classList.toggle("is-armed", show);
    const sx = layout.x;
    const sy = layout.y;
      const aim = dodge({ x: sx, y: sy }, aimPointer);
    if (act !== "observe") frozenAngles = null;
    armEls.forEach((img, i) => {
      const arm = ARMS[i];
      if (!show) {
        img.style.opacity = "0";
        return;
      }
      const aw = (arm.w / 640) * layout.w;
      const ah = (arm.h / 871) * layout.h;
      let ang = Math.atan2(aim.y - sy, aim.x - sx) - arm.rest;
      if (act === "observe") {
        if (!frozenAngles) frozenAngles = [];
        if (frozenAngles[i] == null) frozenAngles[i] = ang;
        ang = frozenAngles[i];
      }
      img.style.opacity = "1";
      img.style.width = `${aw}px`;
      img.style.height = `${ah}px`;
      img.style.left = `${sx}px`;
      img.style.top = `${sy}px`;
      img.style.transformOrigin = `${arm.ox * aw}px ${arm.oy * ah}px`;
      img.style.transform = `translate(${-arm.ox * aw}px, ${-arm.oy * ah}px) rotate(${ang}rad)`;
    });
  };

  const placeFace = () => {
    const sealed = root.classList.contains("is-sealed");
    const origin = placedOn(drift, 0.36, 0.055);
    const across = placedOn(drift, 0.6, 0.055);
    const on = !sealed && Number(drift.style.opacity) > 0.2 && origin.w > 8;
    face.classList.toggle("is-on", on);
    if (!on) {
      face.classList.remove("is-look");
      face.style.transform = "";
      return;
    }
    const maskW = origin.w * 0.24;
    const maskH = origin.h * 0.15;
    const ang = Math.atan2(across.y - origin.y, across.x - origin.x);
    face.style.left = `${origin.x}px`;
    face.style.top = `${origin.y}px`;
    face.style.width = `${maskW}px`;
    face.style.height = `${maskH}px`;
    face.style.transformOrigin = "0 0";
    face.style.transform = `rotate(${ang}rad)`;
    const rect = drift.getBoundingClientRect();
    const hover = aimPointer.x >= rect.left && aimPointer.x <= rect.right && aimPointer.y >= rect.top && aimPointer.y <= rect.bottom;
    face.classList.toggle("is-look", hover);
    const ex = hover ? clamp((aimPointer.x - (rect.left + rect.width * 0.46)) / (rect.width * 0.45), -1, 1) : 0;
    const ey = hover ? clamp((aimPointer.y - (rect.top + rect.height * 0.1)) / (rect.height * 0.22), -1, 1) : 0;
    const pupil = eye.firstElementChild as HTMLElement | null;
    if (pupil) pupil.style.transform = `translate(calc(-50% + ${ex * 3.5}px), calc(-50% + ${ey * 2.5}px))`;
    eye.style.left = `${((0.438 - 0.36) / 0.24) * maskW}px`;
    eye.style.top = `${((0.094 - 0.055) / 0.15) * maskH}px`;
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
      ctx.lineCap = "round";
      ctx.lineWidth = mark.hit ? 5 : 4;
      ctx.strokeStyle = mark.hit ? "rgba(224,38,31,0.95)" : "rgba(243,238,227,0.95)";
      ctx.beginPath();
      ctx.moveTo(mark.x - mark.r * 0.9, mark.y + mark.r * 0.15);
      ctx.lineTo(mark.x + mark.r, mark.y - mark.r * 0.4);
      ctx.stroke();
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
      ctx.fillRect(bit.x, bit.y, bit.s, Math.max(2, bit.s - 2));
    }
    ctx.globalAlpha = 1;
  };

  const drawSpeed = (vel: number) => {
    if (!ctx || vel < 0.12) return;
    const n = Math.floor(8 + vel * 18);
    ctx.strokeStyle = `rgba(243,238,227,${0.15 + vel * 0.35})`;
    for (let i = 0; i < n; i++) {
      const y = ((i * 97) % viewSize().h);
      const len = 40 + vel * 220;
      ctx.lineWidth = i % 4 === 0 ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo((i * 130) % viewSize().w, y);
      ctx.lineTo(((i * 130) % viewSize().w) + len, y + (i % 2 ? 2 : -2));
      ctx.stroke();
    }
  };

  const drawLife = (now: number) => {
    if (!ctx || act === "observe") return;
    const t = now / 1000;
    const w = viewSize().w;
    const h = viewSize().h;
    if (act === "kakoi" && progress >= 0.26) return;
    if (act === "still" || act === "return") return;
    if (act === "kakoi" && progress >= 0.08) {
      for (let i = 0; i < 26; i++) {
        const x = (0.12 + ((i * 0.137) % 0.76)) * w + Math.sin(t * 0.55 + i) * 7;
        const y = (0.1 + ((i * 0.173) % 0.72)) * h + Math.cos(t * 0.42 + i * 1.3) * 6;
        if (blocked(x, y)) continue;
        ctx.globalAlpha = 0.28 + (i % 4) * 0.1;
        ctx.fillStyle = i % 3 === 0 ? "#E0261F" : progress < 0.24 ? "#F3EEE3" : "#2A2928";
        ctx.fillRect(x, y, 3 + (i % 3), 2 + (i % 2));
      }
      ctx.globalAlpha = 1;
      return;
    }
    const n = act === "intrusion" ? 18 : 9;
    for (let i = 0; i < n; i++) {
      const driftX = act === "intrusion" ? t * 0.03 : t * 0.012;
      const x = ((0.06 + i * 0.11 + driftX) % 1) * w;
      const y = ((0.15 + ((i * 0.19) % 0.7) + Math.sin(t * 0.35 + i) * 0.03) % 1) * h;
      if (blocked(x, y)) continue;
      const r = 10 + (i % 5) * 8;
      const g = ctx.createRadialGradient(x, y, 1, x, y, r);
      const tone = act === "intrusion" ? "224,38,31" : "243,238,227";
      g.addColorStop(0, `rgba(${tone},0.28)`);
      g.addColorStop(1, `rgba(${tone},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    if (act === "intrusion") {
      for (let i = 0; i < 10; i++) {
        const x = (0.55 + ((i * 0.07 + t * 0.04) % 0.4)) * w;
        const y = (0.2 + ((i * 0.13) % 0.55)) * h + Math.sin(t * 3 + i) * 4;
        if (blocked(x, y)) continue;
        ctx.globalAlpha = 0.35 + (Math.sin(t * 6 + i) > 0 ? 0.4 : 0);
        ctx.fillStyle = i % 2 ? "#E0261F" : "#F3EEE3";
        ctx.fillRect(x, y, 4, 3);
      }
      ctx.globalAlpha = 1;
    }
  };

  return {
    setAct(id, p) {
      if (id !== act) {
        frozenTips = null;
        poseTick = -1;
      }
      act = id;
      progress = p;
      const freed = id === "kakoi" || id === "still" || id === "return";
      const sealed = id === "still" || id === "return" || (id === "kakoi" && p >= 0.26);
      root.classList.toggle("is-freed", freed);
      root.classList.toggle("is-sealed", sealed);
      const ringLock = id === "kakoi" && p >= 0.06 && p < 0.26;
      const scarf = id === "kakoi" && p < 0.26;
      wiii.style.opacity = id === "clash" && p < 0.3 ? "1" : scarf ? "1" : "0";
      const phone = viewSize().w <= 800;
      const crush = id === "kakoi" && p < 0.26 && phone;
      drift.classList.toggle("is-frozen", ringLock && !crush);
      drift.style.opacity = sealed ? "0" : id === "intrusion" ? "1" : id === "clash" && p < 0.3 ? "0.92" : id === "neko" && p < 0.42 ? "0.85" : crush || ringLock ? "0.96" : "0";
      face.style.opacity = crush ? "0" : "";
      wiii.style.zIndex = "";
      if (scarf) {
        const w = wiii.offsetWidth || 360;
        const h = wiii.offsetHeight || 340;
        const scale = phone ? 0.3 : 0.72;
        const tipX = viewSize().w * (phone ? 0.16 : 0.36);
        const tipY = viewSize().h * (phone ? 0.74 : 0.58);
        wiii.style.bottom = "auto";
        wiii.style.transformOrigin = "72% 80%";
        wiii.style.transform = `scale(${scale})`;
        wiii.style.left = `${tipX - w * 0.72}px`;
        wiii.style.top = `${tipY - h * 0.8}px`;
        wiii.style.zIndex = phone ? "6" : "";
      } else if (id === "clash" && p < 0.3) {
        wiii.style.bottom = "0";
        wiii.style.top = "";
        wiii.style.left = "0";
        wiii.style.transformOrigin = "";
        wiii.style.transform = `translate(${-18 + p * 110}vw, 8vh)`;
      } else {
        wiii.style.bottom = "0";
        wiii.style.top = "";
        wiii.style.left = "0";
        wiii.style.transformOrigin = "";
        wiii.style.transform = "";
      }
      drift.style.width = "";
      drift.style.transformOrigin = "";
      if (id === "intrusion") drift.style.transform = "translate(-4vw, 4vh)";
      else if (id === "neko" && phone && p < 0.42) {
        const q = Math.round(clamp(p / 0.42, 0, 1) * 6) / 6;
        drift.style.transform = `translate(${-6 - q * 16}vw, ${4 - q * 6}vh) rotate(${-4 - q * 12}deg)`;
      } else if (id === "neko") drift.style.transform = `translate(${-8 - p * 20}vw, 6vh) rotate(${-6 - p * 8}deg)`;
      else if (crush) {
        const q = Math.round(clamp(p / 0.26, 0, 1) * 5) / 5;
        const zoom = 1.85 + q * 0.55;
        drift.style.width = `min(${(84 * zoom).toFixed(2)}vw, ${Math.round(480 * zoom)}px)`;
        drift.style.transformOrigin = "28% 14%";
        drift.style.transform = `translate(${-2 - q * 10}vw, ${-2 - q * 8}vh) rotate(${-3 - q * 9}deg)`;
      } else if (ringLock) drift.style.transform = "translate(54vw, 2vh) scale(0.58)";
      else drift.style.transform = "translate(48vw, 0)";
    },
    recoil() {
      hitUntil = performance.now() + 380;
      drift.classList.remove("is-hit");
      void drift.offsetWidth;
      drift.classList.add("is-hit");
    },
    draw(now, vel) {
      if (now - lastInput > 5000) root.classList.add("is-idle");
      const posed = holdPose(now);
      collectBoxes();
      if (posed) placeFace();
      tips.length = 0;
      const pts = fingerTips();
      for (const pt of pts) tips.push(pt);
      if (ctx) {
        ctx.clearRect(0, 0, viewSize().w, viewSize().h);
        drawSpeed(vel);
        if (posed) placeArms();
        drawShed();
        drawLife(now);
        drawMarks();
        const ribbon = weatherRibbon();
        if (ribbon.length > 1) {
          ctx.lineCap = "round";
          ctx.lineJoin = "round";
          ctx.strokeStyle = "rgba(42,41,40,0.9)";
          ctx.lineWidth = 7;
          ctx.beginPath();
          ribbon.forEach((pt, i) => (i ? ctx.lineTo(pt.x, pt.y) : ctx.moveTo(pt.x, pt.y)));
          ctx.stroke();
          ctx.strokeStyle = "rgba(243,238,227,0.85)";
          ctx.lineWidth = 2;
          ctx.stroke();
        }
        if (trail.length > 1) {
          ctx.lineCap = "round";
          ctx.strokeStyle = "rgba(243,238,227,0.4)";
          ctx.lineWidth = Math.max(0.6, 2.6 - vel * 2.2);
          ctx.beginPath();
          trail.forEach((pt, i) => (i ? ctx.lineTo(pt.x, pt.y) : ctx.moveTo(pt.x, pt.y)));
          ctx.stroke();
        }
      }
      if (!root.classList.contains("is-charge")) spark.style.scale = String(1 + Math.min(0.28, vel * 0.45));
      const bucket = Math.floor(now / (chasing() ? 80 : 32));
      if (bucket !== trailBucket) {
        trailBucket = bucket;
        trail.unshift({ ...pointer });
        if (trail.length > 8) trail.pop();
      }
      const sparkPt = trail[0] ?? pointer;
      spark.style.transform = `translate(${sparkPt.x}px, ${sparkPt.y}px)`;
      const freed = root.classList.contains("is-freed");
      if (!posed) {
        if (performance.now() < hitUntil) drift.classList.add("is-hit");
        else drift.classList.remove("is-hit");
        return;
      }
      ghosts.forEach((ghost, i) => {
        const src = trail[Math.min(trail.length - 1, 2 + i * 2)] ?? sparkPt;
        if (freed) {
          ghost.style.opacity = "0";
          ghost.style.transform = `translate(${src.x + (i - 1) * 80}px, ${src.y - 40}px) rotate(${20 * (i - 1)}deg)`;
          return;
        }
        ghost.style.opacity = chasing() ? String(0.26 - i * 0.06) : "0";
        ghost.style.transform = `translate(${src.x + 10}px, ${src.y + 8}px)`;
      });
      drift.classList.toggle("is-hit", performance.now() < hitUntil);
    },
  };
}
