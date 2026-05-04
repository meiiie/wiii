/**
 * Phase 32 — Multi-turn context debug spec.
 *
 * Drives the live desktop UI on http://localhost:1420 to verify that
 * a follow-up turn within the same conversation actually carries the
 * SAME session_id over the wire to the backend. The API-level probe
 * (curl with hand-crafted session_id) already confirmed the backend
 * memory layer + ChatService stitch turns correctly when session_id
 * is stable. The remaining hypothesis is that the desktop UI generates
 * a fresh id for each turn, so the model never sees prior context.
 *
 * What this test asserts:
 *   1. Login screen → click "Đăng nhập dev" → main UI renders.
 *   2. Send turn 1, capture POST body → ``session_id`` field.
 *   3. Send turn 2 in the SAME conversation, capture POST body.
 *   4. Both turns must carry an identical session_id string.
 *
 * If the assertion fails, the bug is on the frontend: the chat-store
 * is not stamping conversations with a stable session_id, or the
 * payload constructor in ``useSSEStream.ts`` is reading a fresh id
 * for each request.
 */
import { test, expect, type Request } from "@playwright/test";

const BASE_URL = "http://localhost:1420";

// Capture the JSON body of every chat/stream/v3 POST so we can read
// the session_id deterministically (the body is consumed by the SSE
// reader, so we cannot read it from the response).
function captureChatPosts(page: import("@playwright/test").Page) {
  const captured: Array<{ session_id: string; message: string }> = [];
  page.on("request", (req: Request) => {
    if (
      req.method() === "POST" &&
      req.url().includes("/api/v1/chat/stream/v3")
    ) {
      const body = req.postData() || "{}";
      try {
        const parsed = JSON.parse(body);
        captured.push({
          session_id: parsed.session_id || "",
          message: parsed.message || "",
        });
      } catch {
        captured.push({ session_id: "", message: "[unparseable body]" });
      }
    }
  });
  return captured;
}

test("multi-turn within same conversation shares session_id", async ({
  page,
}) => {
  const captured = captureChatPosts(page);

  // Clear any stale localStorage from prior sessions so the login
  // screen renders fresh. The Phase 31 fix means a stale legacy
  // api_key would otherwise leave us in the broken trap state.
  await page.goto(BASE_URL);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.reload();

  // Wait for the dev-login button (data-testid is the stable hook).
  // The visible label is "Đăng nhập nhanh — Local Dev" but we go by
  // testid to survive copy edits.
  const devLoginButton = page.getByTestId("dev-login-button");
  await devLoginButton.waitFor({ state: "visible", timeout: 30_000 });
  await devLoginButton.click();

  // Wait for the chat composer to be ready. The textarea uses
  // aria-label="Nhập tin nhắn" — stable hook independent of the
  // welcome-placeholder rotation.
  const composer = page.getByLabel("Nhập tin nhắn");
  await composer.waitFor({ state: "visible", timeout: 60_000 });

  // ── Turn 1 ──
  await composer.fill("Tên mình là Hùng");
  await composer.press("Enter");

  // Wait for the assistant response to finish — the streaming step
  // returns to idle (composer becomes editable again).
  await page.waitForTimeout(8_000);
  await page.waitForFunction(
    () => {
      const c = document.querySelector(
        "textarea, [contenteditable]",
      ) as HTMLElement | null;
      return c?.getAttribute("aria-disabled") !== "true";
    },
    { timeout: 60_000 },
  );

  // ── Turn 2 ──
  await composer.fill("Mình tên là gì?");
  await composer.press("Enter");
  await page.waitForTimeout(8_000);

  // ── Assertions ──
  // We expect two captured POSTs.
  expect(captured.length).toBeGreaterThanOrEqual(2);

  const turn1 = captured[0];
  const turn2 = captured[1];

  console.log(
    "[multi-turn-context] turn1 session_id =",
    turn1.session_id,
    "msg =",
    turn1.message,
  );
  console.log(
    "[multi-turn-context] turn2 session_id =",
    turn2.session_id,
    "msg =",
    turn2.message,
  );

  // Both messages must round-trip.
  expect(turn1.message).toContain("Hùng");
  expect(turn2.message).toContain("gì?");

  // The hard assertion — same conversation must carry same session_id.
  expect(turn1.session_id).toBeTruthy();
  expect(turn2.session_id).toBe(turn1.session_id);
});
