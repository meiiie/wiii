#!/usr/bin/env node
/**
 * Native Wiii E2E: drives the compiled Tauri app through tauri-driver (WebKitWebDriver)
 * with the pinned bundled Neko Core and a loopback model. HOME is a temporary directory,
 * so app data, Neko config and sessions never touch the developer's profile.
 *
 *   npm run test:e2e:native -- --app "src-tauri/target/debug/Wiii Workbench" [--artifacts dir]
 */
import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { APPROVED_CONTENT, APPROVED_FILE, MARKERS, startFixtureModel } from "./fixture-model.mjs";
import { WebDriver, elementId, until } from "./webdriver.mjs";

const QUEUED_TEXT = "E2E_QUEUED follow-up must survive restart";
const PERMISSION_PROMPT = `${MARKERS.permission}: write the approval file`;
const SLOW_PROMPT = `${MARKERS.slow}: hold this turn until it is cancelled`;

const { values: args } = parseArgs({ options: {
  app: { type: "string" },
  artifacts: { type: "string", default: "e2e-native-artifacts" },
  driver: { type: "string", default: process.env.TAURI_DRIVER ?? "tauri-driver" },
  port: { type: "string", default: "4444" },
  keep: { type: "boolean", default: false },
  xdotool: { type: "string", default: process.env.XDOTOOL ?? "xdotool" },
} });
if (!args.app) throw new Error("--app <path to compiled Wiii binary> is required");
const app = path.resolve(args.app);
const artifacts = path.resolve(args.artifacts);
mkdirSync(artifacts, { recursive: true });

const root = realpathSync(mkdtempSync(path.join(tmpdir(), "wiii-native-e2e-")));
const home = path.join(root, "home");
// The native folder chooser starts in HOME, so keep the project there.
const project = path.join(home, "wiii-e2e-project");
for (const directory of [home, project, path.join(home, ".neko-core"), path.join(home, "tmp")]) {
  mkdirSync(directory, { recursive: true });
}
writeFileSync(path.join(project, "README.md"), "# Wiii native E2E project\n");

const log = (message) => console.log(`[native-e2e] ${message}`);
let step = 0;

async function capture(driver, name) {
  step += 1;
  const file = path.join(artifacts, `${String(step).padStart(2, "0")}-${name}.png`);
  try {
    writeFileSync(file, Buffer.from(await driver.screenshot(), "base64"));
  } catch (error) {
    log(`screenshot ${name} failed: ${error.message}`);
  }
}

const bodyText = (driver) => driver.execute("return document.body ? document.body.innerText : '';");

async function waitText(driver, needle, label, timeoutMs = 30_000) {
  await until(async () => (await bodyText(driver)).includes(needle), label ?? `text ${needle}`, timeoutMs);
}

async function element(driver, css, label, timeoutMs = 30_000) {
  return until(async () => {
    for (const id of await driver.findAll(css)) if (await driver.displayed(id)) return id;
    return null;
  }, label ?? css, timeoutMs);
}

/** A visible element matching `css` whose text (or aria-label) contains `needle`. */
async function elementWithText(driver, css, needle, label, timeoutMs = 30_000) {
  return until(async () => {
    const found = await driver.execute(`
      const [css, needle] = arguments;
      return [...document.querySelectorAll(css)].find((node) => {
        const box = node.getBoundingClientRect();
        const text = (node.innerText || "") + " " + (node.getAttribute("aria-label") || "");
        return box.width > 0 && box.height > 0 && text.includes(needle);
      }) ?? null;`, [css, needle]);
    return elementId(found);
  }, label ?? `${css} containing ${needle}`, timeoutMs);
}

/** Scroll a matching element into view, then verify it is not covered before clicking. */
async function clickableWithText(driver, css, needle, label, timeoutMs = 30_000) {
  return until(async () => {
    const found = await driver.execute(`
      const [css, needle] = arguments;
      return [...document.querySelectorAll(css)].find((node) => {
        if (!(node.innerText || "").includes(needle)) return false;
        node.scrollIntoView({ block: "center", inline: "nearest" });
        const box = node.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0) return false;
        const x = box.left + box.width / 2, y = box.top + box.height / 2;
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
        const hit = document.elementFromPoint(x, y);
        return Boolean(hit && (hit === node || node.contains(hit)));
      }) ?? null;`, [css, needle]);
    return elementId(found);
  }, label ?? `${css} containing ${needle}`, timeoutMs);
}

async function clickEnabled(driver, id, timeoutMs = 30_000) {
  await until(() => driver.enabled(id), "control to become enabled", timeoutMs);
  await driver.click(id);
}

async function typeInto(driver, css, text) {
  // A completion notice can briefly cover the composer's center after a
  // turn. Wait for a real pointer target rather than forcing focus through it.
  const id = await clickableWithText(driver, css, "", `${css} to be unobstructed`);
  await driver.click(id);
  await driver.type(id, text);
  return id;
}

async function focusMainWindow(driver) {
  await until(async () => {
    for (const handle of await driver.handles()) {
      await driver.switchTo(handle);
      const url = await driver.url();
      if (url.includes("splashscreen")) continue;
      const ready = await driver.execute("return Boolean(document.querySelector('.nk-root'));");
      if (ready) return true;
    }
    return false;
  }, "main Wiii window", 90_000, 500);
}

const xdotool = (...argv) => execFileSync(args.xdotool, argv, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();

function chooserWindows() {
  try {
    return xdotool("search", "--onlyvisible", "--name", "Neko Chill").split("\n").filter(Boolean);
  } catch {
    return [];
  }
}

/** The folder chooser is a native GTK dialog outside the webview, so drive it through X11. */
async function pickFolderInGtkChooser(folder) {
  const [window] = await until(async () => {
    const found = chooserWindows();
    return found.length ? found : null;
  }, "native folder chooser", 30_000, 250);
  // CI's Xvfb has no window manager, so activation is best effort and focus is set directly.
  try { xdotool("windowactivate", "--sync", window); } catch { /* no EWMH window manager */ }
  xdotool("windowfocus", "--sync", window);
  xdotool("key", "--clearmodifiers", "ctrl+l");
  await new Promise((resolve) => setTimeout(resolve, 300));
  xdotool("type", "--delay", "20", `${folder}/`);
  await new Promise((resolve) => setTimeout(resolve, 300));
  xdotool("key", "Return");
  await until(async () => {
    if (!chooserWindows().includes(window)) return true;
    xdotool("key", "Return");
    return false;
  }, "native folder chooser to close", 15_000, 1_000);
}

function appProcesses() {
  try {
    return execFileSync("pgrep", ["-f", app], { encoding: "utf8" }).trim().split("\n").filter(Boolean);
  } catch {
    return [];
  }
}

function xauthority() {
  const candidate = process.env.XAUTHORITY ?? path.join(homedir(), ".Xauthority");
  return existsSync(candidate) ? candidate : undefined;
}

const appEnv = () => ({
  ...process.env,
  HOME: home,
  TMPDIR: path.join(home, "tmp"),
  XDG_CONFIG_HOME: path.join(home, ".config"),
  XDG_DATA_HOME: path.join(home, ".local/share"),
  XDG_CACHE_HOME: path.join(home, ".cache"),
  NEKO_AUTO_UPDATE: "0",
  // HOME is isolated, so keep the X server cookie reachable.
  ...(xauthority() ? { XAUTHORITY: xauthority() } : {}),
});

/**
 * Wiii gives the bundled Neko 10 seconds to answer its startup probe. On a cold CI disk the
 * first start of the large single-file binary can take longer, so load it once beforehand.
 */
function warmBundledNeko() {
  const neko = path.join(path.dirname(app), "runtime/neko/neko");
  if (!existsSync(neko)) throw new Error(`no bundled Neko next to the app at ${neko}`);
  const started = Date.now();
  const version = execFileSync(neko, ["--version"], { env: appEnv(), encoding: "utf8", timeout: 120_000 }).trim();
  log(`bundled Neko ${version} answered in ${Date.now() - started} ms`);
}

function startTauriDriver() {
  const child = spawn(args.driver, ["--port", args.port], {
    env: appEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  const driverLog = path.join(artifacts, "tauri-driver.log");
  let buffered = "";
  const sink = (chunk) => {
    buffered += chunk;
    writeFileSync(driverLog, buffered);
  };
  child.stdout.on("data", sink);
  child.stderr.on("data", sink);
  return child;
}

async function launch(base) {
  await until(() => fetch(`${base}/status`).then(() => true), "tauri-driver to listen", 30_000, 250);
  const driver = await WebDriver.start(base, app);
  await focusMainWindow(driver);
  return driver;
}

async function closeApp(driver) {
  await driver.quit().catch((error) => log(`quit: ${error.message}`));
  await until(async () => appProcesses().length === 0, "previous Wiii process to exit", 30_000, 250);
}

async function main() {
  const model = await startFixtureModel();
  // An active Neko profile is what Wiii's model picker selects by default.
  writeFileSync(path.join(home, ".neko-core/config.json"), JSON.stringify({
    active_profile: "wiii-e2e",
    profiles: {
      "wiii-e2e": {
        provider: "openai_compat", label: "Wiii E2E loopback", auth: "none",
        base_url: `http://127.0.0.1:${model.port}/v1`, model: "wiii-e2e-model", models: ["wiii-e2e-model"],
      },
    },
    mode: "default", dream_mode: "off", auto_update: false, auto_update_check: false,
    max_retries: 0, timeout_seconds: 60,
  }, null, 2));
  warmBundledNeko();
  const tauriDriver = startTauriDriver();
  const base = `http://127.0.0.1:${args.port}`;
  let driver;
  try {
    log("launching Wiii");
    driver = await launch(base);
    await capture(driver, "first-launch");

    log("opening a project");
    await driver.click(await element(driver, '[data-testid="overview-create-first-project"], [data-testid="create-first-project"]'));
    await element(driver, '[data-testid="project-dialog"]');
    await driver.click(await element(driver, '[data-testid="project-dialog-add-folder"]'));
    await pickFolderInGtkChooser(project);
    await waitText(driver, project, "selected project folder");
    await capture(driver, "project-dialog");
    await driver.click(await element(driver, '[data-testid="project-dialog-primary"]'));
    await element(driver, '[data-testid="project-home-input"]', "project home");

    log("sending the first prompt");
    await waitText(driver, "wiii-e2e-model", "loopback Neko profile in the model picker", 60_000);
    await typeInto(driver, '[data-testid="project-home-input"]', PERMISSION_PROMPT);
    await clickEnabled(driver, await elementWithText(driver, "button", "Gửi và mở phiên"));

    log("approving the permission request");
    await element(driver, '[data-testid="permission-card"]', "permission card", 60_000);
    await waitText(driver, "write_file", "write_file permission preview");
    await capture(driver, "permission-card");
    await driver.click(await elementWithText(driver, '[data-testid="permission-card"] button', "Allow once"));
    await waitText(driver, MARKERS.permissionDone, "answer after approval", 60_000);
    const written = path.join(project, APPROVED_FILE);
    await until(() => existsSync(written), "approved file on disk");
    if (readFileSync(written, "utf8") !== APPROVED_CONTENT) throw new Error("approved file has unexpected content");
    await capture(driver, "permission-approved");

    log("starting a slow turn, queueing a follow-up and cancelling");
    await until(async () => !(await driver.findAll('[data-testid="neko-cancel"]')).length, "first turn to finish");
    await typeInto(driver, '[data-testid="neko-composer-input"]', SLOW_PROMPT);
    await clickEnabled(driver, await element(driver, '[data-testid="neko-send"]'));
    await until(() => model.requests.some((request) => request.user.includes(MARKERS.slow)), "slow turn to reach the model", 60_000);
    await element(driver, '[data-testid="neko-cancel"]', "running turn cancel control");
    await typeInto(driver, '[data-testid="neko-composer-input"]', QUEUED_TEXT);
    await clickEnabled(driver, await elementWithText(driver, "button", "Xếp hàng tin nhắn"));
    await element(driver, '[data-testid="neko-outbox-row"]', "queued outbox row");
    await capture(driver, "outbox-queued");
    await driver.click(await element(driver, '[data-testid="neko-cancel"]'));
    await until(async () => !(await driver.findAll('[data-testid="neko-cancel"]')).length, "turn cancellation", 30_000);
    await elementWithText(driver, '[data-testid="neko-outbox"] button', "Tiếp tục hàng đợi", "outbox paused after cancel");
    await capture(driver, "cancelled");
    if (model.requests.some((request) => request.user.includes("E2E_QUEUED"))) {
      throw new Error("the queued follow-up reached the model after cancellation");
    }

    log("restarting Wiii");
    await closeApp(driver);
    driver = await launch(base);
    await capture(driver, "after-restart");
    // The session may be listed in the sidebar, the overview catalog or both, depending on window width.
    const row = await clickableWithText(driver, '.nk-session-row button, [data-testid="neko-overview"] button',
      MARKERS.permission, "persisted session in the sidebar or overview", 60_000);
    await driver.click(row);
    await waitText(driver, MARKERS.permissionDone, "restored transcript", 60_000);
    await element(driver, '[data-testid="neko-outbox-row"]', "persisted outbox row", 30_000);
    await waitText(driver, "Wiii đã mở lại", "outbox paused by restart");
    await until(() => driver.execute(`
      return [...document.querySelectorAll('[data-testid="neko-outbox-row"] button[title]')]
        .some((node) => node.getAttribute("title") === arguments[0]);`, [QUEUED_TEXT]), "queued text after restart");
    // WebDriver ends the app without its graceful exit, so recovery must fail closed rather than resume.
    await waitText(driver, "Lần chạy native có kết quả chưa xác định", "fail-closed recovery notice");
    const outboxText = await driver.execute("return document.querySelector('[data-testid=\"neko-outbox\"]').innerText;");
    await capture(driver, "restored-session-and-outbox");
    if (model.requests.some((request) => request.user.includes("E2E_QUEUED"))) {
      throw new Error("the queued follow-up was delivered without user review after restart");
    }
    log(`outbox after restart: ${outboxText.replace(/\s+/g, " ").trim()}`);
    writeFileSync(path.join(artifacts, "model-requests.json"), JSON.stringify(model.requests, null, 2));
    log("PASS");
  } catch (error) {
    if (driver) {
      await capture(driver, "failure");
      // textContent includes collapsed <details>, where Wiii puts the Neko probe error.
      const body = await driver.execute("return document.body ? document.body.textContent : '';")
        .catch((reason) => `body unavailable: ${reason.message}`);
      writeFileSync(path.join(artifacts, "failure-body.txt"), body);
      const details = await driver.execute("return [...document.querySelectorAll('details')].map((node) => node.textContent.trim()).join('\\n');")
        .catch(() => "");
      if (details) log(`page details at failure:\n${details}`);
      const providers = await driver.executeAsync(`
        const done = arguments[arguments.length - 1];
        window.__TAURI_INTERNALS__.invoke("neko_control_provider_list", { providerId: "neko" })
          .then((value) => done(JSON.stringify(value)), (reason) => done("error: " + reason));`, [])
        .catch((reason) => `unavailable: ${reason.message}`);
      log(`Neko provider probe at failure: ${providers}`);
    }
    writeFileSync(path.join(artifacts, "model-requests.json"), JSON.stringify(model.requests, null, 2));
    throw error;
  } finally {
    if (driver) await driver.quit().catch(() => {});
    tauriDriver.kill("SIGTERM");
    await model.close();
    if (!args.keep) rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
}

main().catch((error) => {
  console.error(`[native-e2e] FAIL: ${error.stack ?? error}`);
  process.exitCode = 1;
});
