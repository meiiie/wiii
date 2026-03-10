import { readFile } from "node:fs/promises";

const RESULT_SENTINEL = "__WIII_BROWSER_RESULT__";

async function loadJob(jobPath) {
  if (!jobPath) {
    throw new Error("Missing browser job path.");
  }
  const raw = await readFile(jobPath, "utf8");
  return JSON.parse(raw);
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {}
  try {
    return await import("playwright-core");
  } catch {}
  throw new Error("Playwright is not installed in the browser sandbox template.");
}

async function main() {
  const job = await loadJob(process.argv[2]);
  const playwright = await loadPlaywright();
  const browser = await playwright.chromium.launch({ headless: true });

  try {
    const context = await browser.newContext({
      viewport: {
        width: Number(job.viewport?.width || 1440),
        height: Number(job.viewport?.height || 1024),
      },
    });

    try {
      const page = await context.newPage();
      const timeoutMs = Number(job.timeout_ms || 120000);
      page.setDefaultTimeout(timeoutMs);

      const response = await page.goto(job.url, {
        waitUntil: job.wait_until || "networkidle",
        timeout: timeoutMs,
      });

      let screenshotBase64 = "";
      if (job.capture_screenshot) {
        const screenshot = await page.screenshot({
          type: "png",
          fullPage: Boolean(job.full_page),
        });
        screenshotBase64 = screenshot.toString("base64");
      }

      const excerpt = await page.evaluate(() => {
        const body = document?.body?.innerText || "";
        return body.replace(/\s+/g, " ").trim().slice(0, 500);
      });

      const result = {
        requested_url: job.url,
        final_url: page.url(),
        title: await page.title(),
        response_status: response ? response.status() : null,
        excerpt,
        screenshot_base64: screenshotBase64,
        label: job.screenshot_label || "Browser page loaded",
      };

      console.log(`${RESULT_SENTINEL}${JSON.stringify(result)}`);
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
