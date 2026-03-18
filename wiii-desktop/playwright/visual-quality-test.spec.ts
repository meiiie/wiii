/**
 * Visual Quality API Tests — test multiple simulation types via backend API.
 *
 * Sends visual queries directly to the streaming API, collects SSE events,
 * extracts HTML output, and scores quality markers.
 *
 * Run: npx playwright test playwright/visual-quality-test.spec.ts
 */
import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const API_URL = "http://localhost:8000";
const __filename2 = fileURLToPath(import.meta.url);
const __dirname2 = dirname(__filename2);

function getApiKey(): string {
  const envPath = resolve(__dirname2, "../../maritime-ai-service/.env");
  const envContent = readFileSync(envPath, "utf-8");
  const match = envContent.match(/^API_KEY=["']?([^"'\r\n]+)/m);
  return match?.[1] ?? "";
}

interface QualityResult {
  name: string;
  lines: number;
  chars: number;
  score: number;
  markers: Record<string, boolean>;
  qualityGateRejections: number;
  toolCalls: number;
}

async function testVisualQuery(
  name: string,
  query: string,
  apiKey: string,
): Promise<QualityResult> {
  const sessionId = `pw-${name}-${Date.now()}`;

  const response = await fetch(`${API_URL}/api/v1/chat/stream/v3`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify({
      message: query,
      user_id: "playwright-test",
      session_id: sessionId,
      role: "student",
    }),
  });

  const text = await response.text();

  // Parse SSE events
  const events = text.match(/data: ({.*?})\n/g) || [];
  const qualityRejections = (text.match(/Quality score/g) || []).length;
  const toolCalls = (text.match(/tool_create_visual_code/g) || []).length;

  // Find best HTML
  let bestHtml = "";
  for (const eventStr of events) {
    try {
      const data = eventStr.replace("data: ", "").trim();
      const obj = JSON.parse(data);
      const content = obj.content;
      if (content && typeof content === "object") {
        const html = content.fallback_html || content.code_html || "";
        if (html.length > bestHtml.length) bestHtml = html;
      }
    } catch {
      // skip
    }
  }

  // Score quality markers
  const htmlLower = bestHtml.toLowerCase();
  const markers: Record<string, boolean> = {
    css_vars: bestHtml.includes("--bg") && bestHtml.includes("--accent"),
    canvas_raf:
      htmlLower.includes("<canvas") &&
      bestHtml.includes("requestAnimationFrame"),
    delta_time: ["deltaTime", "dt ", "elapsed"].some((k) =>
      bestHtml.includes(k),
    ),
    bridge: htmlLower.includes("wiiivisualbridge"),
    readouts:
      htmlLower.includes("readout") ||
      bestHtml.includes("aria-live") ||
      (htmlLower.match(/<span id=/g) || []).length >= 3,
    planning: bestHtml.includes("STATE MODEL"),
    dark_mode: bestHtml.includes("prefers-color-scheme"),
    fragment: !bestHtml.includes("DOCTYPE"),
    grid_flex: htmlLower.includes("grid") || htmlLower.includes("flex"),
    controls: (htmlLower.match(/type=.range/g) || []).length >= 2,
  };

  const score = Object.values(markers).filter(Boolean).length;
  const lines = bestHtml.split("\n").length;

  return {
    name,
    lines,
    chars: bestHtml.length,
    score,
    markers,
    qualityGateRejections: qualityRejections,
    toolCalls,
  };
}

test.describe("Visual Quality API Tests", () => {
  let apiKey: string;

  test.beforeAll(() => {
    apiKey = getApiKey();
    expect(apiKey.length).toBeGreaterThan(0);
  });

  test("projectile motion — Canvas simulation quality", async () => {
    test.setTimeout(180_000);
    const result = await testVisualQuery(
      "projectile",
      "Mo phong chuyen dong nem xien bang Canvas co dieu chinh goc va van toc",
      apiKey,
    );
    console.log(
      `[projectile] ${result.lines} lines, ${result.chars} chars, score ${result.score}/10, rejections: ${result.qualityGateRejections}, tools: ${result.toolCalls}`,
    );
    console.log(`  markers:`, result.markers);

    expect(result.chars).toBeGreaterThan(500);
    expect(result.markers.canvas_raf).toBe(true);
    expect(result.markers.grid_flex).toBe(true);
  });

  test("solar system — orbital mechanics quality", async () => {
    test.setTimeout(180_000);
    const result = await testVisualQuery(
      "solar-system",
      "Mo phong he mat troi don gian voi cac hanh tinh quay quanh bang Canvas",
      apiKey,
    );
    console.log(
      `[solar-system] ${result.lines} lines, ${result.chars} chars, score ${result.score}/10, rejections: ${result.qualityGateRejections}, tools: ${result.toolCalls}`,
    );
    console.log(`  markers:`, result.markers);

    expect(result.chars).toBeGreaterThan(500);
    expect(result.markers.canvas_raf).toBe(true);
  });

  test("spring-mass — physics simulation quality", async () => {
    test.setTimeout(180_000);
    const result = await testVisualQuery(
      "spring-mass",
      "Mo phong he lo xo khoi luong bang Canvas co dieu chinh do cung va khoi luong",
      apiKey,
    );
    console.log(
      `[spring-mass] ${result.lines} lines, ${result.chars} chars, score ${result.score}/10, rejections: ${result.qualityGateRejections}, tools: ${result.toolCalls}`,
    );
    console.log(`  markers:`, result.markers);

    expect(result.chars).toBeGreaterThan(500);
    expect(result.markers.canvas_raf).toBe(true);
  });
});
