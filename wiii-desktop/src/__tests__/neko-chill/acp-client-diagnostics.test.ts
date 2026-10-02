import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AcpJsonRpcClient, type AcpTransport } from "@/neko-chill/drivers/acp/client";
import { AcpProtocolError, AcpRpcError, AcpTransportError, projectAcpFailure, projectDiagnosticData, safeDiagnosticText } from "@/neko-chill/drivers/acp/errors";

class Transport implements AcpTransport {
  sent: Array<Record<string, any>> = [];
  sendError: Error | null = null;
  line = (_line: string) => {};
  exited = (_code: number | null) => {};
  async send(line: string) { if (this.sendError) throw this.sendError; this.sent.push(JSON.parse(line)); }
  onLine(handler: (line: string) => void) { this.line = handler; }
  onExit(handler: (code: number | null) => void) { this.exited = handler; }
  async kill() {}
  inject(frame: unknown) { this.line(JSON.stringify(frame)); }
}

function setup() {
  const transport = new Transport();
  const handlers = { onAgentRequest: vi.fn(async () => ({})), onNotification: vi.fn(), onProtocolError: vi.fn() };
  return { transport, handlers, client: new AcpJsonRpcClient(transport, handlers) };
}

describe("ACP diagnostic correlation and error boundaries", () => {
  it.each([-32700, -32600, -32601, -32602, -32603, -32055, 42])("retains code %s and a bounded structured provider response", async (code) => {
    const { client, transport } = setup();
    const result = client.request("session/prompt", {}).catch(error => error);
    transport.inject({ id: 1, error: { code, message: "upstream operation failed", data: { statusCode: 400, details: "duplicate tool result", retryable: false, unknown: "do-not-retain" } } });
    const error = await result;
    expect(error).toBeInstanceOf(AcpRpcError);
    expect(error).toMatchObject({ kind: "rpc", code, requestId: 1, method: "session/prompt", dataPresent: true, data: { statusCode: 400, details: "duplicate tool result", retryable: false } });
    expect(error.data).not.toHaveProperty("unknown");
    expect(error.message).toContain(String(code));
    expect(error.message).toContain("duplicate tool result");
    expect(transport.sent).toHaveLength(1);
  });

  it.each([undefined, null, "untyped", [], { message: { token: "synthetic-only" }, code: "-32603", data: "raw-body" }])("unknown/malformed payload remains a failure without guessing denial: %j", async (errorPayload) => {
    const { client, transport } = setup();
    const result = client.request("session/prompt", {}).catch(error => error);
    transport.inject({ id: 1, error: errorPayload === undefined ? {} : errorPayload });
    const error = await result;
    expect(error).toBeInstanceOf(Error);
    expect(error.kind).toMatch(/rpc|protocol/);
    expect(error.message.length).toBeLessThan(1200);
    expect(transport.sent).toHaveLength(1);
  });

  it("projects allowlisted data only and redacts nested credentials before truncation", () => {
    const error = new AcpRpcError(4, "session/prompt", { code: -32603, message: "Internal error", data: { headers: { Authorization: "Bearer synthetic-private" }, request: { body: "private" }, error: { statusCode: 401, details: "a".repeat(700) + " api_key=synthetic-secret", raw: "private" }, __proto__: { polluted: true } } });
    const projection = projectAcpFailure(error);
    expect(error.data?.error).toMatchObject({ statusCode: 401, details: "Chi tiết nhạy cảm đã được ẩn." });
    expect(JSON.stringify(projection)).not.toMatch(/synthetic-private|synthetic-secret|Authorization|headers|private|polluted/);
    expect(Object.getPrototypeOf(error.data!)).toBeNull();
    expect(projection.diagnostic).toMatchObject({ category: "rpc-response", code: -32603, requestId: 4 });
  });

  it("omits arbitrary data strings, payload bodies and unknown keys", () => {
    expect(projectDiagnosticData("opaque secret")).toBeUndefined();
    expect(projectDiagnosticData({ raw: "secret", body: "private", stack: "private" })).toBeUndefined();
    expect(safeDiagnosticText('400 {"error":{"messages":"private"}}')).toContain("đã được ẩn");
  });

  it("never invokes getters and caps recursive data and oversized prose", () => {
    const getter = vi.fn(() => { throw new Error("must not run"); });
    const data: Record<string, unknown> = {};
    Object.defineProperty(data, "details", { get: getter });
    data.error = data;
    expect(projectDiagnosticData(data)).toBeUndefined();
    expect(getter).not.toHaveBeenCalled();
    expect(safeDiagnosticText("x".repeat(4096) + " token=secret")).toContain("đã được ẩn");
    expect(JSON.stringify(projectDiagnosticData({ details: "漢😀".repeat(600) })).length).toBeLessThan(2048);
  });

  it("keeps Unicode intact, removes bidi/control and makes Markdown links inert", () => {
    const unicode = safeDiagnosticText("😀漢Tiếng Việt".repeat(10), 7);
    expect(Array.from(unicode)).toHaveLength(8);
    expect(unicode).not.toMatch(/[\ud800-\udbff]$/);
    const failure = projectAcpFailure(new AcpRpcError(1, "session/prompt", { code: -32055, message: "[open](/private) ![image](https://user:pass@host/path?key=value#fragment)\u202e\n<script>" }));
    expect(failure.message).toContain("\\[open\\]");
    expect(failure.message).not.toMatch(/https:|user:pass|key=value|\u202e|\n|<script>/);
  });

  it("renders diagnostic links and images as inert text with actual GFM", () => {
    const failure = projectAcpFailure(new AcpRpcError(1, "session/prompt", { code: -32055,
      message: "See www.example.invalid/support email user@example.invalid [open](/private) ![img](https://host.invalid/image)",
      data: { details: "Contact ops@example.invalid or www.example.invalid" },
    }));
    const html = renderToStaticMarkup(createElement(ReactMarkdown, { remarkPlugins: [remarkGfm], children: failure.message }));
    const container = document.createElement("div");
    container.innerHTML = html;
    expect(container.querySelectorAll("a,img,script")).toHaveLength(0);
    expect(container.textContent).toContain("đã ẩn");
    expect(container.textContent).not.toMatch(/ops@example|user@example|www\.example/);
  });

  it("distinguishes send/exit/timeout/disposal from RPC errors without retaining causes", async () => {
    const sent = setup();
    sent.transport.sendError = new Error("Authorization: Bearer synthetic-private");
    const sendError = await sent.client.request("session/prompt", {}).catch(error => error);
    expect(sendError).toBeInstanceOf(AcpTransportError);
    expect(sendError).toMatchObject({ reason: "send", requestId: 1 });
    expect(JSON.stringify(projectAcpFailure(sendError))).not.toContain("synthetic-private");
    const exit = setup();
    const exited = exit.client.request("session/prompt", {}).catch(error => error);
    exit.transport.exited(1);
    expect(await exited).toMatchObject({ kind: "transport", reason: "exit", method: "session/prompt" });
    const closed = setup();
    await closed.client.dispose();
    expect(await closed.client.request("session/prompt", {}).catch(error => error)).toMatchObject({ reason: "disposed", requestId: null });
    vi.useFakeTimers();
    try {
      const timed = setup();
      const timeout = timed.client.request("session/prompt", {}, 20).catch(error => error);
      await vi.advanceTimersByTimeAsync(20);
      expect(await timeout).toMatchObject({ kind: "transport", reason: "timeout", requestId: 1 });
    } finally { vi.useRealTimers(); }
  });

  it("reports malformed frames and unknown IDs without echoing their raw contents", () => {
    const { transport, handlers } = setup();
    transport.line('Authorization: Bearer synthetic-private');
    transport.inject(null);
    transport.inject([]);
    transport.inject({ id: "sk-synthetic-private", error: {} });
    expect(handlers.onProtocolError).toHaveBeenCalledTimes(4);
    expect(JSON.stringify(handlers.onProtocolError.mock.calls)).not.toContain("synthetic-private");
  });

  it("correlates a malformed response as a protocol fault rather than success", async () => {
    const { client, transport } = setup();
    const result = client.request("session/prompt", {}).catch(error => error);
    transport.inject({ id: 1, error: "not-an-error-object" });
    expect(await result).toBeInstanceOf(AcpProtocolError);
  });
});
