"""
Minimal webhook verification server for Facebook Messenger Platform.
Run this temporarily to complete webhook verification on Facebook Developer Console.
"""

import http.server
import urllib.parse
import sys

VERIFY_TOKEN = "wiii_fb_verify_s3cr3t_2026"
PORT = 8000


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        hub_mode = params.get("hub.mode", [None])[0]
        hub_verify = params.get("hub.verify_token", [None])[0]
        hub_challenge = params.get("hub.challenge", [None])[0]

        if parsed.path == "/api/v1/messenger/webhook":
            if hub_mode == "subscribe" and hub_verify == VERIFY_TOKEN:
                print(f"[OK] Webhook verified! Challenge: {hub_challenge}")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(hub_challenge.encode())
                return

        # Health check
        if parsed.path == "/" or parsed.path == "/api/v1/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        self.send_response(403)
        self.end_headers()
        self.wfile.write(b"Verification failed")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        print(f"[POST] {self.path} — {body[:500]}")
        response = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(response)
        self.wfile.flush()


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = ThreadedHTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"Webhook verify server running on port {port}", flush=True)
    print(f"Verify token: {VERIFY_TOKEN}", flush=True)
    print(f"Endpoint: /api/v1/messenger/webhook", flush=True)
    server.serve_forever()
