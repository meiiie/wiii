import type { ActId } from "./plates";
import type { MasterTimeline } from "./timeline";

const COPY: Record<ActId, { kicker: string; title: string; body: string; ja: string }> = {
  awaken: {
    kicker: "00 — The spark",
    title: "The spark is your cursor.",
    body: "Wiii is a local-first desktop workspace for working with Neko. You decide what it can access and change.",
    ja: "覚醒",
  },
  intrusion: {
    kicker: "01 — Drift",
    title: "It changes everything without asking.",
    body: "A local project does not require a Wiii Service account. You decide what the agent can access and change. Model providers may require their own account.",
    ja: "侵入",
  },
  clash: {
    kicker: "02 — The work",
    title: "The work stays in the folder.",
    body: "Project. Choose a folder. Session. The sessions that belong to it. Tools. Công cụ beside the conversation.",
    ja: "衝突",
  },
  observe: {
    kicker: "03 — Observe",
    title: "Observation is not control.",
    body: "",
    ja: "観測",
  },
  neko: {
    kicker: "04 — Neko",
    title: "Taking control waits.",
    body: "It does not undo what already left.",
    ja: "猫",
  },
  kakoi: {
    kicker: "05 — Kakoi",
    title: "The ring closes.",
    body: "",
    ja: "囲",
  },
  still: {
    kicker: "06 — Still",
    title: "Computer is optional.",
    body: "Wiii Service is optional. Neither is required to begin.",
    ja: "間",
  },
  return: {
    kicker: "07 — The cursor",
    title: "The spark goes back to the cursor.",
    body: "",
    ja: "還",
  },
};

const RULES = [
  { at: 0.26, text: "A project folder, and the sessions that belong to it." },
  { at: 0.36, text: "Tools in view, beside the conversation." },
  { at: 0.42, text: "A missing harness is not a failed check. Look in Tổng quan → Quản lý harness." },
  { at: 0.7, text: "An interrupted action is not automatically repeated when its outcome is unknown." },
  { at: 0.86, text: "Computer is optional. Wiii Service is optional. Neither is required to begin." },
];

const ACT_LABEL: Record<ActId, string> = {
  awaken: "00 Awaken",
  intrusion: "01 Intrusion",
  clash: "02 Clash",
  observe: "03 Observe",
  neko: "04 Neko",
  kakoi: "05 Kakoi",
  still: "06 Still",
  return: "07 Return",
};

export type Overlay = {
  root: HTMLElement;
  sync: (timeline: MasterTimeline, local: number, frame: number) => void;
  setSound: (on: boolean) => void;
  onSeek: (fn: (id: ActId) => void) => void;
  onSound: (fn: () => void) => void;
};

export function mountOverlay(timeline: MasterTimeline): Overlay {
  const root = document.createElement("div");
  root.id = "film-root";
  root.innerHTML = `
    <a class="film-skip" href="#film-copy">Skip to content</a>
    <p id="film-live" class="film-sr" aria-live="polite"></p>
    <div class="film-top">
      <header class="film-chrome">
        <a class="film-brand" data-overlay href="#act-awaken">Wiii</a>
        <p class="film-readout" aria-hidden="true"><span id="film-act">00 Awaken</span><span id="film-frame">F 0001</span></p>
        <nav class="film-stamps" aria-label="Acts"></nav>
      </header>
      <div class="film-lead" id="film-copy">
        <p class="film-kicker" id="film-kicker" data-overlay></p>
        <h1 id="film-title" data-overlay></h1>
      </div>
    </div>
    <p class="film-ja" id="film-ja" lang="ja" hidden></p>
    <div class="film-bot">
      <p id="film-body" data-overlay hidden></p>
      <footer class="film-colo" id="film-colo" hidden>
        <p data-overlay>The spark goes back to the cursor.</p>
        <p data-overlay>Built by <a href="https://holilihu.online">HoLiLiHu</a>. Original characters © HoLiLiHu</p>
      </footer>
      <div class="film-bot-row">
        <p class="film-how" id="film-how" data-overlay>Scroll the film. Tap to strike. Hold the ring to seal.</p>
        <button id="film-sound" type="button" data-overlay aria-pressed="false">Sound off</button>
      </div>
      <button id="film-seal" type="button" data-overlay hidden>
        <svg viewBox="0 0 48 48" aria-hidden="true">
          <circle cx="24" cy="24" r="18" fill="none" stroke="currentColor" stroke-width="2" opacity="0.35"></circle>
          <circle id="film-ring" cx="24" cy="24" r="18" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="113" stroke-dashoffset="113"></circle>
        </svg>
        Hold to seal
      </button>
    </div>
  `;
  document.body.append(root);
  const nav = root.querySelector(".film-stamps") as HTMLElement;
  for (const id of ["awaken", "intrusion", "clash", "observe", "neko", "kakoi", "still", "return"] as ActId[]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.act = id;
    btn.dataset.overlay = "";
    btn.textContent = ACT_LABEL[id].slice(0, 2);
    btn.setAttribute("aria-label", ACT_LABEL[id].slice(3));
    nav.append(btn);
  }
  const seal = root.querySelector("#film-seal") as HTMLButtonElement;
  const hold = (on: boolean) => {
    timeline.holding = on;
  };
  seal.addEventListener("pointerdown", (e) => {
    hold(true);
    e.preventDefault();
  });
  seal.addEventListener("pointerup", () => hold(false));
  seal.addEventListener("pointercancel", () => hold(false));
  seal.addEventListener("keydown", (e) => {
    if (e.key === " " || e.key === "Enter") {
      hold(true);
      e.preventDefault();
    }
  });
  seal.addEventListener("keyup", () => hold(false));
  seal.addEventListener("blur", () => hold(false));

  let seek: (id: ActId) => void = () => {};
  nav.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest("button");
    if (!btn?.dataset.act) return;
    seek(btn.dataset.act as ActId);
  });
  const sound = root.querySelector("#film-sound") as HTMLButtonElement;
  let onSound: () => void = () => {};
  sound.addEventListener("click", () => onSound());

  const title = root.querySelector("#film-title") as HTMLElement;
  const body = root.querySelector("#film-body") as HTMLElement;
  const kicker = root.querySelector("#film-kicker") as HTMLElement;
  const ja = root.querySelector("#film-ja") as HTMLElement;
  const actEl = root.querySelector("#film-act") as HTMLElement;
  const frameEl = root.querySelector("#film-frame") as HTMLElement;
  const ring = root.querySelector("#film-ring") as SVGCircleElement;
  const colo = root.querySelector("#film-colo") as HTMLElement;
  const live = root.querySelector("#film-live") as HTMLElement;
  const lead = root.querySelector(".film-lead") as HTMLElement;
  const top = root.querySelector(".film-top") as HTMLElement;
  const bot = root.querySelector(".film-bot") as HTMLElement;
  let shown: ActId | "" = "";

  return {
    root,
    onSeek: (fn) => {
      seek = fn;
    },
    onSound: (fn) => {
      onSound = fn;
    },
    setSound: (on) => {
      sound.setAttribute("aria-pressed", on ? "true" : "false");
      sound.textContent = on ? "Sound on" : "Sound off";
    },
    sync: (tl, local, frame) => {
      const act = tl.act;
      const copy = act === "neko" && local >= 0.42
        ? { ...COPY.neko, title: "Neko Core is the default.", body: "Existing harness choices stay intact." }
        : COPY[act];
      title.textContent = copy.title;
      kicker.textContent = copy.kicker;
      ja.textContent = copy.ja;
      let text = copy.body;
      if (act === "kakoi") {
        text = "Hold the ring. Drift stays outside.";
        for (const rule of RULES) if (local >= rule.at) text = rule.text;
      }
      body.textContent = text;
      body.hidden = text.trim() === "";
      actEl.textContent = ACT_LABEL[act];
      frameEl.textContent = `F ${String(frame).padStart(4, "0")}`;
      const paper = act === "still" || act === "kakoi";
      const tuck = act === "kakoi" && window.innerWidth / Math.max(1, window.innerHeight) < 0.75;
      root.classList.toggle("is-paper", paper);
      root.classList.toggle("is-kakoi", tuck);
      if (tuck) bot.insertBefore(lead, bot.firstChild);
      else top.append(lead);
      document.documentElement.classList.toggle("on-paper", paper);
      const showSeal = act === "kakoi" && !tl.sealed && local >= 0.45;
      seal.hidden = !showSeal;
      ring.style.strokeDashoffset = String(113 * (1 - tl.seal));
      colo.hidden = !(act === "return" && local >= 0.82);
      for (const btn of nav.querySelectorAll("button")) {
        btn.setAttribute("aria-current", btn.dataset.act === act ? "true" : "false");
      }
      if (shown !== act) {
        shown = act;
        live.textContent = ACT_LABEL[act];
      }
      document.documentElement.dataset.act = act;
      document.documentElement.dataset.engine = "film";
    },
  };
}
