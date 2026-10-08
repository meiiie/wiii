/**
 * Film-engine QA. The DOM suite stays on `/` (this machine is SwiftShader, so
 * `/` must keep the fallback). This script drives `/film` directly.
 *
 * 390×844 dpr2 and 360×780: random flicks, 40 fast downs, 60 ups, a tap,
 * scrollY stays 0, no horizontal overflow. Desktop wheel at 1440.
 */
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const port = 4191;
const chrome = process.env.CHROME_PATH || "/usr/local/bin/google-chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const preview = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
  cwd: root,
  stdio: ["ignore", "pipe", "pipe"],
});
let previewLog = "";
preview.stdout.on("data", (chunk) => { previewLog += chunk; });
preview.stderr.on("data", (chunk) => { previewLog += chunk; });

const waitForServer = async () => {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/film`);
      if (res.ok) return;
    } catch { /* booting */ }
    await sleep(200);
  }
  throw new Error(`preview did not start\n${previewLog}`);
};

await waitForServer();

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--no-sandbox", "--hide-scrollbars"],
});
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", (err) => pageErrors.push(String(err)));
const failures = [];
const fail = (msg) => {
  failures.push(msg);
  console.error("FAIL", msg);
};

const state = () => page.evaluate(() => {
  const d = window.__WIII.debug();
  return {
    p: window.__WIII.progress,
    act: window.__WIII.act,
    g: window.__WIII.gating,
    seal: window.__WIII.seal,
    y: window.scrollY,
    orient: window.__WIII.orient,
    plate: window.__WIII.plate,
    energy: d.energy,
    strikes: window.__WIII.strikes,
  };
});

const until = async (pred, ms, label) => {
  const t0 = Date.now();
  let last = await state();
  while (Date.now() - t0 < ms) {
    last = await state();
    if (pred(last)) return last;
    await sleep(200);
  }
  fail(`${label} p=${last.p.toFixed(3)} act=${last.act} gate=${last.g} seal=${last.seal.toFixed(2)} energy=${Math.round(last.energy)}`);
  return last;
};

const drag = async (client, x, y0, y1) => {
  await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: y0, id: 1 }] });
  const steps = 5;
  for (let i = 1; i <= steps; i++) {
    await client.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [{ x, y: Math.round(y0 + ((y1 - y0) * i) / steps), id: 1 }],
    });
    await sleep(12);
  }
  await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await sleep(16);
};

const overlayAt = async (w, h, mobile) => {
  await page.setViewport({ width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
  await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII?.mode === "film" && window.__WIII.plate, { timeout: 15000 });
  await page.evaluate(() => document.fonts.ready);
  await sleep(250);
  // Kakoi at 0.55/0.60 stays unsealed. Acts after kakoi seal the ring, so they come last.
  const stops = [
    ["awaken", 0.55],
    ["intrusion", 0.55],
    ["clash", 0.2],
    ["clash", 0.55],
    ["clash", 0.7],
    ["observe", 0.55],
    ["neko", 0.55],
    ["kakoi", 0.55],
    ["kakoi", 0.6],
    ["still", 0.55],
    ["return", 0.55],
    ["return", 0.9],
  ];
  let bad = 0;
  for (const [id, t] of stops) {
    await page.evaluate((act, local) => window.__WIII.scrollToAct(act, local), id, t);
    await sleep(60);
    const problems = await page.evaluate(() => {
      const height = window.innerHeight;
      const topLine = height * 0.14;
      const botLine = height * 0.78;
      const visible = [...document.querySelectorAll("[data-overlay]")].flatMap((el) => {
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) < 0.05) return [];
        const rect = el.getBoundingClientRect();
        if (rect.width < 2 || rect.height < 2) return [];
        const name = el.id || el.getAttribute("aria-label") || (el.textContent || "").trim().slice(0, 28);
        return [{ name, top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right }];
      });
      const found = [];
      for (const rect of visible) {
        const inTop = rect.top >= -2 && rect.bottom <= topLine + 2;
        const inBot = rect.top >= botLine - 2 && rect.bottom <= height + 2;
        if (!inTop && !inBot) found.push(`zone ${rect.name} ${rect.top.toFixed(0)}-${rect.bottom.toFixed(0)} of ${height}`);
      }
      for (let i = 0; i < visible.length; i++) {
        for (let j = i + 1; j < visible.length; j++) {
          const a = visible[i];
          const b = visible[j];
          const overlapW = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const overlapH = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          if (overlapW > 1 && overlapH > 1) found.push(`hit ${a.name} × ${b.name}`);
        }
      }
      return found;
    });
    if (problems.length) {
      bad += 1;
      fail(`${w}x${h} ${id}@${t} ${problems.slice(0, 6).join("; ")}`);
    }
  }
  if (!bad) console.log(`overlay ${w}x${h} clean`);
};

const overflow = () => page.evaluate(() => {
  const rootEl = document.documentElement;
  const offenders = [...document.querySelectorAll("body *")]
    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 2 && (rect.right > rootEl.clientWidth + 1 || rect.left < -1))
    .slice(0, 4)
    .map(({ el, rect }) => `${el.tagName}#${el.id} right=${Math.round(rect.right)}`);
  return { sw: rootEl.scrollWidth, cw: rootEl.clientWidth, offenders };
});

try {
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII, { timeout: 15000 });
  await sleep(400);
  const home = await page.evaluate(() => window.__WIII.mode || "dom");
  console.log(`home mode=${home}`);
  if (home === "film") fail("software renderer took the film engine on /");

  await overlayAt(360, 780, true);
  await overlayAt(390, 844, true);
  await overlayAt(430, 932, true);
  await overlayAt(1440, 900, false);

  const phone = async (w, h, full) => {
    await page.setViewport({ width: w, height: h, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__WIII?.mode === "film" && window.__WIII.plate, { timeout: 15000 });
    await sleep(700);
    const boot = await state();
    console.log(`${w} boot orient=${boot.orient} plate=${boot.plate} y=${boot.y}`);
    if (boot.orient !== "portrait") fail(`${w} orient ${boot.orient}`);
    if (!boot.plate.includes("-portrait-1920.")) fail(`${w} plate ${boot.plate}`);
    if (boot.y !== 0) fail(`${w} scrollY ${boot.y}`);
    const urls = await page.evaluate(() => performance.getEntriesByType("resource").map((e) => e.name));
    if (urls.some((u) => u.includes("portrait-2560"))) fail(`${w} loaded a 2560 portrait plate`);
    if (urls.some((u) => u.includes("portrait-1280"))) fail(`${w} loaded a 1280 portrait plate at dpr 2`);
    if (!urls.some((u) => u.includes("portrait-depth-1024"))) fail(`${w} missing 1024 portrait depth`);
    const plates = urls.filter((u) => /\/art\/kf\d/.test(u) && !u.includes("depth"));
    if (plates.length > 4) fail(`${w} preloaded ${plates.length} plates`);

    const client = await page.createCDPSession();
    const strikes = boot.strikes;
    await page.touchscreen.tap(w * 0.5, h * 0.5);
    await sleep(200);
    const tapped = await page.evaluate(() => window.__WIII.strikes);
    if (tapped <= strikes) fail(`${w} tap did not strike`);

    if (full) {
      for (let i = 0; i < 100; i++) {
        const dir = Math.random() < 0.5 ? 1 : -1;
        const dist = 90 + Math.random() * 380;
        const y0 = h * 0.55;
        const y1 = Math.max(24, Math.min(h - 24, y0 - dir * dist));
        await drag(client, w / 2, y0, y1);
      }
      const mid = await state();
      if (mid.y !== 0) fail(`${w} random flicks moved scrollY to ${mid.y}`);
      console.log(`${w} random p=${mid.p.toFixed(3)} act=${mid.act} strikes=${mid.strikes}`);
      await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
      await page.waitForFunction(() => window.__WIII?.plate, { timeout: 15000 });
      await sleep(400);
    }

    const yDown0 = h * 0.82;
    const yDown1 = h * 0.16;
    for (let i = 0; i < 40; i++) await drag(client, w / 2, yDown0, yDown1);
    const end = await until((s) => s.p >= 0.98 && !s.g, 28000, `${w} 40 down did not finish`);
    console.log(`${w} end p=${end.p.toFixed(3)} act=${end.act} y=${end.y}`);
    if (end.y !== 0) fail(`${w} end scrollY ${end.y}`);
    for (let i = 0; i < 60; i++) await drag(client, w / 2, yDown1, yDown0);
    const back = await until((s) => s.p <= 0.02 && !s.g, 28000, `${w} 60 up did not return`);
    console.log(`${w} back p=${back.p.toFixed(3)} act=${back.act}`);
    if (back.y !== 0) fail(`${w} back scrollY ${back.y}`);
    const flow = await overflow();
    if (flow.sw > flow.cw + 1) fail(`${w} overflow ${flow.sw}>${flow.cw} ${flow.offenders.join(" | ")}`);
    const perf = await page.evaluate(() => window.__WIII.perf());
    console.log(`${w} perf avg=${perf.avg.toFixed(2)} p95=${perf.p95.toFixed(2)} n=${perf.n} dpr=${perf.dpr} dof=${perf.dof}`);
    await client.detach();
  };

  await phone(390, 844, true);
  await phone(360, 780, false);

  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1, isMobile: false, hasTouch: false });
  await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII?.mode === "film", { timeout: 15000 });
  await sleep(500);
  await page.evaluate(() => window.__WIII.scrollToAct("act-intrusion", 0.4));
  const before = await state();
  // Size only. Toggling isMobile reloads the document, which is not an orientation change.
  await page.setViewport({ width: 700, height: 1000, deviceScaleFactor: 1 });
  await sleep(900);
  const flipped = await state();
  console.log(`resize ${before.orient} p=${before.p.toFixed(3)} -> ${flipped.orient} p=${flipped.p.toFixed(3)} plate=${flipped.plate}`);
  if (flipped.orient !== "portrait") fail(`resize orient ${flipped.orient}`);
  if (!flipped.plate.includes("portrait")) fail(`resize plate ${flipped.plate}`);
  if (Math.abs(flipped.p - before.p) > 0.04) fail(`resize lost t ${before.p.toFixed(3)} -> ${flipped.p.toFixed(3)}`);

  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1, isMobile: false, hasTouch: false });
  await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII?.plate, { timeout: 15000 });
  await sleep(400);
  const desk = await state();
  if (desk.orient !== "landscape") fail(`1440 orient ${desk.orient}`);
  for (let i = 0; i < 10; i++) {
    await page.mouse.wheel({ deltaY: 140 });
    await sleep(30);
  }
  const wheeled = await until((s) => s.p > 0.08, 4000, "1440 wheel did not advance");
  console.log(`1440 wheel p=${wheeled.p.toFixed(3)} act=${wheeled.act} orient=${wheeled.orient} plate=${wheeled.plate}`);
  if (wheeled.y !== 0) fail(`1440 scrollY ${wheeled.y}`);
  const perf = await page.evaluate(() => window.__WIII.perf());
  console.log(`1440 perf avg=${perf.avg.toFixed(2)} p95=${perf.p95.toFixed(2)} n=${perf.n} dpr=${perf.dpr} dof=${perf.dof}`);
} finally {
  await browser.close();
  preview.kill("SIGTERM");
}

if (pageErrors.length) for (const err of pageErrors) fail(`pageerror ${err}`);
console.log(failures.length ? `\n${failures.length} film failure(s)` : "\nfilm QA passed");
if (failures.length) process.exit(1);
