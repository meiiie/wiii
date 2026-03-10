from __future__ import annotations

from pathlib import Path
import json
import time

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path("E:/Sach/Sua/AI_v1/.claude/reports/playwright")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = "Ve mot bieu do bang Python va gui lai file PNG nhu artifact."


def dump(page, name: str, *, console_logs: list[dict], network_logs: list[dict]) -> None:
    payload = {
        "url": page.url,
        "title": page.title(),
        "body_excerpt": page.locator("body").inner_text()[:16000],
        "buttons": page.locator("button").all_inner_texts(),
        "thinking_toggle_states": page.locator(".thinking-block__toggle").evaluate_all(
            """els => els.map((el, index) => ({
                index,
                expanded: el.getAttribute("aria-expanded"),
                text: el.innerText.slice(0, 220),
            }))"""
        ),
        "thinking_content_shells": page.locator(".thinking-block__content-shell").evaluate_all(
            """els => els.map((el, index) => ({
                index,
                height: Math.round(el.getBoundingClientRect().height),
                text: el.innerText.slice(0, 220),
            }))"""
        ),
        "storage": page.evaluate("() => ({ local: {...window.localStorage}, session: {...window.sessionStorage} })"),
        "console": console_logs[-200:],
        "network": network_logs[-300:],
    }
    (ARTIFACT_DIR / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    page.screenshot(path=str(ARTIFACT_DIR / f"{name}.png"), full_page=True)


def wait_for_shell(page) -> None:
    page.wait_for_timeout(1000)
    for _ in range(30):
        has_textarea = page.locator("textarea").count() > 0
        password_inputs = page.locator("input[type='password']").count()
        button_count = page.locator("button").count()
        if has_textarea or (password_inputs == 0 and button_count >= 8):
            return
        page.wait_for_timeout(500)
    raise RuntimeError("App shell did not appear after dev-mode login.")


def wait_for_stream_completion(page, timeout_seconds: int = 140) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        body_text = page.locator("body").inner_text()
        if "Dừng Wiii" not in body_text and "Dung Wiii" not in body_text:
            return
        page.wait_for_timeout(1000)
    raise RuntimeError("Stream did not finish before timeout.")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1400})
        page = context.new_page()

        console_logs: list[dict] = []
        network_logs: list[dict] = []

        page.on(
            "console",
            lambda msg: console_logs.append(
                {
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location,
                }
            ),
        )
        page.on(
            "response",
            lambda response: network_logs.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "ok": response.ok,
                }
            ),
        )

        page.goto("http://127.0.0.1:1420/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        dump(page, "50_chart_before_login", console_logs=console_logs, network_logs=network_logs)

        buttons = page.locator("button")
        if buttons.count() < 3:
            raise RuntimeError("Login screen did not render the expected developer mode button.")
        buttons.nth(2).click()
        password_input = page.locator("input[type='password']").first
        password_input.fill("local-dev-key")
        page.locator("button").nth(2).click()
        page.wait_for_timeout(3000)
        dump(page, "51a_chart_after_devmode_submit", console_logs=console_logs, network_logs=network_logs)

        wait_for_shell(page)
        dump(page, "51_chart_after_login", console_logs=console_logs, network_logs=network_logs)

        composer = page.locator("textarea").first
        composer.click()
        composer.fill(PROMPT)
        page.keyboard.press("Enter")

        for checkpoint in (12, 35, 70):
            time.sleep(checkpoint if checkpoint == 12 else checkpoint - (12 if checkpoint == 35 else 35))
            dump(page, f"52_chart_tplus_{checkpoint:02d}s", console_logs=console_logs, network_logs=network_logs)

        wait_for_stream_completion(page)
        dump(page, "53_chart_after_done", console_logs=console_logs, network_logs=network_logs)
        page.wait_for_timeout(4500)
        dump(page, "54_chart_after_settle", console_logs=console_logs, network_logs=network_logs)

        browser.close()


if __name__ == "__main__":
    main()
