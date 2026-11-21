/** Loopback OpenAI-compatible model for the native E2E. It never calls the network. */
import { createServer } from "node:http";

export const MARKERS = {
  permission: "E2E_PERMISSION",
  permissionDone: "WIII_E2E_PERMISSION_DONE",
  slow: "E2E_SLOW",
  slowStarted: "WIII_E2E_SLOW_STARTED",
  generic: "WIII_E2E_OK",
};
export const APPROVED_FILE = "wiii-e2e-approved.txt";
export const APPROVED_CONTENT = "approved through the Wiii permission card\n";

function textOf(message) {
  if (!message) return "";
  if (typeof message.content === "string") return message.content;
  if (Array.isArray(message.content)) return message.content.map((part) => part?.text ?? "").join("");
  return "";
}

export function startFixtureModel() {
  const requests = [];
  const open = new Set();
  const server = createServer((request, response) => {
    let body = "";
    request.on("data", (chunk) => { body += chunk; });
    request.on("end", () => {
      if (!request.url?.endsWith("/chat/completions")) {
        response.writeHead(404).end();
        return;
      }
      const parsed = JSON.parse(body || "{}");
      const messages = Array.isArray(parsed.messages) ? parsed.messages : [];
      const last = messages.at(-1);
      const lastUser = [...messages].reverse().find((message) => message.role === "user");
      const userText = textOf(lastUser);
      requests.push({ model: parsed.model, role: last?.role, user: userText.slice(0, 200) });
      const chunk = (delta, finish) => `data: ${JSON.stringify({
        id: "wiii-e2e", object: "chat.completion.chunk", model: "wiii-e2e-model",
        choices: [{ index: 0, delta, finish_reason: finish }],
      })}\n\n`;
      response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
      const finish = (text) => {
        response.write(chunk({ role: "assistant", content: text }, null));
        response.write(chunk({}, "stop"));
        response.end("data: [DONE]\n\n");
      };
      const toolCall = (name, args) => {
        response.write(chunk({
          role: "assistant",
          tool_calls: [{
            index: 0, id: `call_wiii_e2e_${name}_${requests.length}`, type: "function",
            function: { name, arguments: JSON.stringify(args) },
          }],
        }, null));
        response.write(chunk({}, "tool_calls"));
        response.end("data: [DONE]\n\n");
      };
      const previousTool = last?.role === "tool"
        ? messages.at(-2)?.tool_calls?.at(-1)?.function?.name
        : undefined;
      const verificationNudge = /OUTCOME VERIFICATION REQUIRED|NO VERIFICATION EVIDENCE/.test(userText);
      if (previousTool === "write_file") {
        finish("Wrote the approval file.");
        return;
      }
      if (previousTool === "read_file") {
        finish(`${MARKERS.permissionDone}: the approval file was written and read back.`);
        return;
      }
      if (verificationNudge && last?.role === "user") {
        toolCall("read_file", { path: APPROVED_FILE });
        return;
      }
      if (userText.includes(MARKERS.permission) && last?.role === "user") {
        toolCall("write_file", { path: APPROVED_FILE, content: APPROVED_CONTENT });
        return;
      }
      if (userText.includes(MARKERS.slow) && last?.role === "user") {
        // Hold the turn open until Wiii cancels it.
        response.write(chunk({ role: "assistant", content: `${MARKERS.slowStarted} ` }, null));
        open.add(response);
        const timer = setTimeout(() => response.end(), 120_000);
        response.on("close", () => { clearTimeout(timer); open.delete(response); });
        return;
      }
      finish(MARKERS.generic);
    });
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({
    server,
    requests,
    port: server.address().port,
    close: () => new Promise((done) => {
      for (const response of open) response.destroy();
      server.close(() => done());
    }),
  })));
}
