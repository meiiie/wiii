/** Contract test: the real AcpDriver against the pinned Neko Core binary.
 * Runs only when WIII_NEKO_CONTRACT_BINARY points at a prepared bundle
 * (`python tools/release/prepare_neko_bundle.py --target linux-x64`).
 * A loopback OpenAI-compatible fixture is the only model; HOME is temporary.
 */
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { DurableOutbox, emptyOutbox, type OutboxSnapshot } from "@/neko-chill/durable-outbox";
import { normalizeSessionTitle } from "@/neko-chill/session-title";
import { AcpDriver } from "@/neko-chill/drivers/acp/driver";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { DriverEvent } from "@/neko-chill/drivers/types";
import { parseNekoTaskRecoveryError, type NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";

const BINARY = process.env.WIII_NEKO_CONTRACT_BINARY;
if (process.env.WIII_NEKO_CONTRACT_REQUIRED === "1" && !BINARY) {
  throw new Error("WIII_NEKO_CONTRACT_BINARY is required when WIII_NEKO_CONTRACT_REQUIRED=1");
}
const LOCK = JSON.parse(readFileSync(path.resolve(__dirname, "../../../src-tauri/neko-bundle.lock.json"), "utf8"));
const EXPECTED_VERSION = process.env.WIII_NEKO_CONTRACT_EXPECTED_VERSION ?? LOCK.version;
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

interface FixtureRequest { model: string; messages: Array<{ role: string; content?: unknown }> }
interface FixtureTool { name: string; arguments: Record<string, string> }
function fixtureModel(tool?: FixtureTool): Promise<{ server: Server; port: number; requests: string[]; bodies: FixtureRequest[] }> {
  const requests: string[] = [];
  const bodies: FixtureRequest[] = [];
  const server = createServer((request, response) => {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      const parsed = JSON.parse(body || "{}");
      bodies.push(parsed);
      requests.push(String(parsed.model));
      const last = JSON.stringify(parsed.messages?.at(-1) ?? "");
      const chunk = (delta: object, finish: string | null) => `data: ${JSON.stringify({
        id: "fixture", object: "chat.completion.chunk", model: "fixture-model",
        choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`;
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      if (tool && !parsed.messages.some((message: { role: string }) => message.role === "tool")) {
        response.write(chunk({ role: "assistant", tool_calls: [{ index: 0, id: "fixture-tool", type: "function",
          function: { name: tool.name, arguments: "" } }] }, null));
        response.write(chunk({ tool_calls: [{ index: 0, function: { arguments: JSON.stringify(tool.arguments) } }] }, null));
        response.write(chunk({}, "tool_calls"));
        response.end("data: [DONE]\n\n");
        return;
      }
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
    resolve({ server, port: (server.address() as AddressInfo).port, requests, bodies })));
}

async function until(predicate: () => boolean, label: string, ms = 20_000): Promise<void> {
  await vi.waitFor(() => expect(predicate(), label).toBe(true), { timeout: ms, interval: 25 });
}

describe.skipIf(!BINARY)("Neko Core ACP desktop contracts (real binary)", () => {
  let home: string;
  let root: string;
  let model: Awaited<ReturnType<typeof fixtureModel>>;
  const live: ProcessTransport[] = [];

  beforeEach(() => {
    home = realpathSync(mkdtempSync(path.join(tmpdir(), "wiii-neko-desktop-contract-")));
    root = path.join(home, "scratch");
    mkdirSync(root, { mode: 0o700 });
    mkdirSync(path.join(home, "tmp"));
    mkdirSync(path.join(home, ".neko-core"));
  });

  afterEach(async () => {
    await Promise.all(live.splice(0).map(transport => transport.kill()));
    if (model) await new Promise<void>((resolve, reject) => model.server.close(error => error ? reject(error) : resolve()));
    rmSync(home, { recursive: true, force: true });
  });

  async function configure(tool?: FixtureTool, mode = "auto") {
    model = await fixtureModel(tool);
    writeFileSync(path.join(home, ".neko-core/config.json"), JSON.stringify({
      provider: "openai_compat", base_url: `http://127.0.0.1:${model.port}/v1`,
      model: "fixture-model", api_key: "fixture-not-a-secret", mode, dream_mode: "off",
      auto_update: false, auto_update_check: false, verify_before_exit: false, max_retries: 0, timeout_seconds: 30,
    }));
  }

  function driverFor(resume?: { sessionId: string; receipt: NekoTaskReceipt }) {
    const transport = new ProcessTransport(BINARY!, home);
    live.push(transport);
    const events: DriverEvent[] = [];
    const admitted: Array<{ sessionId: string; receipt: NekoTaskReceipt }> = [];
    const driver = new AcpDriver({ sessionId: "wiii-scratch-thread", cwd: root, transport,
      resumeSessionId: resume?.sessionId, onEvent: event => events.push(event),
      taskScope: { authorizedRoot: root, label: LABEL, expectedReceipt: resume?.receipt,
        onAdmitted: async (sessionId, receipt) => { admitted.push({ sessionId, receipt }); } } });
    return { driver, events, admitted,
      answer: () => events.flatMap(event => event.type === "answer-delta" ? [event.text] : []).join(""),
      finished: () => events.flatMap(event => event.type === "turn-finished" ? [event.stopReason] : []),
      titles: () => events.flatMap(event => event.type === "session-info" && event.title ? [event.title] : []),
    };
  }

  it("projects a completed read tool and sends its result back to the model", async () => {
    writeFileSync(path.join(root, "evidence.txt"), "READ_TOOL_EVIDENCE");
    await configure({ name: "read_file", arguments: { path: "evidence.txt" } });
    const h = driverFor();
    await h.driver.start();
    await h.driver.prompt("Read the fixture evidence.");
    expect(h.finished()).toEqual(["end_turn"]);
    expect(h.answer()).toContain(MARKER);
    expect(h.events).toContainEqual(expect.objectContaining({ type: "activity", activity: expect.objectContaining({
      id: "fixture-tool", toolName: "read_file", status: "completed", operation: "read",
    }) }));
    expect(model.bodies).toHaveLength(2);
    expect(JSON.stringify(model.bodies[1].messages.filter(message => message.role === "tool"))).toContain("READ_TOOL_EVIDENCE");
    await h.driver.dispose();
  });

  for (const choice of ["allow_once", "reject_once"] as const) {
    it(`${choice} resolves a real write approval without hanging the turn`, async () => {
      // Neko 1.9.3 core/permissions.ts: default prompts for gated write_file.
      await configure({ name: "write_file", arguments: { path: "approved.txt", content: "APPROVED_WRITE" } }, "default");
      const h = driverFor();
      await h.driver.start();
      const turn = h.driver.prompt("Write the fixture file.");
      try {
        await until(() => h.events.some(event => event.type === "permission-request"), "write permission");
        const event = h.events.find(event => event.type === "permission-request");
        if (event?.type !== "permission-request") throw new Error("Missing permission request");
        expect(event.request.activityId).toBe("fixture-tool");
        expect(event.request.options.map(option => option.kind)).toEqual(["allow_once", "allow_always", "reject_once", "reject_always"]);
        const option = event.request.options.find(option => option.kind === choice)!;
        expect(option.optionId).not.toBe("");
        await h.driver.resolvePermission({ requestId: event.request.requestId, optionId: option.optionId });
        await turn;
        expect(h.finished()).toEqual(["end_turn"]);
        expect(h.answer()).toContain(MARKER);
        expect(existsSync(path.join(root, "approved.txt"))).toBe(choice === "allow_once");
        if (choice === "allow_once") expect(readFileSync(path.join(root, "approved.txt"), "utf8")).toBe("APPROVED_WRITE");
        expect(model.bodies.length).toBeGreaterThanOrEqual(2);
        expect(JSON.stringify(model.bodies[1].messages.filter(message => message.role === "tool")))
          .toContain(choice === "allow_once" ? "Wrote approved.txt" : "Denied by user");
      } finally {
        await h.driver.dispose();
        await turn.catch(() => {});
      }
    });
  }

  for (const firstLine of ["Name this conversation", "A long first prompt whose title must exceed sixty characters and retain a visible truncation marker"]) {
    it(`preserves the first-line title across cold resume (${firstLine.length} characters)`, async () => {
      await configure();
      const h = driverFor();
      await h.driver.start();
      await h.driver.prompt(`${firstLine}\nThis second line is not the title.`);
      const accepted = firstLine.length > 60
        ? [`${firstLine.slice(0, 45)}... [truncated]`, `${firstLine.slice(0, 59).trimEnd()}…`]
        : [firstLine];
      await until(() => h.titles().some(title => accepted.includes(title)), "first-line session title");
      const expected = h.titles().find(title => accepted.includes(title))!;
      expect(normalizeSessionTitle(expected)).toBe(expected.endsWith("... [truncated]")
        ? `${firstLine.slice(0, 45)}…` : expected);
      await h.driver.dispose();
      const resumed = driverFor(h.admitted[0]);
      await resumed.driver.start();
      expect(resumed.titles()).toContain(expected);
      expect(normalizeSessionTitle(resumed.titles().find(title => title === expected)!)).toBe(normalizeSessionTitle(expected));
      await resumed.driver.dispose();
    });
  }

  it("writes relative to an empty private scratch cwd without claiming OS confinement", async () => {
    expect(readdirSync(root)).toEqual([]);
    if (process.platform !== "win32") expect(statSync(root).mode & 0o777).toBe(0o700);
    await configure({ name: "write_file", arguments: { path: "scratch.txt", content: "SCRATCH_WRITE" } });
    const h = driverFor();
    await h.driver.start();
    await h.driver.prompt("Write in the scratch working directory.");
    expect(h.finished()).toEqual(["end_turn"]);
    expect(readFileSync(path.join(root, "scratch.txt"), "utf8")).toBe("SCRATCH_WRITE");
    expect(existsSync(path.join(home, "scratch.txt"))).toBe(false);
    // Pinned Neko permits ordinary outside structured writes in auto mode; cwd is not a sandbox.
    expect(h.driver.runtime.workspaceIsolation).toBe("advisory");
    await h.driver.dispose();
  });

  it("cold-resumes a durable queued prompt exactly once and holds uncertain delivery", async () => {
    await configure();
    const h = driverFor();
    await h.driver.start();
    const binding = { sessionId: "wiii-scratch-thread", workspace: root,
      task: `scratch-run:${root}`, model: JSON.stringify([null, []]) };
    let persisted: OutboxSnapshot = emptyOutbox();
    const storage = { read: async () => structuredClone(persisted),
      write: async (value: OutboxSnapshot) => { persisted = structuredClone(value); } };
    const original = new DurableOutbox(storage, () => {});
    await original.hydrate();
    const queuedPrompt = "Reply with the fixture marker for this queued prompt.";
    await original.enqueue(binding, queuedPrompt, "queued-prompt");
    await h.driver.dispose();

    const resumed = driverFor(h.admitted[0]);
    await resumed.driver.start();
    const restarted = new DurableOutbox(storage, () => {});
    await restarted.hydrate();
    const send = vi.fn(async (text: string, accepted: () => void) => {
      accepted();
      await resumed.driver.prompt(text);
      return resumed.finished().at(-1) === "end_turn";
    });
    await restarted.dispatch(binding.sessionId, () => binding, () => true, send);
    expect(model.bodies).toHaveLength(0);
    expect(restarted.snapshot.queues[0].paused).toBe(true);
    await restarted.resume(binding.sessionId);
    await restarted.dispatch(binding.sessionId, () => binding, () => true, send);
    await restarted.dispatch(binding.sessionId, () => binding, () => true, send);
    expect(model.bodies).toHaveLength(1);
    expect(JSON.stringify(model.bodies[0].messages)).toContain(queuedPrompt);
    expect(resumed.finished()).toEqual(["end_turn"]);
    expect(resumed.answer()).toContain(MARKER);
    expect(persisted.queues[0].items).toEqual([]);
    expect(send).toHaveBeenCalledTimes(1);

    await restarted.enqueue(binding, "Never replay an uncertain prompt.", "interrupted-prompt");
    await restarted.dispatch(binding.sessionId, () => binding, () => true, async () => {
      throw new Error("App stopped before delivery could be acknowledged");
    });
    expect(persisted.queues[0].items[0].state).toBe("delivering");
    const uncertain = new DurableOutbox(storage, () => {});
    await uncertain.hydrate();
    expect(uncertain.snapshot.queues[0].items[0].state).toBe("uncertain");
    await expect(uncertain.resume(binding.sessionId)).rejects.toThrow();
    await uncertain.dispatch(binding.sessionId, () => binding, () => true, send);
    expect(send).toHaveBeenCalledTimes(1);
    expect(model.bodies).toHaveLength(1);
    await resumed.driver.dispose();
  });
});

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
    expect(init?.result.agentInfo).toMatchObject({ name: "neko-core", version: EXPECTED_VERSION });
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
    await expect(h.driver.start()).rejects.toMatchObject({
      name: "NekoTaskProtocolError",
      reason: "activation-mismatch",
    });
    expect(h.admitted).toHaveLength(0);
    await expect(h.driver.prompt("must not run")).rejects.toThrow();
    await h.driver.dispose();
    expect(model.requests.every(name => name === "fixture-model")).toBe(true);
  });
});
