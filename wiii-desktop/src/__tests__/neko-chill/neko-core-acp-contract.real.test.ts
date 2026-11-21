/** Contract test: the real AcpDriver against the pinned Neko Core binary.
 * Runs only when WIII_NEKO_CONTRACT_BINARY points at a prepared bundle
 * (`python tools/release/prepare_neko_bundle.py --target linux-x64`).
 * A loopback OpenAI-compatible fixture is the only model; HOME is temporary.
 */
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { AcpDriver } from "@/neko-chill/drivers/acp/driver";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { DriverEvent } from "@/neko-chill/drivers/types";
import { parseNekoTaskRecoveryError, type NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";

const BINARY = process.env.WIII_NEKO_CONTRACT_BINARY;
const LOCK = JSON.parse(readFileSync(path.resolve(__dirname, "../../../src-tauri/neko-bundle.lock.json"), "utf8"));
const MARKER = "WIII_TASK_HANDOFF_OK";
const SLOW_MARKER = "WIII_SLOW_TURN_STARTED";
const LABEL = "Sửa lỗi bàn giao tác vụ";

class ProcessTransport implements AcpTransport {
  readonly frames: Array<Record<string, any>> = [];
  private readonly child: ChildProcessWithoutNullStreams;
  private readonly exited: Promise<void>;
  private stderr = "";
  constructor(binary: string, home: string) {
    this.child = spawn(binary, ["acp"], { cwd: home, stdio: ["pipe", "pipe", "pipe"], env: {
      PATH: "/usr/bin:/bin", HOME: home, TMPDIR: path.join(home, "tmp"), NEKO_AUTO_UPDATE: "0",
    } });
    this.child.stderr.on("data", chunk => { this.stderr = (this.stderr + chunk).slice(-4096); });
    this.exited = new Promise(resolve => this.child.once("exit", () => resolve()));
    createInterface({ input: this.child.stdout }).on("line", line => {
      try { this.frames.push(JSON.parse(line)); } catch { /* the client reports protocol errors */ }
    });
  }
  async send(line: string): Promise<void> {
    await new Promise<void>((resolve, reject) => this.child.stdin.write(line + "\n", error => error ? reject(error) : resolve()));
  }
  onLine(handler: (line: string) => void): void {
    createInterface({ input: this.child.stdout }).on("line", handler);
  }
  onExit(handler: (code: number | null, detail?: { stderrTail?: string | null }) => void): void {
    this.child.once("exit", code => handler(code, { stderrTail: this.stderr || null }));
  }
  async kill(): Promise<void> {
    if (this.child.exitCode === null && this.child.signalCode === null) this.child.kill("SIGTERM");
    await this.exited;
  }
}

function fixtureModel(): Promise<{ server: Server; port: number; requests: string[] }> {
  const requests: string[] = [];
  const server = createServer((request, response) => {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      const parsed = JSON.parse(body || "{}");
      requests.push(String(parsed.model));
      const last = JSON.stringify(parsed.messages?.at(-1) ?? "");
      const chunk = (delta: object, finish: string | null) => `data: ${JSON.stringify({
        id: "fixture", object: "chat.completion.chunk", model: "fixture-model",
        choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`;
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      if (last.includes("SLOW")) {
        // Hold the turn open until Wiii cancels it.
        response.write(chunk({ role: "assistant", content: SLOW_MARKER }, null));
        const timer = setTimeout(() => response.end(), 20_000);
        response.on("close", () => clearTimeout(timer));
        return;
      }
      response.write(chunk({ role: "assistant", content: MARKER }, null));
      response.write(chunk({}, "stop"));
      response.end("data: [DONE]\n\n");
    });
  });
  return new Promise(resolve => server.listen(0, "127.0.0.1", () =>
    resolve({ server, port: (server.address() as AddressInfo).port, requests })));
}

async function until(predicate: () => boolean, label: string, ms = 20_000): Promise<void> {
  const deadline = Date.now() + ms;
  while (!predicate()) {
    if (Date.now() > deadline) throw new Error(`Timed out waiting for ${label}`);
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}

describe.skipIf(!BINARY)("Neko Core ACP task-v1 contract (real binary)", () => {
  let home: string;
  let root: string;
  let model: Awaited<ReturnType<typeof fixtureModel>>;
  const live: ProcessTransport[] = [];

  beforeAll(async () => {
    model = await fixtureModel();
    home = realpathSync(mkdtempSync(path.join(tmpdir(), "wiii-neko-contract-")));
    root = path.join(home, "project");
    for (const directory of [root, path.join(home, "tmp"), path.join(home, ".neko-core")]) mkdirSync(directory);
    writeFileSync(path.join(home, ".neko-core/config.json"), JSON.stringify({
      provider: "openai_compat", base_url: `http://127.0.0.1:${model.port}/v1`,
      model: "fixture-model", api_key: "fixture-not-a-secret", dream_mode: "off",
      auto_update: false, auto_update_check: false, max_retries: 0, timeout_seconds: 30,
    }));
  });

  afterAll(async () => {
    await Promise.all(live.map(transport => transport.kill()));
    await new Promise(resolve => model?.server.close(resolve));
    if (home) rmSync(home, { recursive: true, force: true });
  });

  function driverFor(options: { resumeSessionId?: string; expectedReceipt?: NekoTaskReceipt } = {}) {
    const transport = new ProcessTransport(BINARY!, home);
    live.push(transport);
    const events: DriverEvent[] = [];
    const admitted: Array<{ sessionId: string; receipt: NekoTaskReceipt }> = [];
    const closed: string[] = [];
    const driver = new AcpDriver({ sessionId: "wiii-work-thread", cwd: root, transport,
      resumeSessionId: options.resumeSessionId, onEvent: event => events.push(event),
      taskScope: { authorizedRoot: root, label: LABEL, expectedReceipt: options.expectedReceipt,
        onAdmitted: async (sessionId, receipt) => { admitted.push({ sessionId, receipt }); },
        onCloseOutcome: outcome => { closed.push(outcome); } } });
    const answer = () => events.flatMap(event => event.type === "answer-delta" ? [event.text] : []).join("");
    const finished = () => events.flatMap(event => event.type === "turn-finished" ? [event.stopReason] : []);
    return { transport, driver, events, admitted, closed, answer, finished };
  }

  let sessionId = "";
  let firstReceipt: NekoTaskReceipt;
  let resumedReceipt: NekoTaskReceipt;

  it("advertises task-v1, admits a scoped session, prompts, cancels and closes cleanly", async () => {
    const h = driverFor();
    await h.driver.start();
    const init = h.transport.frames.find(frame => frame.id !== undefined && frame.result?.agentInfo);
    expect(init?.result.agentInfo).toMatchObject({ name: "neko-core", version: LOCK.version });
    expect(init?.result._meta["neko.taskProtocol"]).toEqual({ version: 1, mode: "fixed-active-task" });

    expect(h.admitted).toHaveLength(1);
    ({ sessionId, receipt: firstReceipt } = h.admitted[0]);
    expect(firstReceipt).toMatchObject({ version: 1, mode: "fixed-active-task", label: LABEL, root, activationEpoch: 1 });
    expect(h.driver.backendSessionId).toBe(sessionId);

    await h.driver.prompt("Reply with the fixture marker. Do not call tools.");
    expect(h.answer()).toContain(MARKER);
    expect(h.finished()).toEqual(["end_turn"]);

    await expect(h.driver.prompt("/task new other")).rejects.toThrow();

    const slow = h.driver.prompt("SLOW turn for cancellation");
    await until(() => h.answer().includes(SLOW_MARKER), "slow turn start");
    await h.driver.cancel();
    await slow;
    expect(h.finished()).toEqual(["end_turn", "cancelled"]);
    expect(h.events.some(event => event.type === "error")).toBe(false);

    await h.driver.dispose();
    expect(h.closed).toEqual(["acknowledged"]);
  });

  it("cold-resumes the task in a new process with a fresh activation", async () => {
    const h = driverFor({ resumeSessionId: sessionId, expectedReceipt: firstReceipt });
    await h.driver.start();
    expect(h.admitted).toHaveLength(1);
    resumedReceipt = h.admitted[0].receipt;
    expect(h.admitted[0].sessionId).toBe(sessionId);
    expect(resumedReceipt).toMatchObject({ id: firstReceipt.id, label: LABEL, root, activationEpoch: 2 });
    expect(resumedReceipt.activationId).not.toBe(firstReceipt.activationId);

    await h.driver.prompt("Reply with the fixture marker again.");
    expect(h.answer()).toContain(MARKER);
    expect(h.finished()).toEqual(["end_turn"]);

    // A second writer for the held task fails closed with a typed recovery error.
    const rival = driverFor({ resumeSessionId: sessionId, expectedReceipt: resumedReceipt });
    await expect(rival.driver.start()).rejects.toThrow();
    expect(rival.admitted).toHaveLength(0);
    const failure = rival.transport.frames.find(frame => frame.error?.code === -32002);
    expect(parseNekoTaskRecoveryError(failure?.error.code, failure?.error.data)).toEqual({
      version: 1, kind: "writer_unavailable", action: "retain_mapping_and_request_recovery" });
    await rival.driver.dispose();

    await h.driver.dispose();
    expect(h.closed).toEqual(["acknowledged"]);
  });

  it("refuses a stale receipt without admitting a prompt", async () => {
    const h = driverFor({ resumeSessionId: sessionId, expectedReceipt: firstReceipt });
    await expect(h.driver.start()).rejects.toThrow();
    expect(h.admitted).toHaveLength(0);
    await expect(h.driver.prompt("must not run")).rejects.toThrow();
    await h.driver.dispose();
    expect(model.requests.every(name => name === "fixture-model")).toBe(true);
  });
});
