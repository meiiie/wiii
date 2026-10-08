import gsap from "gsap";
import { Sfx } from "../audio";
import { isSoftwareRenderer } from "./capable";
import "./film.css";
import { mountOverlay } from "./overlay";
import {
  aheadPlate,
  artUrls,
  coverWindow,
  evalCam,
  LANDSCAPE,
  orientOf,
  plateFor,
  PORTRAIT,
  type ActId,
  type Cam,
  type Orient,
  type PlateId,
} from "./plates";
import { FilmRenderer, type Grade, type SceneDraw } from "./render";
import { VirtualScroll } from "./scroll";
import { MasterTimeline } from "./timeline";

const GRADES: Record<ActId, Grade> = {
  awaken: { lift: [0.02, 0.025, 0.04], gain: [0.95, 0.97, 1.05], gamma: 1.02, sat: 0.9 },
  intrusion: { lift: [0.06, 0.01, 0.01], gain: [1.08, 0.94, 0.9], gamma: 0.96, sat: 1.05 },
  clash: { lift: [0.05, 0.0, 0.0], gain: [1.12, 0.9, 0.86], gamma: 0.92, sat: 1.12 },
  observe: { lift: [0.03, 0.03, 0.04], gain: [0.96, 0.96, 1.0], gamma: 1.04, sat: 0.72 },
  neko: { lift: [0.04, 0.025, 0.015], gain: [1.05, 0.98, 0.92], gamma: 0.98, sat: 1.0 },
  kakoi: { lift: [0.04, 0.03, 0.02], gain: [1.02, 0.98, 0.94], gamma: 1.0, sat: 0.92 },
  still: { lift: [0.07, 0.06, 0.045], gain: [1.06, 1.03, 0.98], gamma: 1.05, sat: 0.66 },
  return: { lift: [0.02, 0.025, 0.05], gain: [0.9, 0.95, 1.08], gamma: 1.04, sat: 0.84 },
};

const FOG: Record<ActId, [number, number, number]> = {
  awaken: [0.05, 0.06, 0.09],
  intrusion: [0.12, 0.03, 0.03],
  clash: [0.16, 0.04, 0.03],
  observe: [0.08, 0.08, 0.09],
  neko: [0.1, 0.06, 0.04],
  kakoi: [0.09, 0.08, 0.07],
  still: [0.93, 0.9, 0.84],
  return: [0.04, 0.05, 0.08],
};

type Tier = { dpr: number; dof: boolean; note: (ms: number) => boolean };

function makeTier(software: boolean): Tier & { index: number } {
  const steps = [1, 1.5, 2];
  const device = window.devicePixelRatio || 1;
  let index = software ? 0 : device >= 2 ? 2 : device >= 1.5 ? 1 : 0;
  let dof = !software;
  let cool = 0;
  const bucket: number[] = [];
  const changed = () => {
    cool = 180;
    return true;
  };
  return {
    get index() { return index; },
    get dpr() { return steps[index]; },
    get dof() { return dof; },
    note(ms: number) {
      bucket.push(ms);
      if (ms > 34 && cool <= 0 && (index > 0 || dof)) {
        if (index > 0) index -= 1;
        else dof = false;
        cool = 6;
        bucket.length = 0;
        return true;
      }
      if (bucket.length < 60) return false;
      const avg = bucket.reduce((s, n) => s + n, 0) / bucket.length;
      bucket.length = 0;
      if (cool > 0) {
        cool -= 60;
        return false;
      }
      if (avg > 22) {
        if (index > 0) {
          index -= 1;
          return changed();
        }
        if (dof) {
          dof = false;
          return changed();
        }
      } else if (avg < 12) {
        if (!dof) {
          dof = true;
          return changed();
        }
        if (index < 2 && device + 0.05 >= steps[index + 1]) {
          index += 1;
          return changed();
        }
      }
      return false;
    },
  };
}

function snowFor(act: ActId, t: number, sealed: boolean, portrait: boolean) {
  const fall = 1;
  const vertical: [number, number] = [0, 0.85];
  if (act === "awaken") return { count: portrait ? 160 : 200, mode: 0, wind: (portrait ? [0.04, 0.7] : [0.15, 0.25]) as [number, number], pressure: 0.06, fall, ring: 0 };
  if (act === "intrusion") return { count: 340, mode: 0, wind: (portrait ? [0.08, 0.9 + t * 0.4] : [0.35 + t * 0.8, 0.3]) as [number, number], pressure: 0.25 + t * 0.4, fall, ring: 0 };
  if (act === "clash") return { count: 420, mode: 0, wind: (portrait ? [0.06, 1.1] : [0.9, 0.15]) as [number, number], pressure: 0.62, fall, ring: 0 };
  if (act === "observe") return { count: 160, mode: 0, wind: (portrait ? [0.04, 0.45] : [0.22, 0.18]) as [number, number], pressure: 0.08 + t * 0.2, fall, ring: 0 };
  if (act === "neko" && t < 0.42) return { count: 400, mode: 0, wind: (portrait ? [0.05, 0.8] : [0.85, 0.2]) as [number, number], pressure: 0.7, fall, ring: 0 };
  if (act === "neko") return { count: 240, mode: 1, wind: (portrait ? [0.04, -0.9] : [0.25, -0.35]) as [number, number], pressure: 0.22, fall: 1.15, ring: 0 };
  if (act === "kakoi" && !(sealed && t >= 0.5)) return { count: 460, mode: 0, wind: (portrait ? [0.7, 0.85] : [1.05, 0.3]) as [number, number], pressure: 0.74, fall, ring: portrait ? 1 : 0 };
  if (act === "kakoi") return { count: portrait ? 220 : 70, mode: 0, wind: (portrait ? [0.55, 0.35] : [0.12, 0.08]) as [number, number], pressure: 0.08, fall: portrait ? 0.8 : 0.4, ring: portrait ? 1 : 0 };
  if (act === "still" || (act === "return" && t >= 0.55)) return { count: portrait ? 180 : 28, mode: 2, wind: (portrait ? vertical : [0, 0.04]) as [number, number], pressure: 0.04, fall: portrait ? 0.7 : 0.2, ring: 0 };
  return { count: 110, mode: 0, wind: (portrait ? [0.04, 0.55] : [0.12, 0.2]) as [number, number], pressure: 0.1, fall, ring: 0 };
}

function cutoutLayout(act: ActId, t: number, sealed: boolean, narrow: boolean, portrait: boolean) {
  if (portrait) {
    const none = { alpha: 0, pos: [0.5, 0.5] as [number, number], size: [0.2, 0.2] as [number, number], depth: 0.5 };
    return { wiii: none, drift: { ...none, depth: 0.4 } };
  }
  const h = narrow ? 0.42 : 0.58;
  const aspect = window.innerWidth / Math.max(1, window.innerHeight);
  const wiiiW = h * (733 / 679) / aspect;
  const driftW = h * (640 / 871) / aspect;
  let wiiiA = 0;
  let driftA = 0;
  let wiiiPos: [number, number] = [0.72, 0.62];
  let driftPos: [number, number] = [0.28, 0.48];
  if (act === "intrusion") {
    wiiiA = 0.95;
    driftA = 1;
    wiiiPos = [0.78, 0.7];
    driftPos = [0.32, 0.42];
  } else if (act === "clash") {
    wiiiA = 1;
    driftA = 1;
    wiiiPos = [0.62, 0.58];
    driftPos = [0.34, 0.46];
  } else if (act === "observe") {
    wiiiA = 0.9;
    driftA = 0.8;
    wiiiPos = [0.7, 0.6];
    driftPos = [0.3, 0.4];
  } else if (act === "neko") {
    wiiiA = 1;
    driftA = t < 0.42 ? 0.9 : 0.15;
    wiiiPos = [0.58, 0.62];
    driftPos = [0.36, 0.4];
  } else if (act === "kakoi") {
    wiiiA = 1;
    driftA = sealed || t >= 0.26 ? 0 : 0.85;
    wiiiPos = [0.5, narrow ? 0.58 : 0.62];
    driftPos = [0.5, 0.3];
  } else if (act === "still") {
    wiiiA = 0.85;
    wiiiPos = [0.5, 0.58];
  } else if (act === "return") {
    wiiiA = t > 0.72 ? 0 : 0.35;
    wiiiPos = [0.5, 0.78];
  }
  return {
    wiii: { alpha: wiiiA, pos: wiiiPos, size: [wiiiW, h] as [number, number], depth: 0.9 },
    drift: { alpha: driftA, pos: driftPos, size: [driftW, h * 1.05] as [number, number], depth: 0.62 },
  };
}

export async function startFilm(): Promise<void> {
  document.documentElement.classList.add("is-film");
  document.body.style.overflow = "hidden";
  const world = document.getElementById("world");
  if (world) {
    world.setAttribute("inert", "");
    world.setAttribute("aria-hidden", "true");
  }
  const canvas = document.createElement("canvas");
  canvas.id = "film";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  const timeline = new MasterTimeline();
  const sfx = new Sfx();
  const flashTimes: number[] = [];
  let invertUntil = 0;
  let shakeUntil = 0;
  let shakeDir: [number, number] = [0, 0];
  let lastPlate: PlateId | "" = "";
  let plateUrl = "";
  const renderer = new FilmRenderer(canvas);
  const tier = makeTier(isSoftwareRenderer());
  renderer.resize(tier.dpr);
  renderer.dof = tier.dof;
  const overlay = mountOverlay(timeline);
  const scroll = new VirtualScroll(timeline, () => {
    const now = performance.now();
    const recent = flashTimes.filter((t) => now - t < 1000);
    if (recent.length < 3) {
      flashTimes.push(now);
      invertUntil = now + 48;
    }
    if (sfx.enabled) sfx.play("impact");
    const live = document.getElementById("film-live");
    if (live) live.textContent = "Strike";
  });
  scroll.bind();
  const x0 = timeline.layout(window.innerHeight, true);
  scroll.snap(x0);

  const orientNow = () => orientOf();
  let orient: Orient = orientNow();
  let lastH = window.innerHeight;

  const warm = (id: PlateId, o: Orient) => {
    const urls = artUrls(id, o);
    renderer.requestImage(urls.plate, urls.fallback, false);
    renderer.requestImage(urls.depth, "", true);
  };

  overlay.onSeek((id) => {
    scroll.snap(timeline.seekAct(id, 0));
  });
  overlay.onSound(() => {
    void sfx.toggle().then((on) => overlay.setSound(on));
  });
  window.addEventListener("pointerdown", () => sfx.unlock(), { passive: true });

  const sceneFor = (slot: string, act: ActId, local: number, cam: Cam, o: Orient, now: number): SceneDraw => {
    const plateId = plateFor(act, local);
    const urls = artUrls(plateId, o);
    const pair = renderer.retain(slot, urls.plate, urls.fallback, urls.depth, urls.aspect);
    if (slot === "a") plateUrl = renderer.urls().includes(urls.plate) ? urls.plate : (urls.fallback && renderer.urls().includes(urls.fallback) ? urls.fallback : plateUrl);
    const crop = coverWindow(cam.focal, pair.aspect, window.innerWidth / Math.max(1, window.innerHeight));
    const stepped = Math.floor(now / 83);
    const portrait = o === "portrait";
    const layout = cutoutLayout(act, local, timeline.sealed, window.innerWidth <= 800, portrait);
    const hold = stepped;
    const wiii = layout.wiii.alpha > 0 ? renderer.image("/art/cut-wiii-960.webp") : null;
    const drift = layout.drift.alpha > 0 ? renderer.image("/art/cut-drift-840.webp") : null;
    const snow = snowFor(act, local, timeline.sealed, portrait);
    return {
      plate: pair.plate,
      depth: pair.depth,
      cam,
      crop,
      rig: [scroll.rigX, scroll.rigY],
      shake: now < shakeUntil ? shakeDir : [0, 0],
      fog: FOG[act],
      fogAmt: act === "still" ? 0.08 : 0.22,
      dof: renderer.dof,
      wiii: { tex: wiii, alpha: layout.wiii.alpha, pos: layout.wiii.pos, size: layout.wiii.size, depth: layout.wiii.depth },
      drift: { tex: drift, alpha: layout.drift.alpha, pos: layout.drift.pos, size: layout.drift.size, depth: layout.drift.depth },
      snow: { ...snow, count: hold % 2 === 0 ? snow.count : Math.max(12, snow.count - 8) },
    };
  };

  const draw = (now: number) => {
    orient = orientNow();
    const act = timeline.act;
    const local = timeline.gate ? 1 : timeline.localT(scroll.cam);
    const breathe = act === "still" ? 0 : Math.sin(now / 1000 * 0.7) * 0.003;
    const keys = orient === "portrait" ? PORTRAIT[act] : LANDSCAPE[act];
    const cam = evalCam(keys, local, breathe);
    if (orient === "portrait") cam.truck = [Math.max(-0.08, Math.min(0.08, cam.truck[0])), cam.truck[1]];
    const stepped = Math.round(local * 12) / 12;
    warm(plateFor(act, stepped), orient);
    warm(aheadPlate(act, stepped), orient);
    const nextIndex = timeline.gate ? timeline.gate.to : Math.min(ACTS_NEXT(act), 7);
    const nextAct = (["awaken", "intrusion", "clash", "observe", "neko", "kakoi", "still", "return"] as ActId[])[nextIndex];
    const plateId = plateFor(act, stepped);
    if (plateId !== lastPlate && (plateId === "impact" || (act === "neko" && stepped >= 0.42 && lastPlate !== "neko"))) {
      const recent = flashTimes.filter((t) => now - t < 1000);
      if (recent.length < 3) {
        flashTimes.push(now);
        invertUntil = now + 50;
      }
      shakeUntil = now + 48;
      shakeDir = [0.012, -0.008];
    }
    lastPlate = plateId;
    const a = sceneFor("a", act, stepped, cam, orient, now);
    const nextKeys = orient === "portrait" ? PORTRAIT[nextAct] : LANDSCAPE[nextAct];
    const nextLocal = timeline.gate ? timeline.gate.t * 0.2 : 0;
    const needB = Boolean(timeline.gate);
    if (needB) {
      const b = sceneFor("b", nextAct, nextLocal, evalCam(nextKeys, nextLocal, 0), orient, now);
      renderer.paintScene(1, b, now / 1000);
    }
    renderer.paintScene(0, a, now / 1000);
    const kind = timeline.gate ? (timeline.gate.kind === "ink" ? 1 : timeline.gate.kind === "smear" ? 2 : 3) : 0;
    const smear = timeline.gate?.kind === "smear"
      ? timeline.gate.t
      : act === "clash" && local > 0.42 && local < 0.62
        ? (local - 0.42) / 0.2
        : 0;
    const grade = gradeFor(act, local, timeline.sealed);
    const impact = plateId === "impact" || invertUntil > now;
    renderer.present(grade, timeline.gate?.t ?? 0, kind, invertUntil > now ? 1 : 0, smear, impact ? 0.0035 : 0, now / 1000);
    const frame = Math.round((timeline.progress * 2400) + 1);
    overlay.sync(timeline, local, frame);
    if (sfx.enabled && timeline.act === "kakoi" && !timeline.sealed && timeline.seal > 0) {
      sfx.wind(0.18 + timeline.seal * 0.75, timeline.seal > 0.35);
    }
    document.documentElement.dataset.p = local.toFixed(3);
  };

  let hold = false;
  let last = performance.now();
  const times: number[] = [];
  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add(() => {
    const now = performance.now();
    const elapsed = Math.max(0, (now - last) / 1000);
    last = now;
    const dt = Math.min(0.5, elapsed);
    const ms = elapsed * 1000;
    times.push(ms);
    if (times.length > 180) times.shift();
    renderer.frameMs = times;
    if (tier.note(ms)) {
      renderer.dof = tier.dof;
      renderer.resize(tier.dpr);
    }
    if (hold) return;
    scroll.update(dt, now);
    draw(now);
  });

  window.addEventListener("resize", () => {
    const o = orientNow();
    if (o === orient && Math.abs(window.innerHeight - lastH) < 48) {
      renderer.resize(tier.dpr);
      return;
    }
    orient = o;
    lastH = window.innerHeight;
    scroll.snap(timeline.layout(window.innerHeight));
    renderer.resize(tier.dpr);
  });

  const api = {
    mode: "film" as const,
    flashTimes,
    lenis: undefined,
    get strikes() { return scroll.strikes; },
    get progress() { return timeline.progress; },
    get act() { return timeline.act; },
    get gating() { return Boolean(timeline.gate); },
    get seal() { return timeline.seal; },
    get orient() { return orient; },
    get plate() { return plateUrl; },
    scrollToAct(id: string, p: number) {
      scroll.snap(timeline.seekAct(id, p));
      draw(performance.now());
    },
    debug() {
      return {
        target: scroll.target,
        pos: scroll.pos,
        cam: scroll.cam,
        energy: timeline.energy,
        locked: scroll.locked,
        cap: timeline.cap(),
        total: timeline.total,
        plate: plateUrl,
        textures: renderer.urls(),
        fbo: renderer.fboOk,
      };
    },
    present(u: number) {
      hold = true;
      const sample = timeline.sampleFilm(u);
      scroll.cam = scroll.pos = scroll.target = timeline.playhead;
      draw(performance.now());
      return sample.act;
    },
    release() { hold = false; },
    perf() {
      const xs = times.slice().sort((a, b) => a - b);
      const avg = xs.reduce((s, n) => s + n, 0) / Math.max(1, xs.length);
      const p95 = xs[Math.min(xs.length - 1, Math.floor(xs.length * 0.95))] ?? 0;
      return { avg, p95, n: xs.length, dpr: tier.dpr, dof: tier.dof };
    },
  };
  window.__WIII = api;
}

function ACTS_NEXT(act: ActId): number {
  const order: ActId[] = ["awaken", "intrusion", "clash", "observe", "neko", "kakoi", "still", "return"];
  return Math.min(order.length - 1, order.indexOf(act) + 1);
}

function gradeFor(act: ActId, local: number, sealed: boolean): Grade {
  const base = GRADES[act];
  if (act === "kakoi" && sealed && local >= 0.26) {
    return { lift: [0.06, 0.05, 0.04], gain: [1.04, 1.02, 0.98], gamma: 1.04, sat: 0.7 };
  }
  return base;
}
