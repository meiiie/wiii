"""Linux-only ACP roundtrip using the pinned binary and a loopback model fixture.

Run with ``python -m tools.release.smoke_neko_bundle``. No external account or
model is used. A temporary HOME prevents reading or changing real Neko settings.
"""
from __future__ import annotations

import argparse
import http.server
import json
from pathlib import Path
import platform
import queue
import subprocess
import sys
import tempfile
import threading
import time

from tools.release.prepare_neko_bundle import DESTINATION, LOCK, check_bundle, manifest_for

MARKER = "WIII_BUNDLED_TRANSPORT_OK"
MAX_FRAME_CHARS = 64 * 1024
MAX_FRAMES = 256


def model_handler(requests: list[dict]):
    class FixtureModel(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 2 * 1024 * 1024:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(size))
            requests.append({"path": self.path, "model": body.get("model")})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in [({"role": "assistant", "content": MARKER}, None), ({}, "stop")]:
                chunk = {
                    "id": "fixture-completion", "object": "chat.completion.chunk",
                    "model": "fixture-model",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    return FixtureModel


def read_frames(stream, messages: queue.Queue) -> None:
    try:
        for _ in range(MAX_FRAMES):
            line = stream.readline(MAX_FRAME_CHARS + 1)
            if not line:
                raise RuntimeError("ACP process closed stdout before the requested response")
            if len(line) > MAX_FRAME_CHARS:
                raise RuntimeError("ACP frame exceeded the smoke-test budget")
            messages.put(json.loads(line))
        raise RuntimeError("ACP process exceeded the smoke-test frame count")
    except Exception as error:
        messages.put(error)


def exercise(binary: Path, home: Path, port: int) -> dict:
    project = home / "project"
    for directory in (project, home / "tmp", home / ".neko-core"):
        directory.mkdir()
    config = {
        "provider": "openai_compat", "base_url": f"http://127.0.0.1:{port}/v1",
        "model": "fixture-model", "api_key": "fixture-not-a-secret",
        "auto_update": False, "auto_update_check": False,
        "max_retries": 0, "timeout_seconds": 10,
    }
    (home / ".neko-core/config.json").write_text(json.dumps(config), encoding="utf-8")
    command = [
        "bwrap", "--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev",
        "--proc", "/proc", "--bind", str(home), str(home),
        "--unshare-pid", "--as-pid-1", "--die-with-parent", "--", str(binary), "acp",
    ]
    environment = {
        "PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home / "tmp"),
        "NEKO_AUTO_UPDATE": "0",
    }
    process = subprocess.Popen(
        command, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    )
    messages = queue.Queue()
    observed = []
    reader = threading.Thread(target=read_frames, args=(process.stdout, messages), daemon=True)
    reader.start()

    def request(request_id: int, method: str, params: dict):
        frame = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        process.stdin.write(json.dumps(frame) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 25
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ACP response deadline exceeded")
            message = messages.get(timeout=remaining)
            if isinstance(message, Exception):
                raise message
            observed.append(message)
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"ACP {method} failed: {message['error']}")
                return message["result"]

    try:
        initialized = request(1, "initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
            "clientInfo": {"name": "wiii-bundle-smoke", "version": "1"},
        })
        session = request(2, "session/new", {"cwd": str(project), "mcpServers": []})
        result = request(3, "session/prompt", {
            "sessionId": session["sessionId"],
            "prompt": [{"type": "text", "text": "Reply with the transport fixture marker. Do not call tools."}],
        })
        if MARKER not in json.dumps(observed) or result.get("stopReason") != "end_turn":
            raise RuntimeError("ACP roundtrip did not deliver and finish the fixture response")
        return {"agent": initialized["agentInfo"], "protocol": initialized["protocolVersion"],
                "session_created": True, "reply_marker_received": True, "stop_reason": result["stopReason"]}
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Killing the bwrap PID-namespace supervisor also terminates descendants.
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)
        process.stdout.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DESTINATION)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("This smoke requires Linux bubblewrap containment")
    target = {"x86_64": "linux-x64", "aarch64": "linux-arm64"}.get(platform.machine())
    if target is None:
        parser.error("No pinned Neko artifact for this host architecture")
    manifest = manifest_for(json.loads(LOCK.read_text(encoding="utf-8")), target)
    check_bundle(args.bundle, manifest)
    requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), model_handler(requests))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="wiii-neko-smoke-") as directory:
            result = exercise((args.bundle / "neko").resolve(), Path(directory), server.server_port)
            if (result["agent"].get("name") != "neko-core"
                    or result["agent"].get("version") != manifest["version"]
                    or result["protocol"] != 1):
                raise RuntimeError("ACP agent identity differs from the pinned runtime")
            if not requests or any(item["model"] != "fixture-model" for item in requests):
                raise RuntimeError("The expected loopback model fixture was not used")
            print(json.dumps({**result, "loopback_fixture_requests": len(requests), "external_model_calls": 0}))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
