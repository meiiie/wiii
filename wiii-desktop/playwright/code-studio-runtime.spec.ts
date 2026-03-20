import { expect, test } from "@playwright/test";

const INITIAL_PROMPT =
  "Build a mini pendulum physics app in chat with drag interaction. Use Code Studio and keep it inline with the conversation.";
const FOLLOWUP_PROMPT =
  "Keep the current app only. Add sliders for gravity and damping, patch the same session, and do not create a second app.";
const VN_INITIAL_PROMPT =
  "Hãy mô phỏng vật lý con lắc bằng mini app HTML/CSS/JS có kéo thả chuột";
const VN_FOLLOWUP_PROMPT_1 =
  "Giữ app hiện tại, thêm slider điều chỉnh trọng lực và ma sát";
const VN_FOLLOWUP_PROMPT_2 =
  "Thêm hiển thị góc lệch và vận tốc theo thời gian";
const VN_SHOW_CODE_PROMPT =
  "Cho tôi xem code đang được sinh ra";

function buildInitScript(serverUrl: string, userId: string, displayName: string) {
  const settingsPayload = {
    server_url: serverUrl,
    api_key: "local-dev-key",
    user_id: userId,
    user_role: "admin",
    display_name: displayName,
    llm_provider: "google",
    theme: "light",
    default_domain: "maritime",
  };
  const authPayload = {
    data: {
      user: null,
      authMode: "legacy",
    },
  };

  return `
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem('wiii:app_settings', JSON.stringify(${JSON.stringify(settingsPayload)}));
    localStorage.setItem('wiii:auth_state', JSON.stringify(${JSON.stringify(authPayload)}));
  `;
}

async function sendPrompt(page, prompt: string) {
  const inputBox = page.locator("textarea[aria-label]").first();
  await inputBox.waitFor({ state: "visible", timeout: 60_000 });
  await inputBox.fill(prompt);
  await inputBox.press("Enter");
}

test.describe("code studio runtime", () => {
  test("streams a code studio app inline and versions follow-up patches", async ({ page }, testInfo) => {
    const uniqueUser = `code-studio-e2e-${Date.now()}`;
    await page.addInitScript(buildInitScript("http://127.0.0.1:8000", uniqueUser, "Code Studio Smoke"));
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForLoadState("networkidle", { timeout: 60_000 });

    await sendPrompt(page, INITIAL_PROMPT);

    const inlineCard = page.locator(".code-studio-card").first();
    const panel = page.locator(".code-studio-panel").first();

    await expect(inlineCard).toBeVisible({ timeout: 120_000 });
    await expect(panel).toBeVisible({ timeout: 120_000 });
    await expect(page.getByTestId("thinking-block")).toHaveCount(0);

    await expect
      .poll(async () => {
        const doneText = await panel.innerText();
        return /da xong|đã xong/i.test(doneText);
      }, {
        timeout: 120_000,
        intervals: [1_000, 1_500, 2_000],
      })
      .toBe(true);

    await expect(panel.locator("iframe").first()).toBeVisible({ timeout: 120_000 });
    await expect(inlineCard.getByRole("button", { name: /xem code/i })).toBeVisible();

    await sendPrompt(page, FOLLOWUP_PROMPT);

    await expect
      .poll(async () => {
        const versionButtons = await panel.locator("button").evaluateAll((nodes) =>
          nodes
            .map((node) => node.textContent?.trim() || "")
            .filter((label) => /^v\d+$/i.test(label)),
        );
        return versionButtons;
      }, {
        timeout: 120_000,
        intervals: [1_000, 1_500, 2_000],
      })
      .toEqual(["v1", "v2"]);

    await expect(panel.locator("iframe").first()).toBeVisible({ timeout: 120_000 });
    await expect(inlineCard.getByRole("button", { name: /xem code/i })).toBeVisible();

    await page.screenshot({
      path: testInfo.outputPath("code-studio-runtime.png"),
      fullPage: true,
    });
  });

  test("supports vietnamese follow-up app edits and explicit code view", async ({ page }, testInfo) => {
    const uniqueUser = `code-studio-vn-${Date.now()}`;
    await page.addInitScript(buildInitScript("http://127.0.0.1:8000", uniqueUser, "Code Studio VN Smoke"));
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForLoadState("networkidle", { timeout: 60_000 });

    const panel = page.locator(".code-studio-panel").first();

    await sendPrompt(page, VN_INITIAL_PROMPT);
    await expect(panel).toBeVisible({ timeout: 120_000 });
    await expect
      .poll(async () => /da xong|đã xong/i.test(await panel.innerText()), {
        timeout: 120_000,
        intervals: [1_000, 1_500, 2_000],
      })
      .toBe(true);

    await sendPrompt(page, VN_FOLLOWUP_PROMPT_1);
    await expect
      .poll(async () => {
        const versionButtons = await panel.locator("button").evaluateAll((nodes) =>
          nodes
            .map((node) => node.textContent?.trim() || "")
            .filter((label) => /^v\d+$/i.test(label)),
        );
        return versionButtons;
      }, {
        timeout: 120_000,
        intervals: [1_000, 1_500, 2_000],
      })
      .toEqual(["v1", "v2"]);

    await sendPrompt(page, VN_FOLLOWUP_PROMPT_2);
    await expect
      .poll(async () => {
        const versionButtons = await panel.locator("button").evaluateAll((nodes) =>
          nodes
            .map((node) => node.textContent?.trim() || "")
            .filter((label) => /^v\d+$/i.test(label)),
        );
        return versionButtons;
      }, {
        timeout: 120_000,
        intervals: [1_000, 1_500, 2_000],
      })
      .toEqual(["v1", "v2", "v3"]);

    await sendPrompt(page, VN_SHOW_CODE_PROMPT);

    await expect(panel.locator("pre code").first()).toBeVisible({ timeout: 120_000 });
    await expect(panel.locator("iframe")).toHaveCount(0);

    await page.screenshot({
      path: testInfo.outputPath("code-studio-runtime-vn.png"),
      fullPage: true,
    });
  });
});

// ─────────────────────────────────────────────────────────────────
// Phase 8: Visual Intelligence routing smoke tests
// ─────────────────────────────────────────────────────────────────

async function sendAndSettle(page, prompt: string) {
  await sendPrompt(page, prompt);
  const input = page.locator("textarea[aria-label]").first();
  await expect
    .poll(
      async () => page.locator('[aria-label="Dừng tạo phản hồi"]').count(),
      { timeout: 120_000, intervals: [1_500, 2_000, 2_500] },
    )
    .toBe(0);
  await expect(input).toBeEnabled({ timeout: 30_000 });
  await page.waitForTimeout(2_000);
}

async function setupFresh(page, label: string) {
  const uid = `routing-${label}-${Date.now()}`;
  await page.addInitScript(buildInitScript("http://127.0.0.1:8000", uid, `Routing ${label}`));
  await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 60_000 });
}

test.describe("Phase 8 routing", () => {
  test("chart: tốc độ tàu container → visual-block, NOT code-studio", async ({ page }, testInfo) => {
    await setupFresh(page, "chart");
    await sendAndSettle(page, "Vẽ biểu đồ so sánh tốc độ các loại tàu container");

    const visualCount = await page.getByTestId("visual-block").count();
    const csCount = await page.locator(".code-studio-card").count();

    expect(visualCount).toBeGreaterThanOrEqual(1);
    expect(csCount).toBe(0);

    await page.screenshot({ path: testInfo.outputPath("routing-chart.png"), fullPage: true });
  });

  test("simulation: con lắc kéo thả → Code Studio or iframe app", async ({ page }, testInfo) => {
    await setupFresh(page, "pendulum");
    await sendAndSettle(page, "Hãy mô phỏng vật lý con lắc có kéo thả chuột");

    const csCount = await page.locator(".code-studio-card").count();
    const iframeCount = await page.locator("iframe").count();
    const visualCount = await page.getByTestId("visual-block").count();

    const hasApp = csCount > 0 || (visualCount > 0 && iframeCount > 0);
    expect(hasApp).toBe(true);

    await page.screenshot({ path: testInfo.outputPath("routing-pendulum.png"), fullPage: true });
  });

  test("simulation: COLREG Rule 15 → simulation lane", async ({ page }, testInfo) => {
    await setupFresh(page, "colreg");
    await sendAndSettle(page, "Mô phỏng Quy tắc 15 COLREGs");

    const csCount = await page.locator(".code-studio-card").count();
    const iframeCount = await page.locator("iframe").count();
    const visualCount = await page.getByTestId("visual-block").count();

    const hasSimulation = csCount > 0 || (visualCount > 0 && iframeCount > 0);
    expect(hasSimulation).toBe(true);

    await page.screenshot({ path: testInfo.outputPath("routing-colreg.png"), fullPage: true });
  });

  test("artifact: mini HTML app → artifact or code-studio lane", async ({ page }, testInfo) => {
    await setupFresh(page, "artifact");
    await sendAndSettle(page, "Tạo một mini app HTML để nhúng");

    const csCount = await page.locator(".code-studio-card").count();
    const artCount = await page.locator(".artifact-card-shell").count();
    const iframeCount = await page.locator("iframe").count();

    const hasArtifact = csCount > 0 || artCount > 0 || iframeCount > 0;
    expect(hasArtifact).toBe(true);

    await page.screenshot({ path: testInfo.outputPath("routing-artifact.png"), fullPage: true });
  });
});
