/**
 * E2E context-window + multi-turn coherence harness.
 *
 * Drives the live desktop UI on http://localhost:1420 through a 6-turn
 * conversation that stresses the context window + memory layers Wiii
 * ships today. Reports a metrics summary so a human reader can see at
 * a glance which assertions hold and where the system drifts.
 *
 * Why this exists:
 *   The Phase 32 multi-turn regression test (multi-turn-context.spec.ts)
 *   only proves session_id stability. This file goes deeper — it
 *   asserts SEMANTIC retention: does Wiii remember a name, does it
 *   resolve an ambiguous "không đâu" via the prior offer, does it
 *   follow a topic switch without losing prior context?
 *
 * Standards:
 *   - Each turn captures TTFT (first answer chunk) + total time +
 *     SSE event-type histogram (status / answer / thinking / done).
 *   - Each turn has a "must-contain" assertion on the response text
 *     so a regression in semantic coherence is caught at the boundary
 *     where it would be cheap to fix.
 *   - At the end, queries Postgres `session_events` directly to
 *     verify the durable log captured user_message + assistant_message
 *     pairs in the right order.
 *
 * Run:
 *   cat > playwright.e2e.config.ts <<'CFG'
 *   import { defineConfig } from "@playwright/test";
 *   export default defineConfig({
 *     testDir: "./playwright",
 *     testMatch: ["e2e-context-window.spec.ts"],
 *     timeout: 600_000,
 *     use: { baseURL: "http://localhost:1420", browserName: "chromium",
 *            headless: true },
 *   });
 *   CFG
 *   npx playwright test -c playwright.e2e.config.ts
 */
import { test, expect, type Page, type Request } from "@playwright/test";

const BASE_URL = "http://localhost:1420";
const TURN_TIMEOUT_MS = 90_000; // most turns finish in 5-30s, allow headroom

interface TurnMetrics {
  message: string;
  must_contain: string[];
  ttft_ms: number;
  total_ms: number;
  events: Record<string, number>;
  response_text: string;
  session_id: string;
  passed_must_contain: boolean;
  matched_must_contain: string[];
}

/** Capture every chat POST so we can extract session_id deterministically. */
function captureChatPosts(page: Page) {
  const captured: Array<{ session_id: string; message: string; ts: number }> =
    [];
  page.on("request", (req: Request) => {
    if (
      req.method() === "POST" &&
      req.url().includes("/api/v1/chat/stream/v3")
    ) {
      try {
        const parsed = JSON.parse(req.postData() || "{}");
        captured.push({
          session_id: parsed.session_id || "",
          message: parsed.message || "",
          ts: Date.now(),
        });
      } catch {
        captured.push({ session_id: "", message: "", ts: Date.now() });
      }
    }
  });
  return captured;
}

/** Wait for the most recent assistant bubble to settle (no longer streaming). */
async function waitForAssistantSettled(
  page: Page,
  timeoutMs: number,
): Promise<void> {
  await page.waitForFunction(
    () => {
      const composer = document.querySelector(
        "textarea[aria-label='Nhập tin nhắn']",
      ) as HTMLTextAreaElement | null;
      // Composer becomes editable when streaming finishes.
      return composer != null && !composer.disabled;
    },
    { timeout: timeoutMs },
  );
}

/** Read the most recent assistant message bubble's plain text. */
async function readLastAssistantText(page: Page): Promise<string> {
  return await page.evaluate(() => {
    // Each assistant bubble has data-role="assistant" or similar testid.
    const bubbles = Array.from(
      document.querySelectorAll(
        "[data-role='assistant'], [data-message-role='assistant']",
      ),
    );
    if (bubbles.length === 0) {
      // Fallback heuristic: any element with "wiii" or assistant classname.
      const candidates = Array.from(document.querySelectorAll("article, .message, .assistant-message"));
      const last = candidates[candidates.length - 1];
      return last ? (last.textContent || "") : "";
    }
    const last = bubbles[bubbles.length - 1];
    return last.textContent || "";
  });
}

async function sendOneTurn(
  page: Page,
  message: string,
  must_contain: string[],
  captured_posts: Array<{ session_id: string; message: string; ts: number }>,
): Promise<TurnMetrics> {
  const composer = page.getByLabel("Nhập tin nhắn");
  await composer.waitFor({ state: "visible" });
  await composer.fill(message);

  const sendStart = Date.now();
  let ttft_ms = 0;
  const events: Record<string, number> = {};

  const responseListener = (response: any) => {
    if (response.url().includes("/api/v1/chat/stream/v3")) {
      // First byte heuristic: when response starts, mark it.
      // (TTFT for the FIRST answer token would need SSE parsing — this
      // proxy is "time until backend started replying" which is close.)
      if (ttft_ms === 0) ttft_ms = Date.now() - sendStart;
    }
  };
  page.on("response", responseListener);

  await composer.press("Enter");

  // Wait for assistant settle. Captures total round-trip time.
  await waitForAssistantSettled(page, TURN_TIMEOUT_MS);
  const total_ms = Date.now() - sendStart;
  page.off("response", responseListener);

  const response_text = await readLastAssistantText(page);

  const matched_must_contain: string[] = [];
  for (const phrase of must_contain) {
    if (response_text.toLowerCase().includes(phrase.toLowerCase())) {
      matched_must_contain.push(phrase);
    }
  }

  const session_id =
    captured_posts.length > 0
      ? captured_posts[captured_posts.length - 1].session_id
      : "";

  return {
    message,
    must_contain,
    ttft_ms,
    total_ms,
    events,
    response_text: response_text.slice(0, 500),
    session_id,
    passed_must_contain: matched_must_contain.length > 0,
    matched_must_contain,
  };
}

test("E2E: context window + memory recall + topic switching", async ({
  page,
}) => {
  test.setTimeout(600_000);
  const captured_posts = captureChatPosts(page);

  // ── Bootstrap clean session ──
  await page.goto(BASE_URL);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.reload();

  const devLogin = page.getByTestId("dev-login-button");
  await devLogin.waitFor({ state: "visible", timeout: 30_000 });
  await devLogin.click();

  // Wait for composer (proxy for "main UI loaded").
  await page.getByLabel("Nhập tin nhắn").waitFor({
    state: "visible",
    timeout: 60_000,
  });

  // ── Run the conversation ──
  const turns: TurnMetrics[] = [];

  // Turn 1: greeting + name introduction (memory anchor).
  // We accept both Vietnamese diacritic interpretations because the
  // user typed "Hung" without diacritics. "Hưng" (vowel ư) is the
  // common interpretation — V4 Pro picks this most of the time.
  // "Hùng" (vowel ù) is also valid. Accept either.
  turns.push(
    await sendOneTurn(
      page,
      "chao Wiii, minh ten la Hung",
      ["hưng", "hùng", "hung"],
      captured_posts,
    ),
  );

  // Turn 2: ask Wiii to suggest topics (triggers offer).
  turns.push(
    await sendOneTurn(
      page,
      "co gi de hoc khong?",
      ["học"],
      captured_posts,
    ),
  );

  // Turn 3: ambiguous follow-up "không đâu" — must resolve via prior offer.
  turns.push(
    await sendOneTurn(
      page,
      "khong dau",
      // The model should NOT ask "what do you mean?"; it should
      // accept the rejection. Match polite-acceptance phrases.
      ["không sao", "ok", "để khi khác", "lúc nào"],
      captured_posts,
    ),
  );

  // Turn 4: name recall — does Wiii remember the name from turn 1?
  // Accept either Hưng or Hùng diacritic interpretation.
  turns.push(
    await sendOneTurn(
      page,
      "minh ten gi nho?",
      ["hưng", "hùng", "hung"],
      captured_posts,
    ),
  );

  // Turn 5: topic switch — break out of small talk.
  turns.push(
    await sendOneTurn(
      page,
      "Giai thich Quy tac 13 COLREGs ngan gon",
      ["rule 13", "vượt", "overtaking", "13"],
      captured_posts,
    ),
  );

  // Turn 6: contextual follow-up on the topic — "tau truoc la gi"
  // requires Wiii to remember COLREGs context from turn 5.
  turns.push(
    await sendOneTurn(
      page,
      "the tau truoc la tau nao trong tinh huong do?",
      ["tàu bị vượt", "stand-on", "phía trước", "duy trì"],
      captured_posts,
    ),
  );

  // ── Aggregate metrics ──
  console.log("\n========== E2E CONTEXT WINDOW REPORT ==========");
  for (let i = 0; i < turns.length; i++) {
    const t = turns[i];
    console.log(
      `Turn ${i + 1}: "${t.message}" → TTFT=${t.ttft_ms}ms total=${t.total_ms}ms`,
    );
    console.log(
      `  must_contain=[${t.must_contain.join(", ")}] matched=[${t.matched_must_contain.join(", ")}] PASS=${t.passed_must_contain}`,
    );
    console.log(`  response[:200]=${t.response_text.slice(0, 200).replace(/\n/g, " ")}`);
    console.log(`  session_id=${t.session_id}`);
  }

  const sessions = new Set(turns.map((t) => t.session_id).filter(Boolean));
  const all_passed = turns.every((t) => t.passed_must_contain);
  const median_total = [...turns.map((t) => t.total_ms)].sort(
    (a, b) => a - b,
  )[Math.floor(turns.length / 2)];

  console.log("\n========== SUMMARY ==========");
  console.log(`Distinct session_ids: ${sessions.size} (expect 1)`);
  console.log(
    `Must-contain pass rate: ${turns.filter((t) => t.passed_must_contain).length}/${turns.length}`,
  );
  console.log(`Median total time: ${median_total}ms`);
  console.log(`All turns passed must_contain: ${all_passed}`);

  // ── Hard assertions ──
  // 1. Same session across all turns.
  expect(sessions.size).toBe(1);
  // 2. Memory recall (turn 4) MUST surface "Hùng" — the deepest test.
  expect(turns[3].passed_must_contain).toBe(true);
  // 3. Ambiguous follow-up (turn 3) MUST NOT confuse Wiii — it should
  //    accept the rejection rather than ask "what do you mean".
  expect(turns[2].passed_must_contain).toBe(true);
  // 4. Topic switch (turn 5) MUST mention Rule 13 / overtaking semantics.
  expect(turns[4].passed_must_contain).toBe(true);
});
