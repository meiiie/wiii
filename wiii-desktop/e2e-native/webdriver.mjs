/** Minimal W3C WebDriver client for tauri-driver; no third-party dependency. */
const ELEMENT = "element-6066-11e4-a23e-4d1d6b4f4f8d";

/** WebKitWebDriver may use the W3C or the legacy JSON Wire element key. */
export function elementId(reference) {
  if (!reference || typeof reference !== "object") return null;
  return reference[ELEMENT] ?? reference.ELEMENT ?? Object.values(reference)[0] ?? null;
}

export class WebDriver {
  constructor(base, sessionId) {
    this.base = base;
    this.sessionId = sessionId;
  }

  static async request(base, method, path, body) {
    const response = await fetch(base + path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok || payload.value?.error) {
      const error = new Error(`${method} ${path}: ${payload.value?.error ?? response.status} ${payload.value?.message ?? text}`);
      error.code = payload.value?.error;
      throw error;
    }
    return payload.value;
  }

  static async start(base, application, env = {}) {
    const value = await WebDriver.request(base, "POST", "/session", {
      capabilities: { alwaysMatch: { browserName: "wry", "tauri:options": { application, env } } },
    });
    return new WebDriver(base, value.sessionId);
  }

  call(method, path, body) {
    return WebDriver.request(this.base, method, `/session/${this.sessionId}${path}`, body);
  }

  quit() { return this.call("DELETE", ""); }
  handles() { return this.call("GET", "/window/handles"); }
  switchTo(handle) { return this.call("POST", "/window", { handle }); }
  title() { return this.call("GET", "/title"); }
  url() { return this.call("GET", "/url"); }
  screenshot() { return this.call("GET", "/screenshot"); }
  execute(script, args = []) { return this.call("POST", "/execute/sync", { script, args }); }
  executeAsync(script, args = []) { return this.call("POST", "/execute/async", { script, args }); }

  async findAll(css) {
    const found = await this.call("POST", "/elements", { using: "css selector", value: css });
    return found.map(elementId);
  }

  click(id) { return this.call("POST", `/element/${id}/click`, {}); }
  type(id, text) { return this.call("POST", `/element/${id}/value`, { text }); }
  clear(id) { return this.call("POST", `/element/${id}/clear`, {}); }
  text(id) { return this.call("GET", `/element/${id}/text`); }
  enabled(id) { return this.call("GET", `/element/${id}/enabled`); }
  displayed(id) { return this.call("GET", `/element/${id}/displayed`); }
}

export async function until(probe, label, timeoutMs = 30_000, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let last;
  for (;;) {
    try {
      const value = await probe();
      if (value) return value;
    } catch (error) {
      last = error;
    }
    if (Date.now() > deadline) {
      throw new Error(`Timed out waiting for ${label}${last ? `: ${last.message}` : ""}`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
